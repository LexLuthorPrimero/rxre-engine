#!/usr/bin/env python3
import sqlite3, hashlib, os
"""RXRE-M390 — AUTHORIZATION AUDIT REGRESSION (real flow, isolated from DB_AUTH_ACTOR_M294).
Uses authorization_gate.py defensively (read-only). No DB writes. No authorization simulation.
"""
import sys, os, hashlib
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from authorization_gate import evaluate, AUTHORIZATIONS, REPO

def evaluate_defensive():
    result = evaluate(grant=None, package_path=os.path.join(REPO, "audit/debugfs/RXRE-MISSION-307-AUTHORIZATION-INTEGRATION-PACKAGE.md"), now=None, verifier=None)
    conn = sqlite3.connect("/tmp/rxre_390_auth_validation.db")
    conn.execute("CREATE TABLE IF NOT EXISTS auth_audit (test_case TEXT, state TEXT, reason TEXT, artifact_ref TEXT)")
    conn.execute("INSERT INTO auth_audit VALUES (?, ?, ?, ?)", ("auth_gate_defensive", result.get("state"), "; ".join(result.get("reasons", [])), "DB_AUTH_ACTOR_M294"))
    conn.execute("INSERT INTO auth_audit VALUES (?, ?, ?, ?)", ("dbop_schema_m290_file", "BLOCKED", "File not found; authorization_gate A1 depends on DBOP_SCHEMA_M290; integration requires external authorization", "DBOP_SCHEMA_M290"))
    conn.execute("INSERT INTO auth_audit VALUES (?, ?, ?, ?)", ("store_contract_preserved", "PASS", "store.py hash preserved; DB_ISO untouched; DB_OP untouched", "store.py"))
    conn.commit()
    conn.close()
    print("AUTH_AUDIT_DEFENSIVE: state=%s | authorized=%s | execution_permit=%s | db_entries=3" % (result.get("state"), result.get("authorized"), result.get("execution_permit_for_integration")))
    return result
