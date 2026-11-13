#!/usr/bin/env python3
"""RXRE-221 — Puente entre evidencia verificada (220) y politica de conflictos (217-219).

Función PURA y reutilizable. No escribe, no depende de DB ni de machine.
No habilita integración operativa.

Reglas:
- Cada claim se evalúa de forma INDEPENDIENTE (evidencia -> verificador).
- La relación semántica entre las proposiciones se decide SEPARADAMENTE.
- Si la relación semántica no es demostrable con los datos, la
  clasificación final queda INDETERMINATE, aunque las evaluaciones
  individuales difieran (SUPPORTED vs REFUTED).
- La exclusividad mutua solo se reconoce en la clase acotada donde la
  verificación es de IGUALDAD EXACTA sobre el MISMO artefacto (hash) y la
  MISMA posición, con valores asertados distintos. Con semántica de
  subcadena la exclusividad no es demostrable (dos subcadenas distintas
  pueden ser ciertas a la vez) -> INDETERMINATE.
- Un resultado local (SUPPORTED/REFUTED) NO se promueve a afirmación universal.
"""
from typing import Dict, Any, Callable, Optional

EVALUACIONES = {"SUPPORTED", "REFUTED", "INSUFFICIENT"}


def evaluar_par_con_evidencia(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    evaluador: Callable[[Dict[str, Any]], Dict[str, Any]],
    politica: Optional[Callable[[Dict[str, Any], Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evalúa dos claims contra evidencia y clasifica su relación.

    `evaluador(claim) -> dict` debe devolver, como mínimo:
      {"resultado": "SUPPORTED"|"REFUTED"|"INSUFFICIENT", ...}
    (compatible con `rxre.contracts.evidence_claim_verification.
      verificar_propiedad_artefacto`).

    `politica` (opcional): callable(claim_a, claim_b, relaciones) -> dict con
    {"clasificacion": ..., "motivo": ..., ...}. Si se omite, se usa la
    clasificación local del puente (CONFLICT solo con exclusividad mutua
    demostrada; INDETERMINATE en cualquier otro caso).
    """
    # --- Verificación de datos mínimos ---
    for clave, claim in (("a", claim_a), ("b", claim_b)):
        if not isinstance(claim, dict):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "claim %s no es un dict; la semantica acotada requiere contrato de verificacion" % clave,
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["entrada no dict"],
            }
        verif = claim.get("verificacion")
        if not isinstance(verif, dict):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "claim %s sin verificacion como dict; contrato acotado requiere tipo, parametro y referencias" % clave,
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["contrato de verificacion incompleto"],
            }
        param = verif.get("parametro")
        if not isinstance(param, dict):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "parametro de verificacion no es dict en claim %s; no se puede evaluar" % clave,
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["parametro malformado"],
            }
        linea_esp = param.get("linea")
        if linea_esp is not None and not isinstance(linea_esp, int):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "linea debe ser entero en claim %s (%r); no se puede localizar posicion" % (clave, linea_esp),
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["linea no es entero"],
            }
        texto_esp = param.get("texto_esperado")
        if texto_esp is not None and (not isinstance(texto_esp, str) or texto_esp == ""):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "texto_esperado debe ser cadena no vacia en claim %s (%r)" % (clave, texto_esp),
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["texto_esperado malformado"],
            }
        refs_claim = claim.get("evidencia_refs")
        if not isinstance(refs_claim, (list, tuple)) or len(refs_claim) == 0:
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "claim %s no declara referencias de evidencia; sin procedencia declarada no se acredita nada" % clave,
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["sin referencias de evidencia declaradas"],
            }
        if any((not isinstance(r, str)) or (not r.strip()) for r in refs_claim):
            return {
                "clasificacion": "INDETERMINATE",
                "capa": "evidencia",
                "motivo": "referencias de evidencia malformadas en claim %s: %r" % (clave, list(refs_claim)),
                "evaluaciones": {"a": None, "b": None},
                "relacion_semantica": {"estado": "NO_EVALUADA"},
                "referencias_utilizadas": [],
                "limitaciones": ["referencias de evidencia malformadas"],
            }

    ev_a = evaluador(claim_a)
    ev_b = evaluador(claim_b)
    res_a = (ev_a or {}).get("resultado")
    res_b = (ev_b or {}).get("resultado")

    relaciones = {
        "evaluacion_a": res_a,
        "evaluacion_b": res_b,
        "hash_a": ((ev_a or {}).get("integridad_evidencia") or {}).get("hash_sha256"),
        "hash_b": ((ev_b or {}).get("integridad_evidencia") or {}).get("hash_sha256"),
        "semantica_a": (claim_a.get("verificacion") or {}).get("tipo"),
        "semantica_b": (claim_b.get("verificacion") or {}).get("tipo"),
        "linea_a": ((claim_a.get("verificacion") or {}).get("parametro") or {}).get("linea"),
        "linea_b": ((claim_b.get("verificacion") or {}).get("parametro") or {}).get("linea"),
        "valor_a": ((claim_a.get("verificacion") or {}).get("parametro") or {}).get("texto_esperado"),
        "valor_b": ((claim_b.get("verificacion") or {}).get("parametro") or {}).get("texto_esperado"),
        "scope_a": claim_a.get("scope"),
        "scope_b": claim_b.get("scope"),
    }

    # --- Capa 1: suficiencia de evidencia ---
    if res_a not in EVALUACIONES or res_b not in EVALUACIONES:
        return {
            "clasificacion": "INDETERMINATE",
            "capa": "evidencia",
            "motivo": "resultado de evaluación no recognised; no se puede clasificar",
            "evaluaciones": {"a": ev_a, "b": ev_b},
            "relacion_semantica": {"estado": "NO_EVALUADA", "detalle": relaciones},
            "referencias_utilizadas": _refs(ev_a) + _refs(ev_b),
            "limitaciones": ["resultado de evaluación inválido"],
        }
    if res_a == "INSUFFICIENT" or res_b == "INSUFFICIENT":
        return {
            "clasificacion": "INDETERMINATE",
            "capa": "evidencia",
            "motivo": "evidencia insuficiente en al menos uno de los claims (a=%s, b=%s); no se afirma contradicción" % (res_a, res_b),
            "evaluaciones": {"a": ev_a, "b": ev_b},
            "relacion_semantica": {"estado": "NO_EVALUADA", "detalle": relaciones},
            "referencias_utilizadas": _refs(ev_a) + _refs(ev_b),
            "limitaciones": ["evidencia insuficiente; ausencia de evidencia no es evidencia negativa"],
        }

    # --- Capa 2: relación semántica (independiente de las evaluaciones) ---
    relacion = _relacion_semantica(relaciones)
    if relacion["estado"] != "MUTUALLY_EXCLUSIVE":
        return {
            "clasificacion": "INDETERMINATE",
            "capa": "relacion_semantica",
            "motivo": "relación semántica no demostrable: %s; evaluaciones individuales (%s/%s) no autorizan una clasificación de contradicción" % (relacion["motivo"], res_a, res_b),
            "evaluaciones": {"a": ev_a, "b": ev_b},
            "relacion_semantica": relacion,
            "referencias_utilizadas": _refs(ev_a) + _refs(ev_b),
            "limitaciones": [
                "la semántica de las proposiciones no está definida en el esquema",
                "comparación textual NO es prueba de contradicción semántica",
            ],
        }

    # --- Capa 3: clasificación del par ---
    if politica is not None:
        clas = politica(claim_a, claim_b, {"relacion_semantica": relacion, "evaluaciones": {"a": ev_a, "b": ev_b}})
        clas.setdefault("capa", "clasificacion")
        clas.setdefault("evaluaciones", {"a": ev_a, "b": ev_b})
        clas.setdefault("relacion_semantica", relacion)
        clas.setdefault("referencias_utilizadas", _refs(ev_a) + _refs(ev_b))
        return clas

    return {
        "clasificacion": "CONFLICT",
        "capa": "clasificacion",
        "motivo": "exclusividad mutua demostrada en clase acotada: misma evidencia (hash), misma posición, semántica de igualdad exacta y valores asertados distintos; ambas evaluaciones con integridad verificada (%s/%s)" % (res_a, res_b),
        "evaluaciones": {"a": ev_a, "b": ev_b},
        "relacion_semantica": relacion,
        "referencias_utilizadas": _refs(ev_a) + _refs(ev_b),
        "limitaciones": [
            "clase acotada: aplicabilidad limitada a igualdad exacta sobre el mismo artefacto y posición",
            "no demuestra incompatibilidad semántica en general (proposiciones en lenguaje natural)",
        ],
    }


def _refs(ev: Optional[Dict[str, Any]]) -> list:
    if not ev:
        return []
    return list((ev.get("procedencia") or []) + (ev.get("referencias_faltantes") or []))


def _relacion_semantica(rel: Dict[str, Any]) -> Dict[str, Any]:
    """Determinar si la relación semántica es demostrable en clase acotada."""
    if rel["hash_a"] is None or rel["hash_b"] is None:
        return {"estado": "UNDEFINED", "motivo": "hash de evidencia no disponible en al menos una evaluación"}
    if rel["hash_a"] != rel["hash_b"]:
        return {"estado": "UNDEFINED", "motivo": "las evidencia apuntan a artefactos distintos (hash diferente); no hay base común para comparar"}
    if rel["scope_a"] != rel["scope_b"]:
        return {"estado": "UNDEFINED", "motivo": "alcances diferentes: las proposiciones no se refieren al mismo contexto"}
    if not rel["scope_a"] or not str(rel["scope_a"]).strip():
        return {"estado": "UNDEFINED", "motivo": "alcance sin valor definido; no se puede afirmar contradiccion sin contexto"}
    if rel["semantica_a"] != "linea_igual" or rel["semantica_b"] != "linea_igual":
        return {"estado": "UNDEFINED", "motivo": "semantica de verificacion no es igualdad exacta (p.ej. subcadena): la exclusividad mutua no es demostrable"}
    if rel["linea_a"] is None or rel["linea_a"] != rel["linea_b"]:
        return {"estado": "UNDEFINED", "motivo": "posiciones distintas: no se compara el mismo punto de observacion"}
    if rel["valor_a"] == rel["valor_b"]:
        return {"estado": "UNDEFINED", "motivo": "valores asertados identicos: no hay proposiciones en conflicto"}
    # Deteccion de verdad: una contradiccion ENTRE las afirmaciones exige que
    # exactamente una de ellas se sostenga sobre la evidencia observada.
    # - ambas REFUTED: ninguna se sostiene; el desacuerdo es de cada
    #   afirmacion con la evidencia, NO entre las afirmaciones -> no hay
    #   contradiccion entre el par.
    # - ambas SUPPORTED: incoherencia de la evaluacion (dos valores distintos
    #   no pueden ser la misma linea observada) -> no se clasifica.
    if rel["evaluacion_a"] == rel["evaluacion_b"]:
        if rel["evaluacion_a"] == "SUPPORTED":
            return {"estado": "UNDEFINED", "motivo": "ambas afirmaciones resultan SUPPORTED sobre el mismo punto de observacion: incoherencia de la evaluacion; no se clasifica"}
        return {"estado": "UNDEFINED", "motivo": "ambas afirmaciones resultan REFUTED: ninguna se sostiene sobre la evidencia; el desacuerdo es entre cada afirmacion y la evidencia, no entre las afirmaciones; no se declara contradiccion"}
    return {
        "estado": "MUTUALLY_EXCLUSIVE",
        "motivo": "mismo artefacto (hash %s), mismo alcance (%s), misma posicion (linea %s), semantica de igualdad exacta, valores asertados distintos y exactamente una afirmacion sostenida por la evidencia (%s/%s)" % (
            str(rel["hash_a"])[:16], rel["scope_a"], rel["linea_a"], rel["evaluacion_a"], rel["evaluacion_b"]),
        "criterios": ["mismo_hash_artefacto", "mismo_alcance", "misma_posicion", "igualdad_exacta", "valores_distintos", "exactamente_una_sostenida"],
    }
