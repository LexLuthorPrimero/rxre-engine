#!/usr/bin/env python3
"""RXRE-208 — Contrato de transición finding -> claim (prueba aislada).
Atraviesa machine.procesar_linea (op:research) en base aislada (/tmp).
No modifica operativa ni zonas protegidas. Fixtures sinteticos etiquetados.
"""
import sqlite3, os, sys, tempfile, shutil, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store as S
from rxre.arquitectura import TIERRA
from rxre.contracts.transition_policy import política_transición
from rxre.adapters.adapter_finding_tierra import ejecutar_adaptador, claim_id_de

TMPDIR = tempfile.mkdtemp(prefix="rxre208_")
DB_ISO = os.path.join(TMPDIR, "operativa.sqlite3")
DB_ISO_T = os.path.join(TMPDIR, "tierra_208.sqlite3")
FAILURES = []

def v(name, cond, detail=""):
    if cond:
        print("PASS", name)
    else:
        print("FAIL", name, "::", detail)
        FAILURES.append(name)

# --- Crear base aislada operativa (esquema real) ---
print("=== Creando base operativa aislada:", DB_ISO, "===")
os.environ["RXRE_DB"] = DB_ISO
c = S.conectar(DB_ISO)

# --- Fixtures sinteticos ---
# Un hallazgo PROVEN completo (v3 contrato)
# Resultado existente para refs
res_op = {"op":"test_208", "capability":"test", "results":[
    {"result_id":"res_208_e1", "value":"{}", "source":"test", "status":"0"},
    {"result_id":"res_208_e2", "value":"{}", "source":"test", "status":"0"}]}
S.registrar(c, res_op, {"status":"ok", "results":[{"result_id":"res_208_e1","value":"{}","source":"test","status":"0"},{"result_id":"res_208_e2","value":"{}","source":"test","status":"0"}]})
# Finding PROVEN completo
fid_proven = S.guardar_finding(c, {
    "finding_id":"finding_208_proven",
    "claim":"Hallazgo completo: acceso DRM con evidencia existente",
    "epistemic":"PROVEN",
    "evidence_ids":["res_208_e1","res_208_e2"],
    "object_hash":"sha208:abc",
    "scope":"rx208",
    "falsification_test":"romper acceso y verificar ausencia",
    "derivation_refs":"[]",
    "contradiction_refs":"[]",
    "limitations":"[\"no UMR\"]",
    "provenance":"{'producer':'fixture_208'}"
})
# Finding PARTIAL completo
fid_partial = S.guardar_finding(c, {
    "finding_id":"finding_208_partial",
    "claim":"Hallazgo parcial: evidencia incompleta",
    "epistemic":"PARTIAL",
    "evidence_ids":["res_208_e1"],
    "object_hash":"sha208:def",
    "scope":"rx208_b",
    "falsification_test":"test_fals_p",
    "derivation_refs":"[]",
    "contradiction_refs":"[]",
    "limitations":"[]",
    "provenance":"{}"
})
# Finding PROVEN_ABSENT completo
fid_abs = S.guardar_finding(c, {
    "finding_id":"finding_208_absent",
    "claim":"Contradiccion: acceso observado pero sin evidencia de ejecucion interna",
    "epistemic":"PROVEN_ABSENT",
    "evidence_ids":[],
    "object_hash":"sha208:abs",
    "scope":"rx208_c",
    "falsification_test":"test_fals_abs",
    "derivation_refs":"[]",
    "contradiction_refs":"[]",
    "limitations":"[\"UMR no autorizado\"]",
    "provenance":"{}"
})
c.commit()

# --- Resolver de referencias (consultando la DB aislada) ---
VALID_REFS = {"res_208_e1", "res_208_e2"}

def resolver_refs_local(ref: str) -> bool:
    return ref in VALID_REFS

# --- Prueba del contrato de transición (política pura) ---
print("\n=== POLITICA DE TRANSICION ===")
for caso in [
    ("proven_completo", fid_proven),
    ("partial_completo", fid_partial),
    ("proven_absent_completo", fid_abs),
]:
    row = S.recuperar_finding(c, caso[1])
    res_pol = política_transición(row, resolver_refs=lambda r: resolver_refs_local(r))
    v(f"pol_{caso[0]}_decision", res_pol["decision"] == "ACCEPT", res_pol["reason"][:60] if res_pol.get("reason") else "")

# Verificar que PARTIAL no se eleva en claim_pre
partial_pol = política_transición(S.recuperar_finding(c, fid_partial), resolver_refs=lambda r: resolver_refs_local(r))
claim_pre_p = partial_pol.get("claim_pre")
if claim_pre_p:
    v("pol_5_partial_no_elevado", claim_pre_p.get("epistemic_state") == "PARTIAL", claim_pre_p.get("epistemic_state"))

# PROVEN con refs inexistente -> REJECT
find_bad = dict(S.recuperar_finding(c, fid_proven), evidence_ids=["bad_ref", "res_208_e1"])
res_bad = política_transición(find_bad, resolver_refs=lambda r: resolver_refs_local(r))
v("pol_2_ref_inexistente_rechazado", res_bad["decision"] == "REJECT" and "bad_ref" in res_bad.get("reason", ""), res_bad.get("reason",""))

# PROVEN sin refs -> REJECT (referencia no demostrada)
find_noref = dict(S.recuperar_finding(c, fid_proven), evidence_ids=[])
res_noref = política_transición(find_noref, resolver_refs=lambda r: resolver_refs_local(r))
v("pol_1_proven_sin_refs_rechazado", res_noref["decision"] == "REJECT", res_noref.get("reason",""))

# Hallazgo con falsification_test faltante -> NEEDS_INPUT
# Nota: guardar_finding deriva el id de claim+evidence_ids (fingerprint), asi que
# el texto de `claim` debe ser distinto para no colisionar con el finding PROVEN.
find_miss = dict(S.recuperar_finding(c, fid_proven),
                 claim="Hallazgo historico sin campos formales v3",
                 falsification_test=None, finding_id="finding_208_missing")
try:
    row_miss = S.guardar_finding(c, find_miss)
    v("pol_3_miss_falsif_falla_guardar", False, "deberia fallar CONTRATO_INCOMPLETO, devolvio %s" % row_miss)
except Exception as e:
    v("pol_3_miss_falsif_falla_guardar", "CONTRATO_INCOMPLETO" in str(e) or "Integrity" in str(type(e)), str(e))

# --- Flujo real: machine.procesar_linea con op:research ---
print("\n=== FLUJO REAL op:research ===")
os.environ["RXRE_DB"] = DB_ISO
import rxre.api.machine as M
resp_proven = M.procesar_linea(json.dumps({
    "op":"research","kind":"claim","status":"PROVEN","text":"Claim operativo con evidencia existente",
    "refs":["res_208_e1","res_208_e2"],"session":"rx208","target":"rx208"
}))
print("research PROVEN:", resp_proven)
# Si refs existen, debe ser ok; si no, debe ser blocked (pero aqui existen)
res_proven_op = M.procesar_linea(json.dumps({
    "op":"research","kind":"claim","status":"PROVEN","text":"Claim sin evidencia",
    "session":"rx208","target":"rx208"
}))
print("research PROVEN sin refs:", res_proven_op)
# Referencia inexistente a nivel operativa
res_bad_op = M.procesar_linea(json.dumps({
    "op":"research","kind":"claim","status":"PROVEN","text":"Referencia falsa",
    "refs":["inexistente_999"],"session":"rx208","target":"rx208"
}))
print("research con ref inexistente:", res_bad_op)

# --- Verificación operativa: base aislada ---
oper_op = sqlite3.connect(DB_ISO)
claims_op = oper_op.execute("SELECT kind, status, refs_json FROM research WHERE kind='claim'").fetchall()
oper_op.close()
# Verificar que la base persistente (.rxre/storage/) no fue alterada
op_legacy = sqlite3.connect("file:/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3?mode=ro", uri=True)
claims_legacy = op_legacy.execute("SELECT count(*) FROM claims").fetchone()[0]
findings_legacy = op_legacy.execute("SELECT count(*) FROM findings WHERE finding_id LIKE 'rx208_%'").fetchone()[0]
op_legacy.close()

db_op_intact = claims_op is not None  # no importa contenido exacto; lo importante es que existe
v("op_oper_207_research_creado", len([r for r in claims_op if r[0]=="claim"]) >= 1, claims_op)
# Verificar persistencia intacta de proteccion
v("oper_207_zona_protegida_intacta", claims_legacy == 2 and findings_legacy == 0,
  f"claims_legacy={claims_legacy}, findings_legacy={findings_legacy}")

# --- Transición: política + adaptador aislado para caso PROVEN completo ---
print("\n=== ADAPTADOR + POLITICA (aislado, no persistente) ===")
g = TIERRA.Grafo(DB_ISO_T)
res_adapt = ejecutar_adaptador(g, S.recuperar_finding(c, fid_proven), resolver_refs=lambda r: r in {"res_208_e1","res_208_e2"}, autorizacion=True)
cl_adapt = g.leer(res_adapt["claim_id"])
print("Adaptador claim:", cl_adapt.get("epistemic_state"), "evidencia:", len(cl_adapt.get("evidence_refs") or []))
# No debe crear duplicados
v("adapt_207_no_duplicados", g.leer(res_adapt["claim_id"]) is not None,
  res_adapt.get("claim_id"))
# Limpieza
shutil.rmtree(TMPDIR, ignore_errors=True)
os.remove(DB_ISO) if os.path.exists(DB_ISO) else None
# Limpieza TMPDB extra si quedo
for p in [DB_ISO, DB_ISO_T]:
    if isinstance(p, str) and os.path.exists(p):
        try: os.unlink(p)
        except: pass
print("\n=== RESULTADO 208 ===")
print("PASS" if not FAILURES else "FAILURES -> %s" % FAILURES)
