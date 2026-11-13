#!/usr/bin/env python3
"""
M289 — Test integrado de verificación E2E con registro independiente.
Trabaja exclusivamente en DB_ISO (/tmp/rxre_289_iso.sqlite3).
No modifica DB_OP, store.py, audit/evidence/, machine.py ni core/evidence_integrity.py.
"""
import sqlite3, hashlib, json, os, subprocess, sys, tempfile

# Paths protegidos (verificación sin modificación)
DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
STORE = "/home/lucas/Escritorio/rxre/tools/rxre/core/store.py"
CONTRACT = "/home/lucas/Escritorio/rxre/tools/rxre/contracts/scope_provenance_contract.py"
ART = "/home/lucas/Escritorio/rxre/audit/artefactos/verificacion_282_20261022.txt"
DB_ISO = "/tmp/rxre_289_iso.sqlite3"
SYNC = "audit/debugfs/RXRE-MISSION-289-E2E-VERIFICATION-CLOSURE.md"

# Hashes protegidos (antes/después: sin cambios esta misión)
with open(STORE, "rb") as f: HASH_STORE = hashlib.sha256(f.read()).hexdigest()
with open(CONTRACT, "rb") as f: HASH_CONTRACT = hashlib.sha256(f.read()).hexdigest()
with open(ART, "rb") as f: HASH_ART = hashlib.sha256(f.read()).hexdigest()
with open(DB_OP, "rb") as f: HASH_DBOP = hashlib.sha256(f.read()).hexdigest()


def build_db_iso():
    for s in ("", "-wal", "-shm"):
        p = DB_ISO + s
        if os.path.exists(p):
            os.remove(p)
    c = sqlite3.connect(DB_ISO)
    c.execute("CREATE TABLE operations (id INTEGER PRIMARY KEY AUTOINCREMENT, operation_id TEXT UNIQUE NOT NULL, scope TEXT, declared_scope TEXT, authorized_scope TEXT, auth_decision TEXT, auth_actor TEXT, auth_timestamp TEXT, raw_json TEXT)")
    c.execute("CREATE TABLE results (id INTEGER PRIMARY KEY AUTOINCREMENT, result_id TEXT UNIQUE NOT NULL, operation_id TEXT, type TEXT, value TEXT, source TEXT, file TEXT, line INTEGER, scope TEXT, tool TEXT, tool_version TEXT, status TEXT, raw_json TEXT, timestamp TEXT, row_hash TEXT, supersedes_ref TEXT, verified_scope TEXT, scope_decision TEXT, limitations_json TEXT)")
    c.execute("CREATE TABLE verificacion_resultado (id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_ref TEXT NOT NULL, operation_id TEXT NOT NULL, result_id TEXT NOT NULL, manifest_path TEXT NOT NULL, manifest_hash_sha256 TEXT NOT NULL, artifact_path TEXT NOT NULL, artifact_hash_sha256 TEXT NOT NULL, row_hash_reference TEXT NOT NULL, scope_decision TEXT NOT NULL, verified_scope TEXT NOT NULL, decision_contract TEXT NOT NULL, contract_version TEXT NOT NULL DEFAULT 'M285', timestamp_iso TEXT NOT NULL, actor TEXT NOT NULL DEFAULT 'lucas', UNIQUE (evidence_ref, operation_id, result_id))")
    c.execute("CREATE INDEX ix_ver_op ON verificacion_resultado (operation_id)")
    c.execute("CREATE INDEX ix_ver_res ON verificacion_resultado (result_id)")
    c.execute("CREATE INDEX ix_ver_evidence ON verificacion_resultado (evidence_ref)")
    c.commit()
    c.close()
    return DB_ISO


def insert_row():
    # Fila original sin falsear VERIFIED (scope_decision='AUTHORIZED', verified_scope='')
    c = sqlite3.connect(DB_ISO)
    c.execute("DELETE FROM results")
    c.execute("DELETE FROM operations")
    raw_json = json.dumps({"hash": HASH_ART}, sort_keys=True, default=str)
    campos = {
        "result_id": "res_289_e2e", "operation_id": "op_289_verified",
        "type": "strace_verificacion", "value": "hash_289_artefacto", "source": "rxre_289_e2e",
        "file": ART, "line": 0, "scope": "scope_289_e2e", "tool": "rxre_289_e2e",
        "tool_version": "1.0", "status": "ok", "raw_json": raw_json,
        "timestamp": "2026-10-22T00:00:00Z",
    }
    row_hash = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
    c.execute("INSERT INTO operations (operation_id,scope,declared_scope,authorized_scope,auth_decision,auth_actor,auth_timestamp,raw_json) VALUES (?,?,?,?,?,?,?,?)",
              ("op_289_verified", "scope_289_e2e", "scope_289_e2e", "scope_289_e2e", "APPROVED", "lucas", "2026-10-22T00:00:00Z", "{}"))
    c.execute("INSERT INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash,verified_scope,scope_decision,limitations_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("res_289_e2e", "op_289_verified", "strace_verificacion", "hash_289_artefacto", "rxre_289_e2e", ART, 0, "scope_289_e2e", "rxre_289_e2e", "1.0", "ok", raw_json, "2026-10-22T00:00:00Z", row_hash, "", "AUTHORIZED", "{}"))
    c.commit()
    c.close()
    return row_hash, "op_289_verified", "res_289_e2e"


def write_manifest(manifest_path):
    with open(manifest_path, "w") as f:
        json.dump({
            "manifest_version": "e2e_289_e2e",
            "operation_id": "op_289_verified",
            "result_id": "res_289_e2e",
            "scope": "scope_289_e2e",
            "hash": HASH_ART,
            "artifact_path": ART,
            "scope_decision": "UNVERIFIED",
            "verified_scope": "",
            "timestamp": "2026-10-22T00:00:00Z",
        }, f, indent=2)
    return hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()


def run_contract_via_subprocess(db_path, result_id, manifest_path, artifact_path, observed_hash):
    """Ejecuta el contrato real en un proceso aislado (sin interpolación de strings en código Python)."""
    # Usamos argumentos de línea de comandos para evitar errores de cotización.
    script_path = "/home/lucas/Escritorio/rxre/tools/rxre/contracts/scope_provenance_contract.py"
    code = f"""
import sys, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
res = verificar_autoridad_scope(
    "ref_289_integrated",
    claim_scope="scope_289_e2e",
    db_op_path="{db_path}",
    db_op_result_id="{result_id}",
    manifest_e2e_path="{manifest_path}",
    observed_artifact_path="{artifact_path}",
    observed_hash="{observed_hash}"
)
print(json.dumps(res))
"""
    # Escribimos código a archivo temporal para evitar problemas con -c
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
        tf.write(code)
        tmp_script = tf.name
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = "/home/lucas/Escritorio/rxre/tools"
        proc = subprocess.run(
            [sys.executable, tmp_script],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        # No silenciar: distinguir explícitamente ERROR, FAIL, PASS
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if proc.returncode != 0:
            return {"decision": "HARNESS_ERROR", "explanation": f"Subprocess crash (rc={proc.returncode}): stderr={stderr[-200:]}", "stdout": stdout, "stderr": stderr}
        if not stdout:
            return {"decision": "HARNESS_ERROR", "explanation": "Subprocess produced empty stdout (possible missing import or silent abort)", "stdout": stdout, "stderr": stderr}
        try:
            res = json.loads(stdout)
        except json.JSONDecodeError:
            return {"decision": "HARNESS_ERROR", "explanation": f"Invalid JSON from contract harness: stdout={stdout[:200]}, stderr={stderr[-200:]}", "stdout": stdout, "stderr": stderr}
        return res
    finally:
        try:
            os.unlink(tmp_script)
        except OSError:
            pass


def test_case(name, description, check_fn, details_fn):
    try:
        ok = check_fn()
        details = details_fn() if ok else ""
        return (name, ok, "PASS" if ok else "FAIL", details, None)
    except Exception as exc:
        return (name, False, "ERROR", str(exc)[:200], str(exc))


def main():
    build_db_iso()
    results = []
    # --- Insertar fila original ---
    row_hash_ref, op_id, res_id = insert_row()
    manifest_path = "/tmp/rxre_289_manifest.json"
    manifest_hash = write_manifest(manifest_path)

    def A():
        res = run_contract_via_subprocess(DB_ISO, res_id, manifest_path, ART, HASH_ART)
        # El contrato real debe concluir VERIFIED para datos válidos
        return res.get("decision") == "VERIFIED"
    def A_details(): return f"contract_decision={run_contract_via_subprocess(DB_ISO, res_id, manifest_path, ART, HASH_ART).get('decision')}"
    # A se ejecuta con detalles capturados; simplificaremos el reporte con un solo llamado.
    a_contract = run_contract_via_subprocess(DB_ISO, res_id, manifest_path, ART, HASH_ART)
    a_ok = a_contract.get("decision") == "VERIFIED"
    results.append(("A caso legitimo (VERIFIED)", a_ok, a_contract.get("decision"), a_contract.get("explanation", "")[:120], None))

    # --- B: manifest alterado ---
    man_bad = "/tmp/rxre_289_bad_manifest.json"
    json.dump({"manifest_version":"bad","operation_id":"op_289_verified","result_id":"res_289_e2e","scope":"scope_289_e2e","hash":"bad_hash","artifact_path":ART,"scope_decision":"VERIFIED","verified_scope":"VERIFIED","timestamp":"2026-10-22T00:00:00Z"}, open(man_bad,"w"))
    b_contract = run_contract_via_subprocess(DB_ISO, res_id, man_bad, ART, HASH_ART)
    results.append(("B manifest/hash alterado", b_contract.get("decision") != "VERIFIED", b_contract.get("decision"), b_contract.get("explanation","")[:120], None))

    # --- C: referencias cruzadas ---
    man_cross = "/tmp/rxre_289_cross_manifest.json"
    json.dump({"manifest_version":"cross","operation_id":"op_289_verified","result_id":"res_289_OTRA","scope":"scope_289_e2e","hash":HASH_ART,"artifact_path":ART,"scope_decision":"UNVERIFIED","verified_scope":"","timestamp":"2026-10-22T00:00:00Z"}, open(man_cross,"w"))
    c_contract = run_contract_via_subprocess(DB_ISO, res_id, man_cross, ART, HASH_ART)
    results.append(("C referencias cruzadas (result_id distinto)", c_contract.get("decision") != "VERIFIED", c_contract.get("decision"), c_contract.get("explanation","")[:120], None))

    # --- C2: row_hash discordante (alterado un byte) ---
    c = sqlite3.connect(DB_ISO)
    row_hash_bueno = c.execute("SELECT row_hash FROM results WHERE result_id='res_289_e2e'").fetchone()[0]
    c.execute("UPDATE results SET row_hash=? WHERE result_id='res_289_e2e'", (row_hash_bueno[:-1] + ("0" if row_hash_bueno[-1] != "0" else "1"),))
    c.commit()
    c.close()
    c2_contract = run_contract_via_subprocess(DB_ISO, res_id, manifest_path, ART, HASH_ART)
    c = sqlite3.connect(DB_ISO)
    c.execute("UPDATE results SET row_hash=? WHERE result_id='res_289_e2e'", (row_hash_bueno,))
    c.commit()
    c.close()
    results.append(("C2 row_hash discordante (alterado 1 byte)", c2_contract.get("decision") != "VERIFIED", c2_contract.get("decision"), c2_contract.get("explanation","")[:120], None))

    # --- D: registro duplicado bloqueado ---
    c = sqlite3.connect(DB_ISO)
    # Alta inicial (legítima)
    c.execute("INSERT INTO verificacion_resultado (evidence_ref,operation_id,result_id,manifest_path,manifest_hash_sha256,artifact_path,artifact_hash_sha256,row_hash_reference,scope_decision,verified_scope,decision_contract,contract_version,timestamp_iso,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("ref_289_dup","op_289_verified","res_289_e2e",manifest_path,manifest_hash,ART,HASH_ART,row_hash_ref,"VERIFIED","VERIFIED","VERIFIED","M285","2026-10-22T00:00:00Z","lucas"))
    c.commit()
    try:
        # Reintento idempotente con los mismos IDs -> debe ser bloqueado por UNIQUE
        c.execute("INSERT INTO verificacion_resultado (evidence_ref,operation_id,result_id,manifest_path,manifest_hash_sha256,artifact_path,artifact_hash_sha256,row_hash_reference,scope_decision,verified_scope,decision_contract,contract_version,timestamp_iso,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("ref_289_dup","op_289_verified","res_289_e2e",manifest_path,manifest_hash,ART,HASH_ART,row_hash_ref,"VERIFIED","VERIFIED","VERIFIED","M285","2026-10-22T00:00:00Z","lucas"))
        c.commit()
        dup_blocked = False
    except sqlite3.IntegrityError:
        c.rollback()
        dup_blocked = True
    c.close()
    results.append(("D registro duplicado bloqueado (UNIQUE)", dup_blocked, "PASS" if dup_blocked else "FAIL", "IntegrityError=" + str(dup_blocked), None))

    # --- E: rollback + reintento ---
    # Primero registro con datos válidos
    c = sqlite3.connect(DB_ISO)
    # Limpieza previa para reintentar limpio
    c.execute("DELETE FROM verificacion_resultado WHERE evidence_ref LIKE 'ref_289_%'")
    c.commit()
    # Primer intento
    c.execute("INSERT INTO verificacion_resultado (evidence_ref,operation_id,result_id,manifest_path,manifest_hash_sha256,artifact_path,artifact_hash_sha256,row_hash_reference,scope_decision,verified_scope,decision_contract,contract_version,timestamp_iso,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("ref_289_retry","op_289_verified","res_289_e2e",manifest_path,manifest_hash,ART,HASH_ART,row_hash_ref,"VERIFIED","VERIFIED","VERIFIED","M285","2026-10-22T00:00:00Z","lucas"))
    c.commit()
    # Rollback simulado: eliminar registro, luego reinsertar con el mismo contenido (reintento)
    c.execute("DELETE FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'")
    c.commit()
    # Reintento
    try:
        c.execute("INSERT INTO verificacion_resultado (evidence_ref,operation_id,result_id,manifest_path,manifest_hash_sha256,artifact_path,artifact_hash_sha256,row_hash_reference,scope_decision,verified_scope,decision_contract,contract_version,timestamp_iso,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("ref_289_retry","op_289_verified","res_289_e2e",manifest_path,manifest_hash,ART,HASH_ART,row_hash_ref,"VERIFIED","VERIFIED","VERIFIED","M285","2026-10-22T00:00:00Z","lucas"))
        c.commit()
        retry_ok = True
        cnt_retry = 1
    except sqlite3.IntegrityError:
        c.rollback()
        retry_ok = False
        cnt_retry = 0
    c.close()
    results.append(("E rollback + reintento", retry_ok, "PASS" if retry_ok else "FAIL", "registros_tras_retry=%d" % cnt_retry, None))

    # --- F: fallos entre manifest y registro (simulado) ---
    c = sqlite3.connect(DB_ISO)
    # Confirmar que manifest persiste y registro puede ser eliminado/reinsertado
    manifest_still_exists = os.path.isfile(manifest_path)
    manifest_still_hash = hashlib.sha256(open(manifest_path,"rb").read()).hexdigest() == manifest_hash
    before_count = c.execute("SELECT COUNT(*) FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'").fetchone()[0]
    c.execute("DELETE FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'")
    c.commit()
    # Reinsertar tras "fallo parcial"
    c.execute("INSERT INTO verificacion_resultado (evidence_ref,operation_id,result_id,manifest_path,manifest_hash_sha256,artifact_path,artifact_hash_sha256,row_hash_reference,scope_decision,verified_scope,decision_contract,contract_version,timestamp_iso,actor) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("ref_289_retry","op_289_verified","res_289_e2e",manifest_path,manifest_hash,ART,HASH_ART,row_hash_ref,"VERIFIED","VERIFIED","VERIFIED","M285","2026-10-22T00:00:00Z","lucas"))
    c.commit()
    after_count = c.execute("SELECT COUNT(*) FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'").fetchone()[0]
    c.close()
    results.append(("F recuperacion tras fallo parcial", manifest_still_exists and manifest_still_hash and after_count == 1, "PASS" if (manifest_still_exists and after_count == 1) else "FAIL", "manifest_exists=%s manifest_hash_ok=%s antes=%d despues=%d" % (manifest_still_exists, manifest_still_hash, before_count, after_count), None))

    # --- G: integridad fila original inmutable ---
    c = sqlite3.connect(DB_ISO)
    fila = c.execute("SELECT result_id, operation_id, verified_scope, scope_decision, row_hash FROM results WHERE result_id='res_289_e2e'").fetchone()
    reg = c.execute("SELECT evidence_ref, operation_id, result_id, manifest_path, manifest_hash_sha256, artifact_hash_sha256, row_hash_reference, verified_scope, decision_contract FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'").fetchone()
    c.close()
    fila_ok = fila[2] == "" and fila[3] == "AUTHORIZED" and fila[4] == row_hash_ref
    reg_ok = reg[0] == "ref_289_retry" and reg[1] == "op_289_verified" and reg[2] == "res_289_e2e"
    results.append(("G integridad fila original + registro independiente", fila_ok and reg_ok, "PASS" if (fila_ok and reg_ok) else "FAIL", "fila_verified='%s' fila_decision='%s' reg_verified='%s' reg_decision='%s'" % (fila[2], fila[3], reg[7], reg[8]), None))

    # --- H: lectura independiente desde SQLite (proceso nuevo, sin memoria) ---
    c = sqlite3.connect("file:%s?mode=ro" % DB_ISO, uri=True)
    ind_reg = c.execute("SELECT verified_scope, decision_contract FROM verificacion_resultado WHERE evidence_ref='ref_289_retry'").fetchone()
    ind_fila = c.execute("SELECT verified_scope, scope_decision FROM results WHERE result_id='res_289_e2e'").fetchone()
    c.close()
    results.append(("H lectura independiente (verificacion_resultado + fila original)", ind_reg[0] == "VERIFIED" and ind_reg[1] == "VERIFIED" and ind_fila[0] == "" and ind_fila[1] == "AUTHORIZED", "PASS" if (ind_reg and ind_fila and ind_reg[0] == "VERIFIED" and ind_fila[0] == "") else "FAIL", f"ind_reg=(verified={ind_reg[0] if ind_reg else None}, decision={ind_reg[1] if ind_reg else None}) ind_fila=(verified={ind_fila[0]}, decision={ind_fila[1]})", None))

    # --- I: regresiones M283-M288 (confirmar que DB_ISO no afecta DB_OP y que los datos se mantienen) ---
    db_op_untouched = open(DB_OP,"rb").read() == open(DB_OP,"rb").read()  # siempre igual
    # Comprobación real de hash DB_OP
    with open(DB_OP,"rb") as f: db_op_now = hashlib.sha256(f.read()).hexdigest()
    db_op_intact = db_op_now == HASH_DBOP
    results.append(("I integridad DB_OP inalterado", db_op_intact, "PASS" if db_op_intact else "FAIL", "hash=%s (mismo=%s)" % (db_op_now[:12], HASH_DBOP[:12]), None))

    # --- J: no modificación de archivos protegidos ---
    with open(STORE,"rb") as f: store_now = hashlib.sha256(f.read()).hexdigest()
    with open(CONTRACT,"rb") as f: contract_now = hashlib.sha256(f.read()).hexdigest()
    protected_ok = (store_now == HASH_STORE) and (contract_now == HASH_CONTRACT)
    results.append(("J archivos protegidos (store.py, contract) sin cambios", protected_ok, "PASS" if protected_ok else "FAIL", "store=%s contract=%s" % (store_now[:12], contract_now[:12]), None))

    # --- Resumen ---
    print("=== M289 INTEGRATED FLOW RESULTS ===")
    all_pass = 0
    for r in results:
        status = "PASS" if r[1] else ("FAIL" if r[2] == "FAIL" else r[2])
        if r[2] == "PASS":
            all_pass += 1
        print("  [%s] %s | %s" % (status, r[0], r[3]))
    print("TOTAL: %d/%d PASS (FAIL/ERROR=%d)" % (all_pass, len(results), len(results)-all_pass))
    # Escribo archivo de resultados resumido
    with open("/tmp/rxre_289_resultados.txt", "w") as f:
        f.write("M289 RESULTADOS\n")
        for r in results:
            status = "PASS" if r[1] else ("FAIL" if r[2] == "FAIL" else r[2])
            f.write("  [%s] %s | detalle: %s\n" % (status, r[0], r[3]))
        f.write("PROTEGIDOS: DB_OP=%s store=%s contract=%s art=%s\n" % (db_op_now[:12], store_now[:12], contract_now[:12], HASH_ART[:12]))
    return results, a_contract

if __name__ == "__main__":
    results, a_contract = main()
