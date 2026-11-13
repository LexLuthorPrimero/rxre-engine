#!/usr/bin/env python3
"""RXRE-M316 — POLÍTICA SQLITE DE ACCESO (PROTOTIPO AISLADO).
Solo opera sobre DB desechable (/tmp/rxre_316_db.sqlite3); no modifica DB_OP ni DB_ISO.
No activa DBOP_ACCESS_M295 real (documentado como INSUFFICIENT para producción)."""
import sqlite3, os, hashlib, json

DB_TEST = "/tmp/rxre_316_db.sqlite3"
AUDIT_LOG = "/tmp/rxre_316_audit.jsonl"

POLICY = {
    # Operaciones permitidas para cada tipo de conexión
    "CREATE": "ALLOW",    # Solo para inicialización del test DB
    "INSERT": "ALLOW",    # Solo en tablas de prueba (not DB_OP)
    "SELECT": "ALLOW",
    "UPDATE": "DENY",     # DB protege; no permitir actualización directa
    "DELETE": "DENY",
    "ALTER": "DENY",
    "DROP": "DENY",
    # Restricción por tabla de auditoría: solo INSERT de registros de auditoría autorizados
}


def _audit_write(event: dict):
    # Registro de auditoría con hash encadenado (prev_hash -> hash de evento)
    last = None
    if os.path.isfile(AUDIT_LOG):
        with open(AUDIT_LOG, "r") as f:
            for line in f:
                last = line.strip()
    event["prev_hash"] = (hashlib.sha256(last.encode()).hexdigest()[:32] if last else "0")
    event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()[:32]
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(event, sort_keys=True, default=str) + "\n")



def set_policy(conn: sqlite3.Connection):
    allowed_select = {"sqlite_master", "sqlite_sequence", "sqlite_autoindex_", "sqlite_stat1", "sqlite_stat2", "sqlite_stat3", "sqlite_stat4", "sqlite_stat_"}
    allowed_insert = {"sqlite_master", "sqlite_sequence", "sqlite_autoindex_", "sqlite_stat_"}
    allowed_create = {"sqlite_", "test_", "sqlite_autoindex_", "sqlite_stat_"}
    allowed_index_create = {"sqlite_autoindex_", "sqlite_stat_", "test_"}
    def authorizer(action, arg1, arg2, db_name, trigger):
        s = str(arg1 or "")
        # Acciones de transaccion / lectura general sin tabla (BEGIN, COMMIT, SAVEPOINT, FUNCTION)
        if action in (sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT, sqlite3.SQLITE_FUNCTION):
            return sqlite3.SQLITE_OK
        if s == "" and action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT):
            return sqlite3.SQLITE_OK
        # Allow internals unconditionally (sqlite_master, sqlite_sequence, sqlite_autoindex_*, sqlite_stat_*)
        if s.startswith("sqlite_") or s.startswith("sqlite_autoindex_") or s.startswith("sqlite_stat_"):
            return sqlite3.SQLITE_OK
        if s.startswith("test_"):
            # For test tables: SELECT and INSERT allowed; CREATE allowed; DENY UPDATE/DELETE/DROP/ALTER by default
            if action == sqlite3.SQLITE_SELECT:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_INSERT:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_CREATE_TABLE:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_CREATE_INDEX and ("sqlite_autoindex_" in s or s.startswith("test_")):
                return sqlite3.SQLITE_OK
            # Deny modification on test tables (defensive)
            if action in (sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_ALTER_TABLE):
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_DROP_TABLE:
                return sqlite3.SQLITE_DENY
            # Allow other read-only actions for test tables
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_OK
        # Deny everything else by default
        return sqlite3.SQLITE_DENY
    conn.set_authorizer(authorizer)

def init_test_db():
    if os.path.isfile(DB_TEST):
        os.remove(DB_TEST)
    con = sqlite3.connect(DB_TEST, isolation_level=None)
    set_policy(con)
    con.execute("CREATE TABLE IF NOT EXISTS test_authorizations (nonce TEXT PRIMARY KEY, payload_json TEXT, public_key_hex TEXT, timestamp_iso TEXT, valid_until_iso TEXT, revoked INTEGER DEFAULT 0)")
    con.execute("CREATE TABLE IF NOT EXISTS test_audit_log (event_json TEXT, prev_hash TEXT, hash TEXT, timestamp_iso TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS test_results (result_id TEXT PRIMARY KEY, operation_id TEXT, scope TEXT, manifest_path TEXT, hash_sha256 TEXT, authority_ref TEXT, decision TEXT, timestamp_iso TEXT)")
    con.commit(); con.close()
    _audit_write({"event": "DB_TEST_INIT",
                  "test_path": DB_TEST,
                  "policy": "PROTOTYPE_M316_ISOLATED",
                  "note": "DBOP_ACCESS_M295 NOT APPLIED; this is isolated proof only"})
    return DB_TEST
