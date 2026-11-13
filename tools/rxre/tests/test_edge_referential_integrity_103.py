#!/usr/bin/env python3
"""TEST 103 — referential integrity of anadir_edge() after RXRE-EDGE-REFERENTIAL-INTEGRITY-103.

Validates:
- Both endpoints exist -> insert succeeds (True)
- Duplicate -> idempotent (same count, no extra row)
- Nonexistent src -> rejected (False), no phantom row
- Nonexistent dst -> rejected (False), no phantom row
- Both nonexistent -> rejected (False)
- Claim status preserved (PROVEN / NOT_DETERMINED) after insertion
- relations() recovers the valid relation
- Persistence after close/reopen (temporary DB)

No production DB or protected storage modified.
"""
import sys, os, sqlite3, hashlib, tempfile, json

sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools/rxre")
from core.store import (conectar, anadir_edge, relations, registrar,
                        registrar_investigacion)

EV_A = "/tmp/obs_102/evidence_A_102.txt"
EV_B = "/tmp/obs_102/evidence_B_102.txt"
HASH_A = "09d4b350296a982cd4db65f42a367dcc30f85669044f8989907fb3a7fbc3cc1c"
HASH_B = "f64c88f6f34f7766fcc2c9fc6555e7d6ed99488a7965900276a9eece3f7cb387"


def main():
    db = tempfile.mktemp(prefix="rxre_edge_103_") + ".sqlite3"
    c = conectar(db)

    # Register one operation with two results (real path: store.registrar)
    op_id = registrar(
        c,
        {"request_id": "req_103", "capability": "rxre"},
        {"operation": "test_edge_integrity", "status": "ok", "persistido": True,
         "results": [
             {"result_id": "res_103_ev_A", "type": "EVIDENCE",
              "value": "evidence A", "status": "PROVEN", "tool": "test",
              "location": {"file": EV_A, "line": 1},
              "raw_json": {"sha256_file_ref": HASH_A, "artefacto_path": EV_A}},
             {"result_id": "res_103_ev_B", "type": "EVIDENCE",
              "value": "evidence B", "status": "PROVEN", "tool": "test",
              "location": {"file": EV_B, "line": 1},
              "raw_json": {"sha256_file_ref": HASH_B, "artefacto_path": EV_B}},
         ]},
        duracion=0.0)
    print(f"[SETUP] operation_id={op_id} (2 results registrados)")

    checks = []

    # T1: valid, both endpoints exist
    r = anadir_edge(c, "res_103_ev_A", "evidence_to_claim", "res_103_ev_B",
                    status="observed", scope="rx550", tool="test",
                    evidence={"sha256_file_ref": HASH_A},
                    operation_id="", result_id="")
    n = c.execute("SELECT COUNT(*) FROM edges WHERE src='res_103_ev_A' AND dst='res_103_ev_B'").fetchone()[0]
    checks.append(("T1 valid both endpoints accepted", r is True and n == 1))

    # T2: duplicate keeps idempotency
    r = anadir_edge(c, "res_103_ev_A", "evidence_to_claim", "res_103_ev_B",
                    status="observed", scope="rx550", tool="test",
                    evidence={"sha256_file_ref": HASH_A},
                    operation_id="", result_id="")
    n = c.execute("SELECT COUNT(*) FROM edges WHERE src='res_103_ev_A' AND dst='res_103_ev_B' AND tipo='evidence_to_claim'").fetchone()[0]
    checks.append(("T2 duplicate idempotent (no extra row)", r is True and n == 1))

    # T3: nonexistent src
    r = anadir_edge(c, "res_INEXISTENTE_103_X", "evidence_to_claim", "res_103_ev_A->claim_v2",
                    status="observed", scope="rx550", tool="test", evidence={},
                    operation_id="", result_id="")
    n = c.execute("SELECT COUNT(*) FROM edges WHERE src='res_INEXISTENTE_103_X'").fetchone()[0]
    checks.append(("T3 nonexistent src rejected, no phantom row", r is False and n == 0))

    # T4: nonexistent dst
    r = anadir_edge(c, "res_103_ev_A", "evidence_to_claim", "res_INEXISTENTE_103_DST",
                    status="observed", scope="rx550", tool="test", evidence={},
                    operation_id="", result_id="")
    n = c.execute("SELECT COUNT(*) FROM edges WHERE dst='res_INEXISTENTE_103_DST'").fetchone()[0]
    checks.append(("T4 nonexistent dst rejected, no phantom row", r is False and n == 0))

    # T5: both nonexistent
    r = anadir_edge(c, "res_X_103", "evidence_to_claim", "res_Y_103",
                    status="observed", scope="rx550", tool="test", evidence={},
                    operation_id="", result_id="")
    n = c.execute("SELECT COUNT(*) FROM edges WHERE src='res_X_103'").fetchone()[0]
    checks.append(("T5 both nonexistent rejected", r is False and n == 0))

    # T6: epistemic states preserved
    registrar_investigacion(c, kind="claim", text="test claim PROVEN",
                            status="PROVEN", refs=["res_103_ev_A"],
                            session="rxre-103", target="rx550", gap_kind="")
    registrar_investigacion(c, kind="hypothesis", text="test hypothesis ND",
                            status="NOT_DETERMINED", refs=["res_103_ev_B"],
                            session="rxre-103", target="rx550",
                            gap_kind="HUECO_DE_EVIDENCIA")
    claim_status = c.execute("SELECT status FROM research WHERE text LIKE '%test claim PROVEN%' ORDER BY id DESC LIMIT 1").fetchone()[0]
    hyp_status = c.execute("SELECT status FROM research WHERE text LIKE '%test hypothesis ND%' ORDER BY id DESC LIMIT 1").fetchone()[0]
    checks.append(("T6 epistemic states preserved (PROVEN / NOT_DETERMINED)",
                   claim_status == "PROVEN" and hyp_status == "NOT_DETERMINED"))

    # T7: relations() recovers the valid relation and does not show the rejected ones
    rel = relations(c, src="res_103_ev_A", tipo="evidence_to_claim")
    rel_bad = relations(c, src="res_INEXISTENTE_103_X", tipo="evidence_to_claim")
    checks.append(("T7 relations() recovers valid, hides rejected",
                   rel["status"] == "ok" and rel["citables"] >= 1
                   and rel_bad["status"] == "empty" and rel_bad["results"] == []))

    # T9: derived claim label (starts with res_ but not exact ref) => rejected (limitación 103)
    r9 = anadir_edge(c, "res_103_ev_A", "evidence_to_claim", "res_103_ev_A->claim",
                     status="observed", scope="rx550", tool="t", evidence={"sha256_file_ref": HASH_A},
                     operation_id="", result_id="")
    n9 = c.execute("SELECT COUNT(*) FROM edges WHERE dst='res_103_ev_A->claim'").fetchone()[0]
    checks.append(("T9 derived label rejected (documented limitation)", r9 is False and n9 == 0))

    # T10: domain nodes (real consumer usage) => accepted (regression guard)
    r10 = anadir_edge(c, "VM_CONTEXT0_CNTL", "writes", "gfx_v8_0.c:1234",
                      status="observed", scope="rx550", tool="t", evidence={},
                      operation_id="", result_id="")
    checks.append(("T10 domain node edge accepted (test_field005/test_rxre002)", r10 is True))

    # T8: persistence after close/reopen
    c.close()
    c2 = sqlite3.connect(db)
    c2.row_factory = sqlite3.Row
    n = c2.execute("SELECT COUNT(*) FROM edges WHERE src='res_103_ev_A' AND dst='res_103_ev_B' AND tipo='evidence_to_claim'").fetchone()[0]
    nbad = c2.execute("SELECT COUNT(*) FROM edges WHERE src IN ('res_INEXISTENTE_103_X','res_X_103') OR dst IN ('res_INEXISTENTE_103_DST','res_Y_103')").fetchone()[0]
    c2.close()
    checks.append(("T8 persistence after reopen (valid=1, phantom=0)", n == 1 and nbad == 0))

    for label, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {label}")
    if all(p for _, p in checks):
        print("\n=== ALL 103 TESTS PASSED ===")
    else:
        print("\n=== SOME FAILURES ===")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
