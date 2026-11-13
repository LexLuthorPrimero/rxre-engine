#!/usr/bin/env python3
"""RXRE-210 — Puerta de autorización explícita finding -> TIERRA.
Aislada: base temporal en /tmp. No toca base operativa ni zonas protegidas.
"""
import sqlite3, tempfile, os, sys, shutil, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.authorization_gate import autorizacion_transicion
import rxre.contracts.transition_policy as _pol
politica_transicion = getattr(_pol, [n for n in dir(_pol) if 'transi' in n][0])
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
from rxre.arquitectura import TIERRA

FAILURES = []
def v(n, cond, d=""):
    if cond: print("PASS", n)
    else:
        print("FAIL", n, "::", d); FAILURES.append(n)

TMP = tempfile.mkdtemp(prefix="rxre210_")
DB_T = os.path.join(TMP, "tierra.sqlite3")
DB_OP = os.path.join(TMP, "op.sqlite3")

# --- Base operativa aislada: resultados reales para refs ---
import rxre.core.store as S
c = S.conectar(DB_OP)
S.registrar(c, {"op":"op_210","capability":"test"},
            {"status":"ok","results":[{"result_id":"res_210_ok","value":"{}","source":"fixture","status":"0"}]})
c.commit()
# snapshots de conteos para probar ausencia de escrituras
def counts(db):
    cc = sqlite3.connect(db)
    out = {}
    for t in ("research","findings","operations","results"):
        try: out[t] = cc.execute("SELECT count(*) FROM %s" % t).fetchone()[0]
        except Exception: out[t] = None
    cc.close(); return out
SNAP_BEFORE = counts(DB_OP)
SNAP_T_BEFORE = counts(DB_T) if os.path.exists(DB_T) else {}

def resolver(r): return r == "res_210_ok"

# ===================================================================
# R1: explicit_enable ausente/falso -> RECHAZADA, sin escrituras
# ===================================================================
f_ok = {"finding_id":"f_210_1","claim":"Claim autorizado 210","epistemic":"PROVEN",
        "object_hash":"h210","scope":"sc210","scope_provenance":"EXPLICIT","falsification_test":"romper y verificar",
        "evidence_ids":["res_210_ok"],"derivation_refs":[],"contradiction_refs":[],
        "limitations":[],"provenance":{"producer":"fixture_210"}}
r1 = autorizacion_transicion(DB_T, f_ok, resolver, explicit_enable=False)
v("R1a_sin_autorizacion_rechazada", r1.get("decision")=="REJECT", r1)
v("R1b_sin_autorizacion_sin_filas", not os.path.exists(DB_T) or counts(DB_T).get("research") in (None,0), str(counts(DB_T) if os.path.exists(DB_T) else {}))
r1b = preintegrate_finding_to_tierra(DB_T, f_ok, resolver_refs=resolver, explicit_enable=False)
v("R1c_hook_bloqueado_por_defecto", r1b.get("decision")=="NOT_ACTIVATED", r1b)

# ===================================================================
# R2/R3: explicit_enable=True con datos validos -> ACCEPT, escribe
# ===================================================================
r2 = autorizacion_transicion(DB_T, f_ok, resolver, explicit_enable=True)
v("R2_autorizado_ok", r2.get("status")=="ok" and r2.get("decision")=="ACCEPT", r2)
claim_id = r2.get("claim_id")
g = TIERRA.Grafo(DB_T)
cl = g.leer(claim_id) if claim_id else None
v("R3_claim_persistido", cl is not None and cl["epistemic_state"]=="PROVEN", cl.get("epistemic_state") if cl else None)
v("R3b_evidence_refs_no_vacios", bool(cl and cl.get("evidence_refs")), cl.get("evidence_refs") if cl else None)
# Verificacion de integridad de evidencia
for ev in (cl.get("evidence_refs") or []):
    fila = g.leer_evidencia(ev, verificar=True)
    v("R3c_evidencia_hash_%s" % ev[:6], fila.get("hash_verificado") is True, fila.get("hash_verificado"))

# ===================================================================
# R4: falsification_test ausente -> NEEDS_INPUT, nunca inventado
# ===================================================================
f_nofals = dict(f_ok, finding_id="f_210_nofals", claim="Claim sin falsification 210",
                falsification_test=None)
r4 = preintegrate_finding_to_tierra(DB_T, f_nofals, resolver_refs=resolver, explicit_enable=True)
v("R4_needs_input", r4.get("decision")=="NEEDS_INPUT", r4)
v("R4b_no_claim_creado", g.leer(r4.get("claim_id") or "clm_inexistente_xxx") is None, r4.get("claim_id"))

# ===================================================================
# R5: PARTIAL conserva estado exacto
# ===================================================================
f_par = dict(f_ok, finding_id="f_210_par", claim="Claim parcial 210", epistemic="PARTIAL")
r5 = preintegrate_finding_to_tierra(DB_T, f_par, resolver_refs=resolver, explicit_enable=True)
cl5 = g.leer(r5.get("claim_id"))
v("R5_partial_conservado", cl5 is not None and cl5["epistemic_state"]=="PARTIAL", cl5.get("epistemic_state") if cl5 else None)

# ===================================================================
# R6: PROVEN_ABSENT preserva semantica de ausencia
# ===================================================================
f_abs = dict(f_ok, finding_id="f_210_abs",
              claim="Ausencia de evidencia interna 210", epistemic="PROVEN_ABSENT", evidence_ids=[])
r6 = preintegrate_finding_to_tierra(DB_T, f_abs, resolver_refs=resolver, explicit_enable=True)
cl6 = g.leer(r6.get("claim_id"))
v("R6_proven_absent_conservado", cl6 is not None and cl6["epistemic_state"]=="PROVEN_ABSENT", cl6.get("epistemic_state") if cl6 else None)
v("R6b_no_es_positivo", cl6 is not None and cl6["epistemic_state"]!="PROVEN", cl6.get("epistemic_state") if cl6 else None)

# ===================================================================
# R7: estado desconocido -> rechazo
# ===================================================================
f_bad = dict(f_ok, finding_id="f_210_bad", claim="Estado desconocido 210", epistemic="OBSERVED")
r7 = preintegrate_finding_to_tierra(DB_T, f_bad, resolver_refs=resolver, explicit_enable=True)
v("R7_estado_desconocido_rechazado", r7.get("decision")=="REJECT", r7)

# ===================================================================
# R8: contradicciones exigen declaracion explicita
# ===================================================================
f_ctr = dict(f_ok, finding_id="f_210_ctr", claim="Claim con contradiccion 210",
             contradiction_refs=["ctr_210"])
r8 = preintegrate_finding_to_tierra(DB_T, f_ctr, resolver_refs=resolver, explicit_enable=True)
v("R8_contradiccion_sin_declaracion", r8.get("decision")=="NEEDS_INPUT", r8)
# Con declaracion explicita y ref valida
r8b = preintegrate_finding_to_tierra(DB_T, f_ctr, resolver_refs=resolver,
        contradiction_statements={"statements":[{"statement":"contradiccion explicita 210","severity":"media"}]},
        explicit_enable=True)
ctr_rows = g.db.execute("SELECT count(*) FROM contradictions WHERE claim_id=?", (r8b.get("claim_id"),)).fetchone()[0]
v("R8b_contradiccion_registrada", ctr_rows >= 1, ctr_rows)

# ===================================================================
# R9: reintento -> identidad determinista, sin duplicados
# ===================================================================
r9 = preintegrate_finding_to_tierra(DB_T, f_ok, resolver_refs=resolver, explicit_enable=True)
v("R9_reintento_mismo_id", r9.get("claim_id")==claim_id and (r9.get("ya_existia") is True or r9.get("estado_epistemologico")=="ya_existia"), r9)
claims_total = g.db.execute("SELECT count(*) FROM claims").fetchone()[0]
ev_total = g.db.execute("SELECT count(*) FROM evidence").fetchone()[0]
r9b = preintegrate_finding_to_tierra(DB_T, f_ok, resolver_refs=resolver, explicit_enable=True)
claims_total2 = g.db.execute("SELECT count(*) FROM claims").fetchone()[0]
ev_total2 = g.db.execute("SELECT count(*) FROM evidence").fetchone()[0]
v("R9b_sin_filas_duplicadas", claims_total==claims_total2 and ev_total==ev_total2, (claims_total,claims_total2,ev_total,ev_total2))

# ===================================================================
# R10: error de persistencia -> rollback, sin registros parciales
# ===================================================================
# Se fuerza el fallo con dos contradicciones de igual enunciado (PK duplicada)
f_fail = dict(f_ok, finding_id="f_210_fail", claim="Claim con fallo 210", contradiction_refs=["c1"])
r10 = preintegrate_finding_to_tierra(DB_T, f_fail, resolver_refs=resolver,
        contradiction_statements={"statements":[{"statement":"dup 210","severity":"media"},
                                               {"statement":"dup 210","severity":"media"}]},
        explicit_enable=True)
v("R10a_error_reportado", r10.get("status")=="error" or r10.get("decision")=="REJECT", r10)
claims_after_fail = g.db.execute("SELECT count(*) FROM claims").fetchone()[0]
v("R10b_sin_claim_parcial", claims_after_fail==claims_total, (claims_after_fail, claims_total))
# el claim del caso fallido no debe existir
from rxre.adapters.adapter_finding_tierra import claim_id_de
cid_fail = claim_id_de(f_fail["claim"], f_fail["object_hash"], f_fail["scope"])
v("R10c_claim_fallido_ausente", g.leer(cid_fail) is None, cid_fail)

# ===================================================================
# Ausencia de escrituras en la base operativa (observada, no deducida)
# ===================================================================
SNAP_AFTER = counts(DB_OP)
v("R11_base_operativa_sin_escrituras", SNAP_AFTER==SNAP_BEFORE, (SNAP_BEFORE, SNAP_AFTER))
# Ninguna escritura en .rxre/storage ni base operativa del proyecto
op_leg = sqlite3.connect("file:/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3?mode=ro", uri=True)
claims_leg = op_leg.execute("SELECT count(*) FROM claims").fetchone()[0]
op_leg.close()
v("R11b_legado_intacto", claims_leg==2, claims_leg)

# ===================================================================
# Ruta ordinaria: op:research NO convierte a TIERRA
# ===================================================================
os.environ["RXRE_DB"] = DB_OP
from rxre.api import machine as M
resp = M.procesar_linea(json.dumps({"op":"research","kind":"claim","status":"PROVEN",
      "text":"Claim ordinario por op:research","refs":["res_210_ok"],"session":"rx210"}))
v("R12_op_research_ok", resp.get("status")=="ok", resp)
research_rows = sqlite3.connect(DB_OP).execute("SELECT count(*) FROM research WHERE kind='claim'").fetchone()[0]
v("R12b_registro_operativo_creado", research_rows>=1, research_rows)
claims_op_db = sqlite3.connect(DB_OP).execute("SELECT count(*) FROM sqlite_master WHERE name='claims'").fetchone()[0]
v("R12c_op_research_no_crea_tabla_claims", claims_op_db==0, claims_op_db)
claims_tierra = g.db.execute("SELECT count(*) FROM claims").fetchone()[0]
v("R12d_op_research_no_crea_claim_tierra", claims_tierra==claims_total, (claims_tierra, claims_total))

# Limpieza
g.cerrar()
shutil.rmtree(TMP, ignore_errors=True)

print("\n=== RESULTADO 210 ===")
print("PASS" if not FAILURES else "FAILURES -> %s" % FAILURES)
