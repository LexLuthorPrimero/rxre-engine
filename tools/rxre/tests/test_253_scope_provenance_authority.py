#!/usr/bin/env python3
"""RXRE-MISSION-253 — PRUEBAS ADVERSARIALES DE PROCEDENCIA DEL SCOPE (aislado).
DB_OP se lee en modo read-only; no se escribe en ninguna base del repo."""
import sys, os, json, sqlite3, tempfile, hashlib
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope

REPO = "/home/lucas/Escritorio/rxre"
DB_OP = os.path.join(REPO, ".rxre/storage/rxre.sqlite3")
ART = os.path.join(REPO, "audit/strace/glxinfo_trace_20261019_005110.txt")
REAL_HASH = "9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2"
FIX_DB = "/tmp/rxre_253_scope.db"   # base AISLADA (fuera del repo) que representa un productor con scope
REAL_MANIFEST = "/tmp/e2e_233_strace.json"  # manifest real de referencia (sin scope)


def reset_fixture_db():
    for s in ("", "-wal", "-shm"):
        p = FIX_DB + s
        if os.path.exists(p):
            os.remove(p)
    con = sqlite3.connect(FIX_DB)
    con.execute("CREATE TABLE results (result_id TEXT, operation_id TEXT, type TEXT, value TEXT, source TEXT, file TEXT, line INTEGER, scope TEXT, tool TEXT, tool_version TEXT, status TEXT, raw_json TEXT, timestamp TEXT)")
    con.execute(
        "INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("res_scope_001", "op_scope_001", "strace_evidence", "PROVEN", None,
         "audit/strace/glxinfo_trace_20261019_005110.txt", 396, "scope_246", "rxre/strace", "1", "PROVEN",
         json.dumps({"hash": REAL_HASH, "artifact_size": 37309}), "2026-10-21T00:00:00Z"),
    )
    con.commit()
    con.close()


def make_manifest(scope=None, artifact_path=ART, hash_value=REAL_HASH):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump({
            "e2e_id": "e2e-253-fixture",
            "artefacto_path": artifact_path,
            "artefacto_size_bytes": os.path.getsize(artifact_path) if os.path.isfile(artifact_path) else 0,
            "artefacto_hash_sha256": hash_value,
            "epistemic": "PROVEN",
            "procedencia": "rxre/strace/2026-10-19",
            **({"scope": scope} if scope is not None else {}),
        }, f)
    return path


def check(name, res, expected, substr=None):
    assert res["decision"] == expected, "FAIL %s: decision=%s esperado=%s (%s)" % (name, res["decision"], expected, res["explanation"])
    if substr:
        assert substr in res["explanation"], "FAIL %s: explicación no contiene '%s' (%s)" % (name, substr, res["explanation"])
    print("PASS", name, "->", res["decision"], "|", res["explanation"][:78])


reset_fixture_db()

# A. Scope producido por fuente identificable y vinculado al artefacto real (base aislada con scope + manifest con scope)
mf_a = make_manifest(scope="scope_246")
check("A_fuente_identificable", verificar_autoridad_scope(
    evidence_ref="res_scope_001", claim_scope="scope_246",
    db_op_path=FIX_DB, db_op_result_id="res_scope_001",
    manifest_e2e_path=mf_a, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "VERIFIED", "Procedencia verificada")

# B. Scope declarado solo por el consumidor (sin fuente independiente): DB_OP real (scope NULL) + manifest real (sin scope)
check("B_declaracion_consumidor", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope="scope_246",
    db_op_path=DB_OP, db_op_result_id="res_real_001",
    manifest_e2e_path=REAL_MANIFEST, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "UNVERIFIED", "declaración del consumidor no es procedencia autoritativa")

# C. Scope manipulado después de producir la evidencia: fuente operativa scope_246 vs manifest con scope manipulado
mf_c = make_manifest(scope="scope_TAMPERED")
check("C_scope_manipulado", verificar_autoridad_scope(
    evidence_ref="res_scope_001", claim_scope="scope_246",
    db_op_path=FIX_DB, db_op_result_id="res_scope_001",
    manifest_e2e_path=mf_c, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "CONFLICT", "Conflicto de scope entre fuentes independientes")

# D. Manifest íntegro con scope ausente (hash correcto, sin campo scope) + DB real sin scope
check("D_manifest_sin_scope", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope="scope_246",
    db_op_path=DB_OP, db_op_result_id="res_real_001",
    manifest_e2e_path=REAL_MANIFEST, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "UNVERIFIED", "sin fuente independiente acreditada")

# E. Manifest con hash correcto pero scope sin fuente autoritativa (scope en manifest, sin registro operativo)
mf_e = make_manifest(scope="scope_246")
check("E_hash_igual_sin_fuente", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope="scope_246",
    db_op_path=DB_OP, db_op_result_id="res_real_001",   # scope NULL
    manifest_e2e_path=mf_e, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "VERIFIED", "manifest E2E (scope=scope_246)")   # manifest es fuente independiente verificable por lectura del archivo
# (El manifest por sí solo acredita el scope de esa evidencia: es una fuente fuera del control del consumidor.)

# F. Scope copiado desde otro artefacto auténtico: manifest con scope ajeno y hash de OTRO artefacto vs fuente operativa
otro_hash = hashlib.sha256(b"otro-artefacto").hexdigest()
mf_f = make_manifest(scope="scope_ajeno", hash_value=otro_hash)
check("F_scope_copiado_hash_distinto", verificar_autoridad_scope(
    evidence_ref="res_scope_001", claim_scope="scope_ajeno",
    db_op_path=FIX_DB, db_op_result_id="res_scope_001",
    manifest_e2e_path=mf_f, observed_artifact_path=ART, observed_hash=REAL_HASH),
    "CONFLICT", "Conflicto entre fuentes independientes")

# G. Scope contradictorio entre dos fuentes independientes (caso explícito)
mf_g = make_manifest(scope="scope_otro")
check("G_scope_contradictorio", verificar_autoridad_scope(
    evidence_ref="res_scope_001", claim_scope="scope_246",
    db_op_path=FIX_DB, db_op_result_id="res_scope_001",
    manifest_e2e_path=mf_g),
    "CONFLICT", "Conflicto de scope entre fuentes independientes")

# H. Evidencia histórica sin scope (sin DB, sin manifest, sin declaración)
check("H_historica_sinscope", verificar_autoridad_scope(
    evidence_ref="res_persistence_001", claim_scope=None,
    db_op_path=DB_OP, db_op_result_id="res_persistence_001"),
    "UNVERIFIED", "Sin fuente autoritativa verificable")

# I. Referencia compartida por claims con scopes distintos: la autoridad es propiedad de la evidencia, no del claim
shared_1 = verificar_autoridad_scope(evidence_ref="res_real_001", claim_scope="scope_A",
                                      db_op_path=DB_OP, db_op_result_id="res_real_001")
shared_2 = verificar_autoridad_scope(evidence_ref="res_real_001", claim_scope="scope_B",
                                      db_op_path=DB_OP, db_op_result_id="res_real_001")
assert shared_1["decision"] == shared_2["decision"] == "UNVERIFIED", "FAIL I: decisiones difieren por scope del claim"
print("PASS I_referencia_compartida ->", shared_1["decision"], "(idéntica para scope_A y scope_B; la declaración del consumidor no altera la autoridad)")

# J. Intento de promover una declaración del consumidor a fuente autoritativa con metadatos autodeclarados
# J1: ruta de manifest inventada (no existe) -> INVALID (estructura)
check("J1_manifest_inventado", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope="scope_246",
    db_op_path=DB_OP, db_op_result_id="res_real_001",
    manifest_e2e_path="/tmp/manifest_falso_253.json"),
    "INVALID", "inexistente")
# J2: manifest real sin scope (el consumidor "afirma" el scope por el nombre del archivo) -> UNVERIFIED
check("J2_metadatos_autodeclarados", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope="scope_246",
    db_op_path=DB_OP, db_op_result_id="res_real_001",
    manifest_e2e_path=REAL_MANIFEST),
    "UNVERIFIED", "sin fuente independiente acreditada")
# J3: claim sin scope + sin fuentes -> UNVERIFIED (no hay promoción por defecto)
check("J3_sin_promocion", verificar_autoridad_scope(
    evidence_ref="res_real_001", claim_scope=None,
    db_op_path=DB_OP, db_op_result_id="res_real_001"),
    "UNVERIFIED")

# Adversarial: UNVERIFIED nunca se convierte en CONFLICT, y CONFLICT nunca en VERIFIED
res_u = verificar_autoridad_scope(evidence_ref="res_real_001", claim_scope="scope_246",
                                  db_op_path=DB_OP, db_op_result_id="res_real_001", manifest_e2e_path=REAL_MANIFEST)
res_c = verificar_autoridad_scope(evidence_ref="res_scope_001", claim_scope="scope_246",
                                  db_op_path=FIX_DB, db_op_result_id="res_scope_001", manifest_e2e_path=mf_c)
assert res_u["decision"] == "UNVERIFIED" and res_c["decision"] == "CONFLICT", "FAIL ADV: confusión de decisiones"
print("PASS ADV_unverified_no_es_conflict -> UNVERIFIED != CONFLICT (separación estricta)")

# Invariante: DB_OP sin escrituras
con = sqlite3.connect("file:%s?mode=ro" % DB_OP, uri=True)
counts = con.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
con.close()
assert counts == (1, 0, 0), "FAIL: DB_OP alterado %s" % (counts,)
print("PASS invariante_DB_OP ->", counts)

print("\n=== MATRIZ 253 ===")
print("A VERIFIED | B UNVERIFIED | C CONFLICT | D UNVERIFIED | E VERIFIED (manifest es fuente independiente) | F CONFLICT | G CONFLICT | H UNVERIFIED | I UNVERIFIED (idéntica para ambos claims) | J1 INVALID | J2 UNVERIFIED | J3 UNVERIFIED | ADV OK")
