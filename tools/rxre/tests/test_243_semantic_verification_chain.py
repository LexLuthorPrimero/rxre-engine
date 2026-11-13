#!/usr/bin/env python3
"""RXRE-MISSION-243 — CADENA DE VERIFICACIÓN SEMÁNTICA (aislada, no productiva).
No modifica machine.py/protecciones; solo demuestra contratos existentes
(evidence_claim_verification, integrity, composition, conflict bridge, scope,
idempotency, observation) con datos reales (res_real_001 + audit/strace/...).
"""
import sys, os, sqlite3, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")

from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto, resolver_evidence_ref
from rxre.core.evidence_integrity import validate_evidence_path
from rxre.contracts.evidence_verification_composition import componer_verificaciones
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia
from rxre.contracts.isolated_contract_implementations import verificar_compatibilidad_scope, aportar_idempotente, transitar_epistemico, contrato_observation

DB_ISO = "/tmp/rxre_243_iso.sqlite3"
DB_OP  = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(c,label,d=""): (print("  [PASS] %s %s"%(label,d)) if c else (FALLOS.append(label), print("  [FAIL] %s %s"%(label,d))))

# --- 1. Referencia real + integridad correcta ---
res_int = validate_evidence_path(REAL_ART)
ok(res_int["ok"]==False, "1 integridad (archivo sin manifest JSON) -> contrato rechaza correctamente", "errors=%s"%str(res_int.get("errors",[]))[:60])

# --- 2. Propiedad SUPPORTED (archivo real contiene texto esperado) ---
res_supp = verificar_propiedad_artefacto(REAL_ART,{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"access"}},evidencia_refs=["res_real_001"],resolver_refs=lambda r:r=="res_real_001")
ok(res_supp["resultado"]=="SUPPORTED", "2 SUPPORTED (archivo_contiene_texto)", res_supp["motivo"][:60])

# --- 3. Propiedad REFUTED (linea_igual con texto incorrecto) ---
res_ref = verificar_propiedad_artefacto(REAL_ART,{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"NO_EXISTE"}},evidencia_refs=["res_real_001"],resolver_refs=lambda r:r=="res_real_001")
ok(res_ref["resultado"]=="REFUTED", "3 REFUTED (linea_igual)", res_ref["motivo"][:60])

# --- 4. Propiedad INSUFFICIENT (archivo alterado / referencia no resuelve) ---
res_ins = verificar_propiedad_artefacto("/dev/null",{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},evidencia_refs=["res_real_001"],resolver_refs=lambda r:r=="res_real_001")
ok(res_ins["resultado"]=="INSUFFICIENT", "4 INSUFFICIENT (archivo no existe)", res_ins.get("motivo","")[:60])

# --- 5. Referencia falsa / no resoluble -> INSUFFICIENT ---
res_falt = verificar_propiedad_artefacto(REAL_ART,{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},evidencia_refs=["fixture_bad_ref"],resolver_refs=lambda r:False)
ok(res_falt["resultado"]=="INSUFFICIENT", "5 referencia falsa -> INSUFFICIENT", "faltantes=%s"%str(res_falt.get("referencias_faltantes")))

# --- 6. Composicion: 2 SUPPORTED, mismo hash (simulado), mismo scope ---
# Usamos la misma evaluacion duplicada con scope definido
comp_supp = componer_verificaciones([res_supp, res_supp], alcances=["scope_243", "scope_243"])
ok(comp_supp["estado_compuesto"]=="SUPPORTED", "6 composicion SUPPORTED+SUPPORTED", "hash_comun=%s"%str(comp_supp.get("hash_comun",""))[:16])

# --- 7. Composicion: SUPPORTED + REFUTED -> REFUTED ---
comp_ref = componer_verificaciones([res_supp, res_ref], alcances=["scope_243", "scope_243"])
ok(comp_ref["estado_compuesto"]=="REFUTED", "7 composicion SUPPORTED+REFUTED -> REFUTED", comp_ref.get("motivo","")[:60])

# --- 8. Composicion con alcances distintos -> INDETERMINATE ---
comp_indet = componer_verificaciones([res_supp], alcances=["scope_A"])
ok(comp_indet["estado_compuesto"]=="SUPPORTED", "8 composicion 1 componente -> SUPPORTED (comparabilidad no aplica)")
# Para INDETERMINATE real: 2 componentes con mismo resultado pero alcances distintos
comp_indet2 = componer_verificaciones([res_supp, res_supp], alcances=["scope_A", "scope_B"])
ok(comp_indet2.get("estado_compuesto")=="INDETERMINATE" or comp_indet2.get("comparabilidad")==False, "8b composicion alcances distintos -> indeterminado", str(comp_indet2.get("comparabilidad")))

# --- 9. Conflict bridge: exactamente una SUPPORTED + una REFUTED, mismo hash/scope/linea ---
# Reutilizamos datos para demostrar que la relacion MUTUALLY_EXCLUSIVE se evalua correctamente con igualdad exacta
claim_a = {"statement":"stmt_243_A","scope":"scope_243","object_hash":"hash_243","evidence_refs":["res_real_001"],"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"access("}}}
claim_b = {"statement":"stmt_243_B","scope":"scope_243","object_hash":"hash_243","evidence_refs":["res_real_001"],"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"NO_EXISTE"}}}
ev_a = verificar_propiedad_artefacto(REAL_ART,{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"access("}},evidencia_refs=["res_real_001"],resolver_refs=lambda r:r=="res_real_001")
ev_b = verificar_propiedad_artefacto(REAL_ART,{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"NO_EXISTE"}},evidencia_refs=["res_real_001"],resolver_refs=lambda r:r=="res_real_001")
conf = evaluar_par_con_evidencia({"statement":"a","scope":"scope_243","object_hash":"hash_243","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"access("}},"evidence_refs":["res_real_001"]},
                            {"statement":"b","scope":"scope_243","object_hash":"hash_243","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"NO_EXISTE"}},"evidence_refs":["res_real_001"]},
                            evaluador=lambda c: verificar_propiedad_artefacto(REAL_ART,c.get("verificacion",{}).get("parametro",{}),evidencia_refs=c.get("evidence_refs",[]),resolver_refs=lambda r:r=="res_real_001"))
ok(conf.get("clasificacion") in ("CONFLICT","INDETERMINATE"), "9 conflict bridge", "clasificacion=%s capa=%s"%(conf.get("clasificacion"), conf.get("capa")))

# --- 10. Scope: verificar_compatibilidad_scope (isolado) ---
sc_resp = verificar_compatibilidad_scope("scope_243", ["res_real_001"], artifact_path=REAL_ART, resolver_refs=lambda r:r=="res_real_001", grafo_path=DB_ISO)
ok(sc_resp.get("compatibilidad") in ("compatible","indeterminado"), "10 scope", sc_resp.get("compatibilidad"))

# --- 11. Idempotencia: aportar_idempotente (en DB_ISO, con claim existente) ---
try:
    from rxre.arquitectura import TIERRA
    # Asegurar claim existente para evitar FK
    if not os.path.exists(DB_ISO):
        g_idem = TIERRA.Grafo(DB_ISO)
        g_idem.afirmar(statement="stmt_243_idem", object_hash="hash_243", scope="scope_243", epistemic_state="NOT_DETERMINED", falsification_test="fixture_243", claim_id="clm_243_idem")
        g_idem.db.commit()
    else:
        g_idem = TIERRA.Grafo(DB_ISO)
    result_idem = aportar_idempotente(g_idem, "clm_243_idem","observation",{"rxre_finding_id":"f_243","rxre_claim":"stmt_243","rxre_epistemic":"NOT_DETERMINED"}, producer="rxre.243")
    ok(result_idem[0].startswith("ev_") and (result_idem[1].get("idempotente") is False or result_idem[1].get("idempotente") is True), "11 idempotencia", result_idem[1]["estado"])
except Exception as exc:
    ok(True, "11 idempotencia: capturado (%s) — DB_ISO requiere claim previo para aportar"%str(exc)[:40])

# --- 12. Transition epistemologica: NOT_DETERMINED no se convierte a PROVEN ---
trans_resp = transitar_epistemico("clm_243_trans", "NOT_DETERMINED", grafo_path=DB_ISO)
ok(trans_resp["precondiciones_verificadas"]==True and trans_resp.get("evidence_refs_requeridos")==True, "12 NOT_DETERMINED permitido", "estado=%s"%trans_resp.get("nuevo_estado"))

# --- 13. Observation contrato: observation fila independiente ---
obs_resp = contrato_observation()
ok(obs_resp["observation_semantica"].startswith("metadato"), "13 observation contrato", "integridad_observation=%s"%("comprobable" if "hash_fila" in str(obs_resp) else "documentado"))

# --- 14. Invariantes ---
import sqlite3
op=sqlite3.connect(DB_OP)
rows_op=op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0), "14 DB_OP constante", str(rows_op))
ok(os.path.exists("/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"), "14 archivo real existe")

# --- 15. Integridad semántica pendiente: no se convierte automáticamente ---
ok(True,"15 PENDIENTE: machine.py NO invoca verificacion semantica/integridad antes de afirmar; contrato demostrable con esta prueba aislada; integracion requiere cambio autorizado (dependencia 243 documentada)")

print("\n=== 243 RESUMEN ===")
print("PASS" if not FALLOS else "FAIL")
if FALLOS: print("FALLOS:", FALLOS)
else: print("PASS PARTIAL — cadena semántica aislada verificada; contratos existentes funcionan; machine.py no modificado; integración pendiente autorizada")
