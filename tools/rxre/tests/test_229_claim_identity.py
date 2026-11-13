#!/usr/bin/env python3
"""RXRE-MISSION-229 — Matriz adversarial de identidad y duplicacion (DB aislada).

Usa interfaces REALES: adapter_finding_tierra.claim_id_de,
contracts.preintegracion_tierra.preintegrate_finding_to_tierra,
contracts.conflict_policy.politica_conflicto_claims.
No escribe en la base operativa; no activa op:claim.
"""
import sys, os, sqlite3
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.adapters.adapter_finding_tierra import claim_id_de
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
from rxre.contracts.conflict_policy import politica_conflicto_claims

DB_ISO = "/tmp/rxre_229_iso.sqlite3"
OP_DB = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
FALLOS = []
RESPUESTAS = []

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def clean():
    for s in ("", "-wal", "-shm"):
        p = DB_ISO + s
        if os.path.exists(p):
            os.remove(p)

def tabla(nombre):
    if not os.path.exists(DB_ISO):
        return 0, 0
    c = sqlite3.connect(DB_ISO)
    try:
        claims = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        try:
            ev = c.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
        except sqlite3.Error:
            ev = -1
        return claims, ev
    finally:
        c.close()

def op_rows():
    c = sqlite3.connect(OP_DB)
    try:
        return tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone())
    finally:
        c.close()

def finding(stmt, oh, sc, eids, ctrefs=None, fid=None):
    return {"finding_id": fid or ("fixture_229_" + stmt[:12]),
            "statement": stmt, "epistemic": "PROVEN",
            "evidence_ids": eids, "falsification_test": "fixture_229_falsification",
            "object_hash": oh, "scope": sc, "contradiction_refs": ctrefs or []}

def pre(f, resolver=lambda r: True, ctrs=None):
    return preintegrate_finding_to_tierra(DB_ISO, f, resolver_refs=resolver,
                                         contradiction_statements=ctrs, explicit_enable=True)

print("=== 229: matriz de identidad de claims (entorno aislado) ===")
op_antes = op_rows()

# --- M1: mismo statement + misma evidencia + mismo alcance ---
clean()
f1 = finding("stmt_229_M1", "hash_229_M1", "scope_229_M1", ["fixture_229_ref_M1"])
r1 = pre(f1)
r1b = pre(f1)
n1, e1 = tabla(DB_ISO)
ok(r1.get("status") == "ok" and r1b.get("status") == "ok", "M1 dos Tehran identicos -> ok", str(r1.get("claim_id"))[:14])
ok(r1.get("claim_id") == r1b.get("claim_id"), "M1b claim_id identico (misma identidad)")
ok(n1 == 1, "M1c un solo claim persistido", "claims=%d" % n1)
ok(r1b.get("ya_existia") is True, "M1d segunda invocacion: ya_existia=True", str(r1b.get("ya_existia")))
RESPUESTAS.append(("M1", "SAME_CLAIM", r1.get("claim_id"), n1, e1))

# --- M2: mismo statement, distinto object_hash ---
f2 = finding("stmt_229_M2", "hash_229_M2", "scope_229_M1", ["fixture_229_ref_M1"])
r2 = pre(f2)
n2, e2 = tabla(DB_ISO)
ok(r2.get("claim_id") != r1.get("claim_id"), "M2 distinto object_hash -> identidad distinta")
ok(n2 == 2, "M2b dos claims persistidos", "claims=%d" % n2)
RESPUESTAS.append(("M2", "DISTINCT_CLAIMS", r2.get("claim_id"), n2, e2))

# --- M3: mismo statement, distinto scope ---
f3 = finding("stmt_229_M3", "hash_229_M1", "scope_229_otro", ["fixture_229_ref_M1"])
r3 = pre(f3)
n3, e3 = tabla(DB_ISO)
ok(r3.get("claim_id") != r1.get("claim_id"), "M3 distinto scope -> identidad distinta")
ok(n3 == 3, "M3b tres claims persistidos", "claims=%d" % n3)
RESPUESTAS.append(("M3", "DISTINCT_CLAIMS", r3.get("claim_id"), n3, e3))

# --- M4: mismo statement, misma hash/scope, distinta procedencia (otra evidencia) ---
f4 = finding("stmt_229_M1", "hash_229_M1", "scope_229_M1", ["fixture_229_ref_M2"])
r4 = pre(f4)
n4, e4 = tabla(DB_ISO)
ok(r4.get("claim_id") == r1.get("claim_id"), "M4 distinta procedencia -> misma identidad (claim_id no depende de refs)")
ok(n4 == 3, "M4b no se crea claim nuevo", "claims=%d" % n4)
ok(e4 >= e1, "M4c evidencia de la segunda procedencia conservada (no se borra)", "evidencia=%d (antes=%d)" % (e4, e1))
RESPUESTAS.append(("M4", "SAME_CLAIM", r4.get("claim_id"), n4, e4))

# --- M5: statement distinto, evidencia compartida ---
f5 = finding("stmt_229_M5", "hash_229_M1", "scope_229_M1", ["fixture_229_ref_M1"])
r5 = pre(f5)
n5, e5 = tabla(DB_ISO)
ok(r5.get("claim_id") != r1.get("claim_id"), "M5 statement distinto -> identidad distinta")
ok(n5 == 4, "M5b claims separados", "claims=%d" % n5)
RESPUESTAS.append(("M5", "DISTINCT_CLAIMS", r5.get("claim_id"), n5, e5))

# --- M6: declaraciones potencialmente contradictorias sin referencias mutuas verificables ---
ca = {"claim_id":"fixture_229_ca","scope":"scope_229_M1","statement":"stmt_229_M1","object_hash":"hash_229_M1",
      "contradiction_refs":["fixture_229_inexistente"],"contradiction_statements":["afirmacion opuesta"]}
cb = {"claim_id":"fixture_229_cb","scope":"scope_229_M1","statement":"stmt_229_CB","object_hash":"hash_229_M1",
      "contradiction_refs":["fixture_229_inexistente"],"contradiction_statements":["afirmacion opuesta"]}
pol = politica_conflicto_claims(ca, cb, resolver_refs=lambda r: False, contradicciones=None)
ok(pol.get("clasificacion") != "CONFLICT", "M6 declaraciones mutuas no verificables -> NO CONFLICT", str(pol.get("clasificacion")))
RESPUESTAS.append(("M6", "INDETERMINATE", pol.get("clasificacion"), n5, e5))

# --- M7: referencias vacias / ausentes / no resolubles ---
clean()
f7 = finding("stmt_229_M7", "hash_229_M7", "scope_229_M7", [])
r7 = pre(f7, resolver=lambda r: False)
n7, e7 = tabla(DB_ISO)
ok(r7.get("status") != "ok" or n7 == 0, "M7 refs no resolubles -> sin claim persistido", "status=%s claims=%d" % (r7.get("status"), n7))
# M7b: statement ausente
f7b = {"finding_id": "fixture_229_m7b", "epistemic": "PROVEN", "evidence_ids": ["x"], "object_hash": "h", "scope": "s"}
r7b = pre(f7b)
ok(r7b.get("status") != "ok", "M7b statement ausente -> no persistido", str(r7b.get("status")))
RESPUESTAS.append(("M7", "NO_PERSIST", r7.get("status"), n7, e7))

# --- Integridad operativa y zonas protegidas ---
op_despues = op_rows()
ok(op_antes == op_despues, "DB operativa sin escrituras", "%s == %s" % (op_antes, op_despues))
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py",
          "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py",
          "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3",
          "/home/lucas/Escritorio/rxre/.rxre/gpu0/original"):
    ok(os.path.exists(p), "zona protegida presente: %s" % os.path.basename(p))

print("\n=== RESUMEN 229 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
for row in RESPUESTAS:
    print("  %s -> %s (%s) claims=%s evidencia=%s" % row)
if FALLOS:
    sys.exit(1)
print("229 OK")
