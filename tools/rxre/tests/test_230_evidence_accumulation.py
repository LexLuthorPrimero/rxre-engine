#!/usr/bin/env python3
"""RXRE-MISSION-230 — Conservacion y acumulacion de evidencia en claim existente.

Perspectiva: la evidencia se comprueba RELEYENDO el estado persistido
(base aislada DB_ISO), no por los valores devueltos.
Usa interfaces reales: contracts.preintegracion_tierra.preintegrate_finding_to_tierra
-> adapters.adapter_finding_tierra.ejecutar_adaptador -> arquitectura.TIERRA.Grafo.
No escribe en la base operativa; no activa op:claim.
"""
import sys, os, sqlite3, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
from rxre.arquitectura import TIERRA

DB_ISO = "/tmp/rxre_230_iso.sqlite3"
OP_DB = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
FALLOS = []
TRAZA = []

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

def estado():
    """Relectura desde la base: claims, evidencia y referencias (no返回值)."""
    if not os.path.exists(DB_ISO):
        return {"claims": [], "evidence": []}
    c = sqlite3.connect(DB_ISO)
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]
        claims = c.execute("SELECT * FROM claims").fetchall()
        ev = c.execute("SELECT evidence_id, claim_id, kind, payload FROM evidence").fetchall()
        return {"claims": [dict(zip(cols, r)) for r in claims], "evidence": ev, "claims_cols": cols}
    finally:
        c.close()

def op_rows():
    c = sqlite3.connect(OP_DB)
    try:
        return tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone())
    finally:
        c.close()

def finding(stmt, oh, sc, eids, fid):
    return {"finding_id": fid, "statement": stmt, "epistemic": "PROVEN",
            "evidence_ids": eids, "falsification_test": "fixture_230_falsification",
            "object_hash": oh, "scope": sc, "contradiction_refs": []}

def pre(f, resolver=lambda r: True):
    TRAZA[:] = []
    g = TIERRA.Grafo(DB_ISO)
    g.db.set_trace_callback(lambda s: TRAZA.append(s))
    try:
        res = preintegrate_finding_to_tierra(DB_ISO, f, resolver_refs=resolver,
                                             contradiction_statements=None, explicit_enable=True)
    finally:
        g.db.set_trace_callback(None)
        g.db.close()
    return res

print("=== 230: acumulacion de evidencia en claim existente ===")
op_antes = op_rows()

# --- 1. Claim nuevo con evidencia inicial E1 ---
clean()
f1 = finding("stmt_230_A", "hash_230_A", "scope_230_A", ["fixture_230_E1"], "fixture_230_f1")
r1 = pre(f1)
st1 = estado()
ev1 = [e for e in st1["evidence"] if e[1] == r1.get("claim_id")]
ok(r1.get("status") == "ok", "1 claim nuevo -> ok", str(r1.get("claim_id"))[:16])
ok(len(st1["claims"]) == 1, "1b un claim persistido", "claims=%d" % len(st1["claims"]))
ok(len(ev1) >= 2, "1c evidencia persistida (observacion + artefacto E1)", "evidencias=%d" % len(ev1))
ok(any("fixture_230_E1" in str(e[3]) for e in ev1), "1d E1 presente en la evidencia persistida")
E1_EV = sorted(e[0] for e in ev1)
print("     evidencia inicial:", E1_EV)

# --- 2. Mismo claim (mismo statement/object_hash/scope) con evidencia ADICIONAL E2 ---
f2 = finding("stmt_230_A", "hash_230_A", "scope_230_A", ["fixture_230_E2"], "fixture_230_f2")
r2 = pre(f2)
st2 = estado()
ev2 = [e for e in st2["evidence"] if e[1] == r2.get("claim_id")]
ok(r2.get("claim_id") == r1.get("claim_id"), "2a mismo claim_id (identidad invariante)")
ok(r2.get("ya_existia") is True, "2b ya_existia=True", str(r2.get("ya_existia")))
n_ev2 = len(ev2)
ok(n_ev2 == len(ev1), "2c evidencia NO acumulada en la base (E2 no persistida)", "evidencia antes=%d despues=%d" % (len(ev1), n_ev2))
ok(not any("fixture_230_E2" in str(e[3]) for e in ev2), "2d E2 NO aparece en la evidencia persistida (no hay fusion)", "E2 presente=%s" % any("fixture_230_E2" in str(e[3]) for e in ev2))
ok(any("fixture_230_E1" in str(e[3]) for e in ev2), "2e E1 intacta (procedencia previa no sobrescrita)")
writes = [s for s in TRAZA if s.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT"))]
ok(not writes, "2f sin operaciones de escritura en la rama ya_existia", "ops=%d" % len(writes))

# --- 3. Repeticion de E2 (idempotencia) ---
r3 = pre(f2)
st3 = estado()
ev3 = [e for e in st3["evidence"] if e[1] == r3.get("claim_id")]
ok(len(ev3) == len(ev1), "3a repeticion E2 idempotente (sin cambio)", "evidencia=%d" % len(ev3))
ok(r3.get("ya_existia") is True, "3b ya_existia persistente")

# --- 4. Referencia inexistente con claim existente ---
# El adapter verifica refs ANTES de la rama ya_existia; con resolver=False rechaza.
# El claim existente no se altera.
f4 = finding("stmt_230_A", "hash_230_A", "scope_230_A", ["fixture_230_E9"], "fixture_230_f4")
r4 = pre(f4, resolver=lambda r: r == "fixture_230_E1")
ev4 = [e for e in estado()["evidence"] if e[1] == r1.get("claim_id")]
ok(r4.get("status") != "ok", "4a referencia no resoluble -> no aceptada", "status=%s" % r4.get("status"))
ok(len(ev4) == len(ev1), "4b evidencia original intacta tras rechazo", "evidencia=%d (antes=%d)" % (len(ev4), len(ev1)))

# --- 5. Segundo claim con distinto scope: evidencia no se cruza ---
f5 = finding("stmt_230_B", "hash_230_B", "scope_230_B", ["fixture_230_E3"], "fixture_230_f5")
r5 = pre(f5)
st5 = estado()
ev_a = [e for e in st5["evidence"] if e[1] == r1.get("claim_id")]
ev_b = [e for e in st5["evidence"] if e[1] == r5.get("claim_id")]
ok(r5.get("claim_id") != r1.get("claim_id"), "5a identidades distintas")
ok(all(e[1] == r1.get("claim_id") for e in ev_a), "5b evidencia de A solo en A")
ok(all(e[1] == r5.get("claim_id") for e in ev_b), "5c evidencia de B solo en B")
ok(any("fixture_230_E3" in str(e[3]) for e in ev_b), "5d E3 en su claim")
ok(not any("fixture_230_E3" in str(e[3]) for e in ev_a), "5e E3 no aparece en el claim A (sin cruce)")
ok(len(st5["claims"]) == 2, "5f dos claims persistidos", "claims=%d" % len(st5["claims"]))

# --- 6. Determinismo de identidad ---
f1b = finding("stmt_230_A", "hash_230_A", "scope_230_A", ["fixture_230_E1"], "fixture_230_f1")
r1b = pre(f1b)
ok(r1b.get("claim_id") == r1.get("claim_id"), "6a claim_id determinista")

# --- Integridad operativa ---
op_despues = op_rows()
ok(op_antes == op_despues, "DB operativa sin escrituras", "%s == %s" % (op_antes, op_despues))
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py",
          "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py",
          "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3",
          "/home/lucas/Escritorio/rxre/.rxre/gpu0/original"):
    ok(os.path.exists(p), "zona protegida presente: %s" % os.path.basename(p))

print("\n=== RESUMEN 230 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("230 OK")
