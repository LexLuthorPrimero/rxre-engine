#!/usr/bin/env python3
"""RXRE-221 — Puente evidencia verificada -> politica de conflictos.

Fixtures sinteticas `fixture_221_`; evidencia REAL ya capturada
(audit/strace/glxinfo_trace_20261019_005110.txt, ref res_real_001).
"""
import sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia

ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def evaluador_real(claim):
    """Evaluador independiente por claim (reutiliza verificador de 220)."""
    return verificar_propiedad_artefacto(
        ART,
        claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

LINEA_REAL = '3284613 access("/dev/dri/renderD128", F_OK) = 0'

CLAIM_A = {
    "claim_id": "fixture_221_claim_a",
    "scope": "runtime",
    "statement": "la traza muestra access(\"/dev/dri/renderD128\", F_OK) = 0",
    "object_hash": "fixture_221_obj",
    "verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": LINEA_REAL}},
    "evidencia_refs": ["res_real_001"],
}
CLAIM_B = {
    "claim_id": "fixture_221_claim_b",
    "scope": "runtime",
    "statement": "la traza muestra openat(\"/dev/dri/renderD128\", O_RDONLY) = 3 en la misma posicion",
    "object_hash": "fixture_221_obj",
    "verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": '3284613 openat("/dev/dri/renderD128", O_RDONLY) = 3'}},
    "evidencia_refs": ["res_real_001"],
}

print("=== 221: puente evidencia -> politica de conflictos ===")

# 1. Evaluaciones independientes: SUPPORTED / REFUTED sobre la misma evidencia real
ev_a = evaluador_real(CLAIM_A)
ev_b = evaluador_real(CLAIM_B)
ok(ev_a["resultado"] == "SUPPORTED", "C1 evaluacion A -> SUPPORTED", ev_a["resultado"])
ok(ev_b["resultado"] == "REFUTED", "C2 evaluacion B -> REFUTED", ev_b["resultado"])

# 2. Puente con relacion semantica demostrable (mismo hash, mismo alcance, misma posicion, igualdad exacta)
res = evaluar_par_con_evidencia(CLAIM_A, CLAIM_B, evaluador_real)
ok(res["clasificacion"] == "CONFLICT", "C3 exclusividad mutua exacta -> CONFLICT", res["clasificacion"])
ok(res["capa"] == "clasificacion", "C3 capa = clasificacion", res["capa"])
ok(res["relacion_semantica"]["estado"] == "MUTUALLY_EXCLUSIVE", "C3 relacion semantica demostrada")
ok("res_real_001" in res["referencias_utilizadas"], "C3 referencias conservadas", str(res["referencias_utilizadas"]))

# 3. Semantica de subcadena: la exclusividad NO es demostrable -> INDETERMINATE
CLAIM_A_SUB = dict(CLAIM_A, verificacion={"tipo": "linea_contiene", "parametro": {"linea": 396, "texto_esperado": 'access("/dev/dri/renderD128", F_OK) = 0'}})
CLAIM_B_SUB = dict(CLAIM_B, verificacion={"tipo": "linea_contiene", "parametro": {"linea": 396, "texto_esperado": 'F_OK) = 0'}})
res = evaluar_par_con_evidencia(CLAIM_A_SUB, CLAIM_B_SUB, evaluador_real)
ok(res["clasificacion"] == "INDETERMINATE", "C4 subcadena -> INDETERMINATE (no exclusividad inventada)", res["clasificacion"])
ok(res["capa"] == "relacion_semantica", "C4 capa = relacion_semantica", res["capa"])

# 4. Alcances distintos: mismo texto, distinto alcance -> INDETERMINATE
CLAIM_B_OTRO_SCOPE = dict(CLAIM_B, scope="boot")
res = evaluar_par_con_evidencia(CLAIM_A, CLAIM_B_OTRO_SCOPE, evaluador_real)
ok(res["clasificacion"] == "INDETERMINATE", "C5 distinto alcance -> INDETERMINATE", res["clasificacion"])

# 5. Artefactos distintos (hash distinto) -> INDETERMINATE
CLAIM_B_OTRO_ART = dict(CLAIM_B, verificacion={"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": LINEA_REAL}})
def evaluador_otro_artefacto(claim):
    if claim.get("claim_id") == "fixture_221_claim_b":
        r = verificar_propiedad_artefacto("/tmp/rxre_221_otro_artefacto.sqlite3", claim.get("verificacion"),
                                          evidencia_refs=["res_real_001"], resolver_refs=lambda cid: cid == "res_real_001")
        return r
    return evaluador_real(claim)
res = evaluar_par_con_evidencia(CLAIM_A, CLAIM_B_OTRO_ART, evaluador_otro_artefacto)
ok(res["clasificacion"] == "INDETERMINATE", "C6 evidencia insuficiente (artefacto otro) -> INDETERMINATE", res["clasificacion"])
ok(res["capa"] == "evidencia", "C6 capa = evidencia", res["capa"])

# 6. Referencia inexistente -> INSUFFICIENT en evaluacion -> INDETERMINATE
CLAIM_SIN_REF = dict(CLAIM_A, evidencia_refs=["res_ficticio_221"])
res = evaluar_par_con_evidencia(CLAIM_SIN_REF, CLAIM_B, evaluador_real)
ok(res["clasificacion"] == "INDETERMINATE", "C7 referencia inexistente -> INDETERMINATE", res["clasificacion"])

# 7. Declaraciones mutuas sin respaldo de evidencia NO pueden fabricar CONFLICT
#    (la politica 218 exige resolver_refs + contradicciones; el puente exige evidencia)
from rxre.contracts.conflict_policy import politica_conflicto_claims
CLAIM_FABRICADO_A = dict(CLAIM_A, contradiction_refs=["fixture_221_claim_b"], contradiction_statements=["declaracion inventada"])
CLAIM_FABRICADO_B = dict(CLAIM_B, contradiction_refs=["fixture_221_claim_a"], contradiction_statements=["declaracion inventada"])
res = evaluar_par_con_evidencia(CLAIM_FABRICADO_A, CLAIM_FABRICADO_B, evaluador_real)
ok(res["clasificacion"] != "CONFLICT" or res["relacion_semantica"]["estado"] == "MUTUALLY_EXCLUSIVE",
   "C8 declaracion mutua sola no fabrica CONFLICT (exige relacion semantica demostrada)", res["clasificacion"])

# 8. Determinismo
r1 = evaluar_par_con_evidencia(CLAIM_A, CLAIM_B, evaluador_real)
r2 = evaluar_par_con_evidencia(CLAIM_A, CLAIM_B, evaluador_real)
ok(r1 == r2, "C9 determinismo (misma entrada -> mismo resultado)")

# 9. Entrada malformada
res = evaluar_par_con_evidencia({}, {}, evaluador_real)
ok(res["clasificacion"] == "INDETERMINATE", "C10 entrada malformada -> INDETERMINATE", res["clasificacion"])

# 10. Politica 218 sigue exigiendo evidencia verificable (no se debilitó)
r_pol = politica_conflicto_claims(CLAIM_FABRICADO_A, CLAIM_FABRICADO_B,
                                   resolver_refs=lambda cid: False, contradicciones=None)
ok(r_pol["clasificacion"] == "INDETERMINATE", "C11 politica 218 sin resolver -> INDETERMINATE (no CONFLICT)", r_pol["clasificacion"])

print("\n=== RESUMEN 221 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("221 OK")
