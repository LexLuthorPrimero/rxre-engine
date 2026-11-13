#!/usr/bin/env python3
"""RXRE-MISSION-246 — CONTRATO DE AUTENTICIDAD / SCOPE / MANIFEST (pruebas aisladas)."""
import sys, sqlite3, hashlib, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.core.evidence_integrity import validate_evidence_path
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto, resolver_evidence_ref
from rxre.contracts.isolated_contract_implementations import verificar_compatibilidad_scope
from rxre.arquitectura import TIERRA

REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
DB_ISO = "/tmp/rxre_246_iso.sqlite3"
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
MANIFEST = "/tmp/e2e_233_strace.json"
FALLOS = []

def ok(c,l,d=""):
    (print("  [PASS] %s %s"%(l,d)) if c else (FALLOS.append(l), print("  [FAIL] %s %s"%(l,d))))

# --- A: Manifest E2E válido ---
ok(validate_evidence_path(MANIFEST, art_path=REAL_ART)["ok"], "A manifest E2E válido -> ok")
# --- B: Manifest alterado (hash incorrecto en archivo) ---
import tempfile, json
bad_manifest = tempfile.mktemp(suffix=".json")
with open(MANIFEST) as f: m = json.load(f)
m["artefacto_hash_sha256"] = "0" * 64
with open(bad_manifest,"w") as f: json.dump(m,f)
ok(validate_evidence_path(bad_manifest, art_path=REAL_ART)["ok"]==False and "hash" in str(validate_evidence_path(bad_manifest, art_path=REAL_ART).get("errors",[])), "B manifest alterado -> rechaza hash")
# --- C: Manifest incompleto (falta campo requerido) ---
inc_manifest = tempfile.mktemp(suffix=".json")
with open(MANIFEST) as f: d=json.load(f)
del d["artefacto_size_bytes"]
with open(inc_manifest,"w") as f: json.dump(d,f)
ok(validate_evidence_path(inc_manifest, art_path=REAL_ART)["ok"]==False and "missing" in str(validate_evidence_path(inc_manifest, art_path=REAL_ART).get("errors",[])).lower(), "C manifest incompleto -> rechaza")
# --- D: Manifest asociado a OTRO artefacto (archivo diferente) ---
ok(validate_evidence_path(MANIFEST, art_path="/dev/null")["ok"]==False, "D manifest con otro artefacto -> rechaza", "errors=%s"%str(validate_evidence_path(MANIFEST, art_path="/dev/null").get("errors")))
# --- E: Referencia DB_OP existente (res_real_001) vs inexistente ---
oc = sqlite3.connect(DB_OP)
row = oc.execute("SELECT 1 FROM results WHERE result_id=?",("res_real_001",)).fetchone()
ok(row is not None, "E referencia res_real_001 existe en DB_OP")
ref_bad = oc.execute("SELECT 1 FROM results WHERE result_id=?",("fixture_bad_ref_246",)).fetchone()
ok(ref_bad is None, "E referencia falsa no existe en DB_OP")
# Autenticidad: resolver_evidence_ref
ok(resolver_evidence_ref("res_real_001") is True, "E resolver_evidence_ref real -> True")
ok(resolver_evidence_ref("fixture_bad_ref_246") is False, "E resolver_evidence_ref falso -> False")
oc.close()
# --- F: Verificación semántica con DB_OP registrado ---
res_sup = verificar_propiedad_artefacto(REAL_ART, {"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, evidencia_refs=["res_real_001"], resolver_refs=lambda r:r=="res_real_001")
ok(res_sup["resultado"]=="SUPPORTED" and res_sup["integridad_evidencia"].get("hash_coincide") is True, "F respaldo + autenticidad -> SUPPORTED")
# --- G: Verificación con hash alterado simulado (archivo alterado) ---
# No alteramos archivo protegido; simulado con texto modificado temporal
import tempfile, shutil
fake_art = tempfile.mktemp(suffix=".txt")
shutil.copy(REAL_ART, fake_art)
with open(fake_art,"a") as f: f.write("ALTERED\n")
res_bad = verificar_propiedad_artefacto(fake_art, {"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, evidencia_refs=["res_real_001"], resolver_refs=lambda r:r=="res_real_001")
ok(res_bad["resultado"]=="INSUFFICIENT" and res_bad.get("integridad_evidencia",{}).get("hash_coincide") is False, "G archivo alterado -> INSUFFICIENT (hash no coincide)")
# --- H: Scope contrato (comparabilidad) ---
# Sin claim en DB_ISO -> indeterminado; con claim -> compatible si mismo scope
clean_db = "/tmp/rxre_246_scope.sqlite3"
for s in ("","-wal","-shm"): p=clean_db+s; (os.path.exists(p) and os.remove(p))
g = TIERRA.Grafo(clean_db)
g.afirmar("stmt_scope","hash","scope_246","PROVEN","f_scope", evidence_refs=["ev_1"], derivation_refs=[], unresolved_obligations=[])
g.db.commit()
g.db.close()
resp_compat = verificar_compatibilidad_scope("scope_246", ["res_real_001"], artifact_path=REAL_ART, resolver_refs=lambda r:r=="res_real_001", grafo_path=clean_db)
ok(resp_compat.get("compatibilidad")=="compatible", "H scope igual con claim existente -> compatible", resp_compat.get("compatibilidad"))
resp_incompat = verificar_compatibilidad_scope("scope_distinct", ["res_real_001"], artifact_path=REAL_ART, resolver_refs=lambda r:r=="res_real_001", grafo_path=clean_db)
ok(resp_incompat.get("compatibilidad")=="indeterminado", "H scope distinto sin claim -> indeterminado (no inventado como incompatible)", resp_incompat.get("compatibilidad"))
# --- I: Referencia existente que apunta a OTRO evento (DB_OP res_real_001 apunta a strace; si referencia declarada como res_real_001 pero archivo es otro) ---
# Ya probado en G (hash alterado). El contrato de autenticidad captura la diferencia.
print("=== 246 RESUMEN ===")
print("PASS" if not FALLOS else "FAIL")
if FALLOS: print("FALLOS:", FALLOS)
else: print("PASS PARTIAL — contratos observados sin cambios; limitaciones documentadas (manifest E2E obligatorio para autenticidad completa; scope indeterminado sin claim previo en DB_ISO)")
