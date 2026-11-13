#!/usr/bin/env python3
"""Composicion segura de verificaciones de propiedades observacionales.

Regla de composicion (conjuncion acotada):
- Las evaluaciones deben ser comparables: mismo hash (mismo artefacto), mismo alcance,
  resultados bien formados.
- Si alguna es INSUFFICIENT -> INSUFFICIENT (no se puede afirmar el compuesto).
- Si al menos una es REFUTED -> REFUTED (una componente falsa invalida la conjuncion).
- Solo si TODAS son SUPPORTED -> SUPPORTED.
- NUNCA se emite CONFLICT; la contradiccion semantica pertenece al puente (221/222),
  no a la composicion.

No escribe DB ni modifica zonas protegidas.
"""
from typing import List, Optional, Dict, Any

RESULTADOS_VALIDOS = {"SUPPORTED", "REFUTED", "INSUFFICIENT"}


def componer_verificaciones(
    evaluaciones: List[Dict[str, Any]],
    alcances: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Componer evaluaciones independientes de un mismo artefacto.

    `evaluaciones`: lista de dicts con, como minimo:
      - resultado: SUPPORTED | REFUTED | INSUFFICIENT
      - integridad_evidencia: dict con hash_sha256 (opcional, pero usado para comparabilidad)
    `alcances`: lista paralela de strings no vacios (opcional; si falta, se asume
      que el contexto no esta definido y la comparabilidad de alcance es INDETERMINATE).
    """
    # --- Validacion de forma ---
    if not isinstance(evaluaciones, (list, tuple)) or len(evaluaciones) == 0:
        return {
            "estado_compuesto": "INDETERMINATE",
            "motivo": "lista de evaluaciones vacia o no lista; no hay componente para componer",
            "resultados_individuales": {},
            "comparabilidad": False,
            "referencias_utilizadas": [],
            "limitaciones": ["sin evaluaciones de entrada"],
        }
    if alcances is not None and len(alcances) != len(evaluaciones):
        return {
            "estado_compuesto": "INDETERMINATE",
            "motivo": "alcances (%d) no coinciden con evaluaciones (%d); no se puede componer" % (len(alcances), len(evaluaciones)),
            "resultados_individuales": {},
            "comparabilidad": False,
            "referencias_utilizadas": [],
            "limitaciones": ["alcances y evaluaciones desalineados"],
        }

    resultados_individuales = {}
    referencias_utilizadas = []
    hashes = []
    alcances_efectivos = alcances or [None] * len(evaluaciones)
    malformadas = []

    for i, (ev, alcance) in enumerate(zip(evaluaciones, alcances_efectivos)):
        clave = "ev_%d" % i
        if not isinstance(ev, dict):
            malformadas.append(clave)
            resultados_individuales[clave] = {"resultado": "INSUFFICIENT", "motivo": "entrada no dict"}
            continue
        res = ev.get("resultado")
        if res not in RESULTADOS_VALIDOS:
            malformadas.append(clave)
            resultados_individuales[clave] = {
                "resultado": "INSUFFICIENT",
                "motivo": "resultado '%s' no reconocido; debe ser SUPPORTED/REFUTED/INSUFFICIENT" % (str(res)[:30]),
            }
            continue
        _motivos = [m for m in [ev.get("motivo", "")] if m]
        _faltantes = ev.get("referencias_faltantes", [])
        if _faltantes:
            _motivos.append("referencia(s) no resoluble(s): %s" % ", ".join(str(x) for x in _faltantes))
        resultados_individuales[clave] = {
            "resultado": res,
            "motivo": ev.get("motivo", ""),
            "motivos": _motivos,
            "propiedad": (ev.get("contenido_verificado") or {}).get("tipo_verificacion"),
            "hash_sha256": (ev.get("integridad_evidencia") or {}).get("hash_sha256"),
        }
        integridad = (ev.get("integridad_evidencia") or {})
        h = integridad.get("hash_sha256")
        hashes.append(h)
        referencias_utilizadas.extend(ev.get("procedencia", []))
        referencias_utilizadas.extend(ev.get("referencias_faltantes", []))

    if malformadas:
        return {
            "estado_compuesto": "INDETERMINATE",
            "motivo": "entradas malformadas en posiciones %s; no se puede componer" % ", ".join(malformadas),
            "resultados_individuales": resultados_individuales,
            "comparabilidad": False,
            "referencias_utilizadas": referencias_utilizadas,
            "limitaciones": ["entrada malformada impide composicion determinista"],
        }

    # --- Comparabilidad: artefacto (hash) y alcance ---
    hashes_no_nulos = [h for h in hashes if h is not None]
    hash_ausente = len(hashes_no_nulos) < len(hashes)
    # Si no hay hashes conocidos (todas las componentes INSUFFICIENT sin
    # integridad acreditada) y los alcances coinciden, la comparabilidad del
    # artefacto no es determinable en detalle, pero el contexto compartido
    # permite clasificar la evidencia como insuficiente (no como indeterminado
    # por contexto distinto).
    comparabilidad_hash = True
    if hashes_no_nulos:
        comparabilidad_hash = len({str(h) for h in hashes_no_nulos}) == 1
    else:
        # Ninguna integridad acreditada: se acepta comparabilidad solo para
        # no confundir ausencia de evidencia con incompatibilidad de contexto.
        comparabilidad_hash = True

    comparabilidad_alcance = (alcances is not None) and (len({str(a) for a in alcances_efectivos}) == 1) and all(str(a).strip() for a in alcances_efectivos if a is not None)
    # Si no se definieron alcances, la comparabilidad de alcance es False -> INDETERMINATE
    comparabilidad = comparabilidad_hash and (comparabilidad_alcance if alcances is not None else False)

    # --- Regla de composicion (conjuncion acotada) ---
    resultados = list(resultados_individuales.values())
    resultados_str = [r.get("resultado") for r in resultados]
    tiene_insuf = any(r == "INSUFFICIENT" for r in resultados_str)
    tiene_refutado = any(r == "REFUTED" for r in resultados_str)
    todos_sostenidos = all(r == "SUPPORTED" for r in resultados_str)

    # Lógica de verdad (mision 226): una conjuncion con componente REFUTED es
    # falsa (no oculta la refutacion con evidencia insuficiente). Una componente
    # INSUFFICIENT solo produce INSUFFICIENT si no hay refutacion verificada.
    if not comparabilidad:
        return {
            "estado_compuesto": "INDETERMINATE",
            "motivo": "evaluaciones no comparables (hash=%s; alcances=%s)" % ("coincide" if comparabilidad_hash else ("distinto" if (hashes_no_nulos and len({str(h) for h in hashes_no_nulos}) > 1) else "absente/incompleto"), "coincide" if (comparabilidad_alcance if alcances is not None else False) else "no definido/distinto"),
            "resultados_individuales": resultados_individuales,
            "comparabilidad": False,
            "hash_comun": str(hashes_no_nulos[0]) if (hashes_no_nulos and comparabilidad_hash) else None,
            "alcance_comun": str(alcances_efectivos[0]) if alcances_efectivos else None,
            "referencias_utilizadas": list({str(r) for r in referencias_utilizadas if r}),
            "limitaciones": ["composicion requiere mismo artefacto (hash) y mismo alcance; no generaliza relaciones semanticas sin definicion"],
        }
    if tiene_refutado:
        refutadas = [k for k, v in resultados_individuales.items() if v.get("resultado") == "REFUTED"]
        return {
            "estado_compuesto": "REFUTED",
            "motivo": "componente(s) refutada(s) %s sobre el mismo artefacto (%s) y alcance (%s)" % (", ".join(refutadas), str(hashes_no_nulos[0])[:16] if hashes_no_nulos else "?", str(alcances_efectivos[0]) if alcances_efectivos else "?"),
            "resultados_individuales": resultados_individuales, "comparabilidad": True,
            "hash_comun": str(hashes_no_nulos[0]) if hashes_no_nulos else None,
            "alcance_comun": str(alcances_efectivos[0]) if alcances_efectivos else None,
            "referencias_utilizadas": list({str(r) for r in referencias_utilizadas if r}),
            "limitaciones": ["la refutacion de un conyuncto refuta la conjuncion (logica de verdad); no contradiccion entre claims"],
        }
    if tiene_insuf:
        detalles_insuf = []
        for clave, detalle in resultados_individuales.items():
            if detalle.get("resultado") == "INSUFFICIENT":
                detalles_insuf.append("%s (%s)" % (clave, "; ".join(detalle.get("motivos", [])) if detalle.get("motivos") else "sin motivo"))
        return {
            "estado_compuesto": "INSUFFICIENT",
            "motivo": "componente(s) con evidencia insuficiente: %s" % ", ".join(detalles_insuf),
            "resultados_individuales": resultados_individuales, "comparabilidad": True,
            "hash_comun": str(hashes_no_nulos[0]) if hashes_no_nulos else None,
            "alcance_comun": str(alcances_efectivos[0]) if alcances_efectivos else None,
            "referencias_utilizadas": list({str(r) for r in referencias_utilizadas if r}),
            "limitaciones": [
                "evidencia insuficiente impide la composicion (conjuncion); ninguna refutacion verificable demuestra falsedad",
                "hash no determinable en componentes insuficientes: la integridad no esta acreditada"],
        }
    return {
        "estado_compuesto": "SUPPORTED",
        "motivo": "todas las propiedades verificadas (conjuncion) sobre el mismo artefacto (%s) y alcance (%s)" % (str(hashes_no_nulos[0])[:16] if hashes_no_nulos else "?", str(alcances_efectivos[0]) if alcances_efectivos else "?"),
        "resultados_individuales": resultados_individuales, "comparabilidad": True,
        "hash_comun": str(hashes_no_nulos[0]) if hashes_no_nulos else None,
        "alcance_comun": str(alcances_efectivos[0]) if alcances_efectivos else None,
        "referencias_utilizadas": list({str(r) for r in referencias_utilizadas if r}),
        "limitaciones": ["composicion acotada: conjuncion de propiedades verificadas; no generaliza a relaciones universales"],
    }
