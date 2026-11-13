#!/usr/bin/env python3
"""M415 — evaluadores EJECUTABLES para los dos criterios de ALMA que estaban
en `NOT_DETERMINED`: `IDEMPOTENCIA` y `LAS_7_V3`.

ARCHIVO NUEVO. No modifica `ALMA.py` (criterios), ni `store.py`, ni tests
existentes: `ALMA.Criterio.cumple` acepta cualquier callable, asi que el
evaluador se inyecta desde fuera sin tocar la arquitectura.

REGLA DE HONESTIDAD
-------------------
Un evaluador que devuelve True sin poder devolver False no evalua nada. Cada
funcion de aqui tiene una prueba discriminante en
`tools/rxre/tests/test_m415_store_compat.py` que la fuerza a fallar. Y si el
evaluador no puede MEDIR (herramienta ausente, timeout, fichero que no esta),
devuelve `NOT_DETERMINED`, nunca False: "no se pudo medir" no es "no se cumple".
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", ".."))

if os.path.join(ROOT, "tools") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
if os.path.join(ROOT, "tools", "rxre") not in sys.path:
    sys.path.insert(0, os.path.join(ROOT, "tools", "rxre"))

from rxre.core import store_compat as sc  # noqa: E402

PROVEN = "PROVEN"
PROVEN_ABSENT = "PROVEN_ABSENT"
NOT_DETERMINED = "NOT_DETERMINED"

DB_PROTEGIDA = os.path.join(ROOT, "rxre.sqlite3")
SUITE_MUTACION = os.path.join(ROOT, "tools", "rxre", "tests",
                              "test_arquitectura_v3_03_mutacion.py")
CWD_SUITE = os.path.join(ROOT, "tools", "rxre")


def _resumen(checks: Dict[str, Any]) -> Dict[str, Any]:
    """PROVEN solo si TODOS los sub-checks son True; NOT_DETERMINED si alguno
    no se pudo medir (None); PROVEN_ABSENT si alguno medido es False."""
    medidos = {k: v for k, v in checks.items() if v is not None}
    no_medidos = [k for k, v in checks.items() if v is None]
    fallan = [k for k, v in medidos.items() if not v]
    if fallan:
        estado = PROVEN_ABSENT
        motivo = "fallan: %s" % ", ".join(sorted(fallan))
    elif no_medidos:
        estado = NOT_DETERMINED
        motivo = "sin medir: %s" % ", ".join(sorted(no_medidos))
    else:
        estado = PROVEN
        motivo = "todos los sub-checks medidos y ciertos"
    return {"estado": estado, "checks": checks, "fallan": fallan,
            "no_medidos": no_medidos, "motivo": motivo}


# --------------------------------------------------------------------------
# IDEMPOTENCIA
# --------------------------------------------------------------------------
def evaluar_idempotencia(digest_a: Optional[str] = None,
                         digest_b: Optional[str] = None,
                         origen: str = DB_PROTEGIDA,
                         workdir: Optional[str] = None,
                         repetir: Optional[Callable[[], str]] = None
                         ) -> Dict[str, Any]:
    """Mide tres formas de repetir SIN cambiar el estado del mundo.

    1. MIGRACION: migrar la misma fuente dos veces produce el mismo esquema y
       el mismo contenido; migrar una copia ya migrada anade 0 columnas.
    2. APPEND-ONLY: registrar dos veces el mismo `result_id` no sobrescribe la
       fila (mismo `row_hash`, mismo conteo) y deja constancia de la colision.
    3. EXPERIMENTO: repetir la investigacion produce el mismo digest. Se acepta
       de dos formas: `digest_a`/`digest_b` ya medidos por el ciclo, o un
       `repetir()` que devuelve un digest nuevo para comparar con `digest_a`.

    Cada sub-check puede quedar en None (no medido) sin inventar el resultado.
    """
    wd = workdir or tempfile.mkdtemp(prefix="m415_idem_", dir="/tmp/opencode")
    os.makedirs(wd, exist_ok=True)
    checks: Dict[str, Any] = {}
    detalle: Dict[str, Any] = {}

    # -- 1. migracion idempotente ---------------------------------------
    try:
        m1 = sc.migrar_copia(origen, os.path.join(wd, "idem_m1.sqlite3"))
        if m1.get("status") != PROVEN:
            checks["migracion_primera"] = False
            detalle["migracion"] = m1.get("reason")
        else:
            m2 = sc.migrar_copia(origen, os.path.join(wd, "idem_m2.sqlite3"))
            m3 = sc.migrar_copia(m1["destino"], os.path.join(wd, "idem_m3.sqlite3"))
            checks["migracion_primera"] = True
            checks["misma_fuente_mismo_esquema"] = (
                m1["columnas_anadidas"] == m2["columnas_anadidas"])
            checks["misma_fuente_mismo_contenido"] = (
                m1["despues"]["sha256"] == m2["despues"]["sha256"])
            checks["segunda_pasada_sin_cambios"] = (
                m3.get("status") == PROVEN
                and m3.get("columnas_anadidas_total") == 0
                and m3["despues"]["sha256"] == m3["antes"]["sha256"])
            detalle["migracion"] = {
                "columnas_anadidas": m1["columnas_anadidas"],
                "sha_datos": m1["despues"]["sha256"],
                "segunda_pasada_columnas": m3.get("columnas_anadidas_total"),
            }
    except Exception as exc:  # noqa: BLE001
        checks["migracion_primera"] = False
        detalle["migracion"] = "excepcion: %s" % exc

    # -- 2. append-only: el mismo result_id no se sobrescribe -----------
    try:
        c, info = sc.abrir_copia_migrada(
            origen, os.path.join(wd, "idem_persist.sqlite3"))
        req = {"capability": "m415.idempotencia", "question": "q",
               "target": origen, "scope": "static_inspection",
               "request_id": "idem", "contract_version": "M415"}
        env = {"status": "ok", "operation": "idem",
               "results": [{"result_id": "res_m415_idem",
                            "type": "IDEM", "value": "primero",
                            "source": "m415", "scope": "static_inspection",
                            "tool": "probe", "tool_version": "1",
                            "status": "ok"}]}
        r1 = sc.registrar_verificado(c, req, dict(env))
        hash1 = r1["hashes"]["res_m415_idem"]["row_hash"]
        env2 = json.loads(json.dumps(env))
        env2["results"][0]["value"] = "segundo (no debe pisar)"
        r2 = sc.registrar_verificado(c, req, env2)
        hash2 = r2["hashes"]["res_m415_idem"]["row_hash"]
        filas = c.execute("SELECT COUNT(*) FROM results WHERE result_id=?",
                          ("res_m415_idem",)).fetchone()[0]
        colisiones = c.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='collision' "
            "AND entity_id=?", ("res_m415_idem",)).fetchone()[0]
        valor = c.execute("SELECT value FROM results WHERE result_id=?",
                          ("res_m415_idem",)).fetchone()[0]
        checks["append_only_mismo_row_hash"] = bool(hash1) and hash1 == hash2
        checks["append_only_una_fila"] = filas == 1
        checks["append_only_valor_original"] = valor == "primero"
        checks["colision_registrada_en_audit"] = colisiones >= 1
        detalle["append_only"] = {"row_hash_1": hash1, "row_hash_2": hash2,
                                  "filas": filas, "colisiones": colisiones,
                                  "valor_final": valor}
        c.close()
    except Exception as exc:  # noqa: BLE001
        checks["append_only_mismo_row_hash"] = False
        detalle["append_only"] = "excepcion: %s" % exc

    # -- 3. el experimento repetido da el mismo digest ------------------
    try:
        if digest_a and digest_b:
            checks["experimento_mismo_digest"] = digest_a == digest_b
            detalle["digest"] = {"a": digest_a, "b": digest_b}
        elif digest_a and repetir is not None:
            nuevo = repetir()
            checks["experimento_mismo_digest"] = nuevo == digest_a
            detalle["digest"] = {"a": digest_a, "b": nuevo}
        else:
            checks["experimento_mismo_digest"] = None
    except Exception as exc:  # noqa: BLE001
        checks["experimento_mismo_digest"] = None
        detalle["digest"] = "excepcion: %s" % exc

    salida = _resumen(checks)
    salida["detalle"] = detalle
    salida["workdir"] = wd
    return salida


# --------------------------------------------------------------------------
# LAS_7_V3
# --------------------------------------------------------------------------
def _correcciones_declaradas() -> List[str]:
    from arquitectura import CORRECCIONES_V3
    return list(CORRECCIONES_V3)


def evaluar_las_7_v3(suite: str = SUITE_MUTACION, cwd: str = CWD_SUITE,
                     timeout: int = 900) -> Dict[str, Any]:
    """Ejecuta el suite de MUTACION y exige 7/7 con cobertura completa.

    No basta con que el suite pase: un suite puede pasar porque no prueba
    nada. Se exige ademas que las mutaciones declaradas cubran EXACTAMENTE las
    7 correcciones de `arquitectura.CORRECCIONES_V3`, y que el resumen diga
    `N/N discriminan` con rc=0. Si el suite no arranca, NOT_DETERMINED.
    """
    checks: Dict[str, Any] = {}
    detalle: Dict[str, Any] = {}
    try:
        declaradas = _correcciones_declaradas()
    except Exception as exc:  # noqa: BLE001
        return {"estado": NOT_DETERMINED, "checks": {},
                "detalle": {"error": str(exc)},
                "motivo": "no se pudo importar CORRECCIONES_V3: %s" % exc}
    checks["hay_7_correcciones"] = len(declaradas) == 7

    if not os.path.isfile(suite):
        checks["suite_ejecutado"] = None
        return {**_resumen(checks), "detalle": {"suite": suite},
                "motivo": "suite de mutacion ausente: %s" % suite}

    with open(suite, "r", encoding="utf-8", errors="ignore") as fh:
        fuente = fh.read()
    mutadas = sorted(set(re.findall(r'"(V3-\d_[A-Z0-9_]+)"', fuente)))
    checks["mutaciones_cubren_las_7"] = sorted(declaradas) == mutadas
    detalle["mutaciones_declaradas"] = mutadas

    try:
        p = subprocess.run([sys.executable, suite],
                           cwd=cwd, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        salida = p.stdout.decode(errors="ignore")
        m = re.search(r"RESUMEN:\s*(\d+)/(\d+)\s+correcciones discriminan", salida)
        checks["suite_ejecutado"] = True
        checks["suite_rc_cero"] = p.returncode == 0
        checks["resumen_7_de_7"] = bool(m) and m.group(1) == m.group(2) == "7"
        detalle.update({"rc": p.returncode,
                        "resumen": m.group(0) if m else None,
                        "stdout_tail": salida.strip().splitlines()[-4:],
                        "stderr_tail": p.stderr.decode(errors="ignore")[-300:]})
    except Exception as exc:  # noqa: BLE001
        checks["suite_ejecutado"] = None
        detalle["error"] = str(exc)

    salida_res = _resumen(checks)
    salida_res["detalle"] = detalle
    return salida_res


class EvaluadoresAlma:
    """Evaluadores listos para inyectar en `ALMA.Criterio.cumple`.

    Cachea por nombre: ALMA puede evaluar dos veces y no tiene sentido correr
    el suite de mutacion dos veces en la misma corrida.
    """

    def __init__(self, digest_a: Optional[str] = None,
                 digest_b: Optional[str] = None,
                 origen: str = DB_PROTEGIDA,
                 workdir: Optional[str] = None,
                 repetir: Optional[Callable[[], str]] = None):
        self.digest_a = digest_a
        self.digest_b = digest_b
        self.origen = origen
        self.workdir = workdir
        self.repetir = repetir
        self._cache: Dict[str, bool] = {}
        self._detalle: Dict[str, Any] = {}

    def idempotencia(self) -> bool:
        if "IDEMPOTENCIA" not in self._cache:
            r = evaluar_idempotencia(digest_a=self.digest_a,
                                     digest_b=self.digest_b,
                                     origen=self.origen,
                                     workdir=self.workdir,
                                     repetir=self.repetir)
            self._cache["IDEMPOTENCIA"] = r["estado"] == PROVEN
            self._detalle["IDEMPOTENCIA"] = r
        return self._cache["IDEMPOTENCIA"]

    def las_7_v3(self) -> bool:
        if "LAS_7_V3" not in self._cache:
            r = evaluar_las_7_v3()
            self._cache["LAS_7_V3"] = r["estado"] == PROVEN
            self._detalle["LAS_7_V3"] = r
        return self._cache["LAS_7_V3"]

    def criterios(self) -> Dict[str, Callable[[], bool]]:
        return {"IDEMPOTENCIA": self.idempotencia,
                "LAS_7_V3": self.las_7_v3}

    def detalle(self) -> Dict[str, Any]:
        return dict(self._detalle)
