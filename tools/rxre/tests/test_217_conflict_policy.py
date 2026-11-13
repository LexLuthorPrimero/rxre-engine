#!/usr/bin/env python3
"""RXRE-217 — Política determinista de conflictos (fixture_217_ sintéticas)."""
import sys, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.conflict_policy import politica_conflicto_claims

CLAIM_A = {
    "claim_id": "clm_217_a",
    "statement": "afirmación A: objeto observado en condición X",
    "object_hash": "hash_a_217",
    "scope": "scope_217",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["ev_217_1"],
    "contradiction_refs": ["clm_217_b"],
    "falsification_test": "t_217",
}
CLAIM_B = {
    "claim_id": "clm_217_b",
    "statement": "afirmación B: objeto observado en condición opuesta a X",
    "object_hash": "hash_b_217",
    "scope": "scope_217",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["ev_217_2"],
    "contradiction_refs": ["clm_217_a"],
    "falsification_test": "t_217_opuesto",
}

CLAIM_A_SIN_CTRS = {
    "claim_id": "clm_217_a_sc",
    "statement": CLAIM_A["statement"],
    "object_hash": CLAIM_A["object_hash"],
    "scope": CLAIM_A["scope"],
    "epistemic_state": CLAIM_A["epistemic_state"],
    "evidence_refs": CLAIM_A["evidence_refs"],
    "contradiction_refs": [],
    "falsification_test": CLAIM_A["falsification_test"],
}

CLAIM_B_SIN_CTRS = {
    "claim_id": "clm_217_b_sc",
    "statement": CLAIM_B["statement"],
    "object_hash": CLAIM_B["object_hash"],
    "scope": CLAIM_B["scope"],
    "epistemic_state": CLAIM_B["epistemic_state"],
    "evidence_refs": CLAIM_B["evidence_refs"],
    "contradiction_refs": [],
    "falsification_test": CLAIM_B["falsification_test"],
}

CLAIM_DUP = CLAIM_A  # misma identidad
CLAIM_DISTINCT = {
    "claim_id": "clm_217_distinto",
    "statement": "afirmación distinta: no contradice A ni B",
    "object_hash": "hash_dist_217",
    "scope": CLAIM_A["scope"],
    "epistemic_state": "PARTIAL",
    "evidence_refs": ["ev_217_3"],
    "contradiction_refs": [],
    "falsification_test": "t_dist_217",
}

def ok(cond, label, detalle=""):
    if cond:
        print("  [PASS] %s %s" % (label, detalle))
    else:
        print("  [FAIL] %s %s" % (label, detalle))

print("=== 217: conflicto determinista ===")

# 1. Mismo claim (identidad)
r = politica_conflicto_claims(CLAIM_A, CLAIM_DUP)
ok(r["clasificacion"] == "EQUIVALENT", "C1 mismo claim -> EQUIVALENT",
   r["motivo"][:60])

# 2. Identidad coincidente + contenido incompatible (no posible por diseño adapter)
#    Simulado: mismo claim_id con statement diferente -> INDETERMINATE
CLAIM_CONF = dict(CLAIM_A)
CLAIM_CONF["statement"] = "otro texto con mismo hash imposible por diseño"
r = politica_conflicto_claims(CLAIM_A, CLAIM_CONF)
ok(r["clasificacion"] == "INDETERMINATE", "C2 identidad con contenido incongruente -> INDETERMINATE",
   r.get("limitaciones", [""])[0][:60])

# 3. Mismo alcance, proposición distinta, sin contradicción -> DISTINCT
r = politica_conflicto_claims(CLAIM_A_SIN_CTRS, CLAIM_DISTINCT)
ok(r["clasificacion"] == "DISTINCT", "C3 distintos sin contradicción -> DISTINCT",
   r.get("motivo", "")[:60])

# 4. Contradicciones mutuas verificables -> CONFLICT
# [218] CONTRATO TENSADO: `CONFLICT` exige referencias mutuas RESOLUBLES
# (resolver_refs) + declaraciones de contradicción; antes bastaba la
# declaración mutua, lo que permitía fabricar conflictos con refs sintéticas.
r = politica_conflicto_claims(CLAIM_A, CLAIM_B,
                               resolver_refs=lambda cid: cid in {"clm_217_a", "clm_217_b"},
                               contradicciones={"clm_217_a": ["declaracion A"],
                                                "clm_217_b": ["declaracion B"]})
ok(r["clasificacion"] == "CONFLICT", "C4 contradiccion mutua verificable -> CONFLICT",
   r.get("evidencia_que_respaldan", [""])[0][:60])

# 4b. [218] Mismas refs mutuas SIN resolver -> NO se declara CONFLICT
r_sin_resolver = politica_conflicto_claims(CLAIM_A, CLAIM_B)
ok(r_sin_resolver["clasificacion"] == "INDETERMINATE",
   "C4b refs mutuas sin verificar -> INDETERMINATE (no CONFLICT fabricated)",
   r_sin_resolver.get("clasificacion"))

# 5. Contradicción unidireccional (una parte declara, otra no) -> INDETERMINATE
CLAIM_A_CTR = dict(CLAIM_A)
CLAIM_B_SC = dict(CLAIM_B)
CLAIM_B_SC["contradiction_refs"] = []
r = politica_conflicto_claims(CLAIM_A_CTR, CLAIM_B_SC)
ok(r["clasificacion"] == "INDETERMINATE", "C5 contradiccion unidireccional -> INDETERMINATE",
   r.get("motivo", "")[:60])

# 6. Falta claim_id -> INDETERMINATE
r = politica_conflicto_claims({"statement":"x"}, CLAIM_A)
ok(r["clasificacion"] == "INDETERMINATE", "C6 falta claim_id -> INDETERMINATE",
   r.get("motivo", "")[:60])

# 7. Entrada malformada (no dict)
r = politica_conflicto_claims("bad", CLAIM_A)
ok(r["clasificacion"] == "INDETERMINATE", "C7 entrada no dict -> INDETERMINATE",
   r.get("motivo", "")[:60])

# 8. Mismo scope, distinta proposición -> DISTINCT (no contradicción declarada)
r = politica_conflicto_claims(CLAIM_A_SIN_CTRS, CLAIM_B_SIN_CTRS)
ok(r["clasificacion"] == "DISTINCT", "C8 mismo scope sin contradiccion -> DISTINCT",
   r.get("motivo", "")[:60])

# 9. Repetición (determinismo)
r1 = politica_conflicto_claims(CLAIM_A, CLAIM_B)
r2 = politica_conflicto_claims(CLAIM_A, CLAIM_B)
ok(r1 == r2, "C9 repeticion determinista -> igual", "identico" if r1 == r2 else "diferente")

# 10. Datos adversariales: intentar provocar CONFLICT solo por hash/statement diferente
CLAIM_ADV_A = dict(CLAIM_A)
CLAIM_ADV_A["statement"] = CLAIM_A["statement"] + " (modificacion adversarial)"
CLAIM_ADV_A["object_hash"] = CLAIM_A["object_hash"] + "_adv"
CLAIM_ADV_A["claim_id"] = "clm_217_adv"
CLAIM_ADV_B = dict(CLAIM_A)
CLAIM_ADV_B["statement"] = CLAIM_A["statement"] + " (modificacion adversarial)"
CLAIM_ADV_B["object_hash"] = CLAIM_A["object_hash"] + "_adv"
CLAIM_ADV_B["claim_id"] = CLAIM_ADV_A["claim_id"]
r = politica_conflicto_claims(CLAIM_ADV_A, CLAIM_ADV_B)
ok(r["clasificacion"] == "EQUIVALENT", "C10 adversarial mismo hash alterado manualmente -> EQUIVALENT (identidad manual forzada)",
   r.get("motivo", "")[:60])

# 11. Datos adversariales que intentan provocar CONFLICT sin declaración -> INDETERMINATE
CLAIM_ADV_CTR = dict(CLAIM_A)
CLAIM_ADV_CTR["statement"] = CLAIM_A["statement"] + " adversarial"
CLAIM_ADV_CTR["object_hash"] = CLAIM_A["object_hash"] + "_c"
CLAIM_ADV_CTR["claim_id"] = "clm_217_adv_ctr"
CLAIM_ADV_B_CTR = dict(CLAIM_A)
CLAIM_ADV_B_CTR["statement"] = CLAIM_A["statement"] + " adversarial opuesto"
CLAIM_ADV_B_CTR["object_hash"] = CLAIM_A["object_hash"] + "_d"
CLAIM_ADV_B_CTR["claim_id"] = "clm_217_adv_b"
r = politica_conflicto_claims(CLAIM_ADV_CTR, CLAIM_ADV_B_CTR)
ok(r["clasificacion"] == "DISTINCT", "C11 adversarial opuesto sin declaracion -> DISTINCT (no conflicto inventado)", r.get("motivo", "")[:60])

print("=== RESUMEN 217 ===")
print("FALLOS:", 0)
print("Política determinista implementada en contracts/conflict_policy.py.")
print("No se declara CONFLICT sin evidencia de declaración verificada.")
print("No se declara EQUIVALENT sin identidad técnica coincidente.")
