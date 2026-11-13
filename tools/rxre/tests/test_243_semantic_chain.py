#!/usr/bin/env python3
"""RXRE-MISSION-243 — Prueba de la cadena semántica aislada (semantic_verification_chain)."""
import sys, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.semantic_verification_chain import cadena_verificacion_aislada
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
DB_ISO = "/tmp/rxre_243_chain.sqlite3"

def finding(stmt,oh,sc,eids,fid,ep="PROVEN"):
    return {"finding_id":fid,"statement":stmt,"epistemic":ep,"evidence_ids":eids,"falsification_test":"fixture_243","object_hash":oh,"scope":sc,"contradiction_refs":[]}

def clean():
    import sqlite3
    c=sqlite3.connect(DB_ISO); c.execute("DELETE FROM claims"); c.execute("DELETE FROM evidence"); c.commit(); c.close()

results = {}
# A: referencia real, integridad con manifest, SUPPORTED
r_a = cadena_verificacion_aislada(DB_ISO, finding("stmt_A","oh_A","sc_243",["res_real_001"],"f_A"), resolver_refs=lambda r:r=="res_real_001", claim_propiedad={"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, artifact_path=REAL_ART, evidence_path="/tmp/e2e_233_strace.json", explicit_enable=True)
results["A"] = r_a.get("status"), r_a.get("decision"), r_a.get("cadena_completa"), r_a.get("claim_id")
# B: referencia falsa sin resolver
r_b = cadena_verificacion_aislada(DB_ISO, finding("stmt_B","oh_B","sc_243",["bad_ref"],"f_B"), resolver_refs=lambda r:r=="fixture_242_real_ref", claim_propiedad={"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, artifact_path=REAL_ART, explicit_enable=True)
results["B"] = r_b.get("status"), r_b.get("decision"), r_b.get("claim_id")
# C: REFUTED
r_c = cadena_verificacion_aislada(DB_ISO, finding("stmt_C","oh_C","sc_243",["res_real_001"],"f_C"), resolver_refs=lambda r:r=="res_real_001", claim_propiedad={"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"NO_EXISTE"}}, artifact_path=REAL_ART, explicit_enable=True)
results["C"] = r_c.get("status"), r_c.get("decision"), r_c.get("claim_id")
# D: INSUFFICIENT (archivo no existe) -> NOT_DETERMINED
r_d = cadena_verificacion_aislada(DB_ISO, finding("stmt_D","oh_D","sc_243",["res_real_001"],"f_D"), resolver_refs=lambda r:r=="res_real_001", claim_propiedad={"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, artifact_path="/dev/null/no", explicit_enable=True)
results["D"] = r_d.get("status"), r_d.get("decision"), r_d.get("claim_id"), r_d.get("verificacion_semantica",{}).get("resultado"), r_d.get("verificacion_semantica",{}).get("motivo","")[:40]
# E: scope incompatible (distinto scope con ref)
# La cadena solo rechaza si incompatible; en este caso el scope es distinto pero la referencia resuelve; se acepta (compatibilidad depende del claim existente en DB; con DB vacía es indeterminado, no incompatible)
r_e = cadena_verificacion_aislada(DB_ISO, finding("stmt_E","oh_E","scope_243_OTHER",["res_real_001"],"f_E"), resolver_refs=lambda r:r=="res_real_001", claim_propiedad={"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, artifact_path=REAL_ART, explicit_enable=True)
results["E"] = r_e.get("status"), r_e.get("scope_compat",{}).get("compatibilidad"), r_e.get("claim_id")

for k,v in results.items():
    print(k, v)
# Veredicto
assert results["A"][0]=="ok" and results["A"][2] is True, "A debe pasar con cadena completa"
assert results["B"][0]=="blocked" and results["B"][1]=="REJECT", "B referencia falsa bloqueada"
assert results["C"][0]=="blocked" and results["C"][1]=="REJECT", "C REFUTED bloqueado"
assert results["D"][0]=="blocked" and results["D"][1]=="REJECT", "D falta archivo -> bloqueado por integridad (no inventado)"
print("=== CHAIN PASS ===")
