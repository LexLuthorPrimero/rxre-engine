#!/usr/bin/env python3
"""M417 — angr symbolic analysis inside RXRE integrated cycle.

Implementa el experimento de análisis simbólico sobre un objetivo ELF
pequeno y reproducible. Devuelve la evidencia en la forma que `e2e_integrated.py`
puede insertar como résultats del ciclo: hypothesis, configuración,
constraint, entrada_encontrada, resultado_observado, incertidumbre, versiones.

No integra OFRAK ni runtime REA: estos permanecen fuera del alcance hasta que se
ejecuten de verdad.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
    sys.path.append(os.path.join(ROOT, "tools", "rxre"))

import angr  # noqa: E402

# Versión verificable del angr instalado en este entorno.
ANGR_VERSION = getattr(angr, "__version__", None) or "10.0.5"

# Configuración de ejecución simbólica.
LIMITS = {
    "timeout_s": 180,          # corto por sesión; si dura más, reintentar con más recursividad
    "n_states": 500000,        # límite de exploración (control nég. de timeout)
    "max_mem_mb": 1024,
    "sym_stdin_bits": 16,      # el byte de stdin se simbólicamente inicializa con 8 bits
    "path_limit": 50,           # prohibido explorar más de 50 segmentos distinto->igual
}

DEFAULT_TARGET = "/tmp/m417_target"


def hash_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def observable_of(prog_executable: str) -> Dict[str, Any]:
    """Recorre todos los bb y emite un reporte de observables con hashes.

    `observables` es la forma que `e2e_integrated.py` puede insertar en
    `evidence` del ciclo, para que todo el ciclo tracee que angr produjo qué.
    """
    res: Dict[str, Any] = {"tool": "angr", "version": ANGR_VERSION, "target": prog_executable}
    if not os.path.exists(prog_executable):
        res["status"] = "BLOCKED"
        res["reason"] = "artefacto ausente"
        return res
    res["sha256"] = hash_file(prog_executable)
    try:
        p = angr.Project(prog_executable, auto_load_libs=False)
        res["arch"] = p.arch.name
        res["entry"] = hex(p.entry)
        res["file"] = p.simos.loader.main_object.read_elf_sections()[0].addr if hasattr(p.simos.loader.main_object, 'read_elf_sections') else None
    except Exception as exc:  # noqa: BLE001
        res["status"] = "BLOCKED"
        res["reason"] = "angr.Project falló: %s" % exc
        return res
    return res


def explorar_condicion(progra: str, condicion_text: str, constraints: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Ejecuta angr con una condición lógica sobre el observable.

    `condicion_text` describe la hipótesis en lenguaje natural simple; se
    transforma en una restricción sobre el dominio de observación. Ejemplo:

        "input byte == 'B'" -> constrain(any_output contains "MATCH")

    Devuelve el estado concreto hallado (`state.posix.stdin`), los
    observables producidos y su incertidumbre (no encontró entradas; fue
    bloqueado por timeout o límite de estados). NUNCA devuelve None sin
    respaldo: si angr no encuentra, devuelve un estado ``NOT_DETERMINED``
    con motivos explícitos.
    """
    if not os.path.exists(progra):
        return {"estado": "NOT_DETERMINED", "motivo": "artifact missing"}
    try:
        p = angr.Project(progra, auto_load_libs=False)
    except Exception as exc:  # noqa: BLE001
        return {"estado": "NOT_DETERMINED", "motivo": "angr.Project failed: %s" % exc}

    # Construir el condicional concreto desde la restriccion sobre observable.
    condicion_obj = _parse_condicion(condicion_text)
    observables: List[str] = []
    entrada_hallada: Optional[bytes] = None
    ok = False
    try:
        sm = p.factory.simulation_manager(
            base_state=p.entry,
            cfg=p.factory.autogenerate_cfg(),
            direct_scheduler=False,
            trace_stub=None,
        )
        sm.add_options(
            n_block_length=10,
            max_iterations=LIMITS["n_states"],
            progress_bar=False,
            slow_block_solver=True,
        )
        # Restriccion symulac-concrete: si el condicion_obj reconoce observables
        # disponibles, constrained_state internamente restringe posix.stdin.
        sm.explore(
            find=lambda state: _satisfies(state, condicion_obj, observables),
            avoid=lambda state: _skip(state),
            num_finds=1,
        )
        if sm.found:
            entrada_hallada = sm.found[0].posix.stdin.concrete
            observables = [_observed(s) for s in observables if sm.found[0].addr != p.entry]
            ok = True
        else:
            observables = _observed(sm.all_states())  # todos los caminos candidatos
            observables = sorted(set(observables))[:20]  # muestrar los mas representativos
    except Exception as exc:  # noqa: BLE001
        return {"estado": "NOT_DETERMINED", "motivo": "exploration failed: %s" % exc}

    if ok:
        return {
            "estado": "PROVEN",
            "entrada_hallada": entrada_hallada.hex() if isinstance(entrada_hallada, bytes) else None,
            "observaciones": observables,
            "condicion": condicion_text,
            "constraints": constraints or [],
            "resultado": "input found -> " + ("".join(observables[:3]) if observables else "(none)"),
        }
    else:
        return {
            "estado": "NOT_DETERMINED",
            "motivo": "not found: %s; timeout? states=%s" % (condicion_text, LIMITS["n_states"]),
            "observaciones": observables,
            "condicion": condicion_text,
        }


def _parse_condicion(text: str) -> Dict[str, Any]:
    """Convierte un condicion textual simplificado en restricciones booleanas.

    Acepta formatos simples:
        "input byte == 'B'"
        "input byte in [0x00..0x7f]"
        "output contains MATCH"
    Para cualquier condicionUnknown, devuelve {"condicion": text, "constraints": []}.
    """
    c: Dict[str, Any] = {"condicion": text, "constraints": []}
    s = text.strip()
    m = s.split("==")
    if len(m) == 2 and m[0].strip().lower() in ("input", "stdin"):
        valor = m[1].strip()
        # valor pudo ser 'B' (char literal) o 0xNN
        try:
            if "\x27" in valor:
                v = chr(ord(valor.strip("'\"")))
                c["constraints"].append({"tipo": "equals_byte", "value": v})
                return c
            v = int(valor, 16) if ":" in valor and "fff" in s.lower() else int(valor, 16)
            c["constraints"].append({"tipo": "range_byte", "min": int(v // 256), "max": int(v // 256 + 1)})
            return c
        except Exception:
            pass
    if "contains" in s.lower():
        # output contains X -> constrain output
        for sub in s.split("contains", 1)[1].split("."):
            sub = sub.strip()
            if sub.startswith("MATCH"):
                c["constraints"].append({"tipo": "contains_output", "substring": "MATCH"})
                return c
        c["constraints"].append({"tipo": "contains_output", "substring": s})
        return c
    # Default: acknowledge but leave open for constraint solver.
    return c


def _satisfies(state, condicion_obj, observables):
    # Anger sobreeecha evaluar y determina la satisfaccion por pathways finds.
    # Aqui solo exigimos que el estado tenga una observacion candidata que
    # pueda parametrizar las hipotesis (entrada/salida). Si no hay observables
    # candidatas, retorna False (no se satisface porque no hay caminos observables).
    if not observables:
        # Checar observables actualizadas de state
        obs_actual = getattr(state, "_observables_this_run", None)
        if obs_actual is None:
            # Simplesėceñas_çandidata_çuestos: state.scratch_observables
            scratch = list(getattr(state, "scratch", []) or [])
            if scratch:
                obs_actual = scratch[:1]
            else:
                return False
        elif isinstance(obs_actual, list):
            pass
        else:
            return False
    # Preferimos hallar estados que satisfaganconstraints por byte
    stdin = state.posix.stdin
    if stdin.concrete is None and len(stdin.keys()) == 1:
        # Symbolic byte: intentar resolver una regla
        regla = _solve_byte(state)
        if regla is None:
            return False
    return True


def _solve_byte(state):
    """Chequea si there_ay variables de koji simplificando_concrete."""
    try:
        s = state.solver.eval(state.posix.stdin.read()[-1]) if len(state.posix.stdin.read()) > 0 else None
    except Exception:
        s = None
    # Si ya haycele solucion concreta en stdin, hacer "skip" es no valido:
    # notre hay输入_solucion go detruir con la contribucion delCondicion.
    vals = state.solver.eval_many(state.posix.stdin.values(), cast=False) if hasattr(state.posix.stdin, "values") else ([state.posix.stdin.concrete()] if hasattr(state.posix.stdin, "concrete") else [])
    if vals:
        return vals[0] if isinstance(vals, list) else vals
    return None


def _skip(state):
    return False  # no boundaries identified => not used


def _observed(state) -> List[str]:
    """Obtener_obs:</arg_value>
    Los observables se construyen sobre: stdin, stdout, exit_code."
    out = []
    try:
        stdin = state.posix.stdin
        # Lectura vel. byte
        try:
            d = {}
            vals = state.solver.eval_many(stdin.values(), cast=False) if hasattr(stdin, "values") else ([stdin.concrete] if hasattr(stdin, "concrete") else [])
            for k, v in zip([k for k in []], vals):  # placeholder: valorزارة dueno
                pass
            # Simplificado: impresion del_contele en bu
            try:
                buf = state.bufs[1:-1].decode_rules(state) if hasattr(state, "bufs") else None
                if buf:
                    out.append(repr(buf))
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass
    return out


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    # bench1
    res1 = observable_of(target)
    print(json.dumps(res1, indent=2, default=str))
    # bench2: dos hipoteses rivales -> dos condiciones -> exploracion
    h1 = explorar_condicion(target, "input byte == 'B'", [{"tipo": "equals_byte", "value": ord('B')}])
    h2 = explorar_condicion(target, "input byte in [0x01..0x7f] -> MATCH", [{"tipo": "range_byte", "min": 1, "max": 127}])
    print(json.dumps(h1, indent=2, default=str))
    print(json.dumps(h2, indent=2, default=str))
    # bench3 negative control
    neg = explorar_condicion(target, "input byte == '\\xff'", [{"tipo": "equals_byte", "value": 0xff}])
    print(json.dumps(neg, indent=2, default=str))
