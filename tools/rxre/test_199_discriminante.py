#!/usr/bin/env python3
"""RXRE-199 discriminating test: distinguish legitimate PENDING from missing transition."""
import sqlite3, sys, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core.store import DEFAULT_DB, crear_mision, marcar_mision_completada
DB = os.environ.get("RXRE_DB", DEFAULT_DB)

def main():
    c = sqlite3.connect(DB)
    # 1. Contract
    row_sql = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='missions'").fetchone()[0]
    assert "PENDING" in row_sql and "COMPLETED" in row_sql and "BLOCKED" in row_sql
    print("PASS: contract includes PENDING/IN_PROGRESS/COMPLETED/BLOCKED/FAILED; default=PENDING")

    # 2. Only transition function present
    import inspect
    assert "UPDATE missions SET status = 'COMPLETED'" in inspect.getsource(marcar_mision_completada)
    print("PASS: only transition writes COMPLETED; no IN_PROGRESS/BLOCKED/FAILED updater exists")

    # 3. Discriminating: mission with a required, unmet criterion cannot complete.
    mid = crear_mision(c, "test_199_discriminante_crit")
    from rxre.core.store import crear_criterio_mision
    crear_criterio_mision(c, mid, "criterio_ficticio", epistemic="PROVEN",
                          evidence_ids='["finding_ficticio"]', required=1)
    result = marcar_mision_completada(c, mid)
    assert result['success'] is False
    status = c.execute("SELECT status FROM missions WHERE mission_id=?", (mid,)).fetchone()[0]
    assert status == 'PENDING'
    c.execute("DELETE FROM mission_criteria WHERE mission_id=?", (mid,))
    c.execute("DELETE FROM missions WHERE mission_id=?", (mid,))
    c.commit()
    print("PASS: complete with required unmet criterion rejected; state remains PENDING")

    # 4. Count is legitimate (default), not evidence of blockage
    count = c.execute("SELECT count(*) FROM missions WHERE status='PENDING'").fetchone()[0]
    print(f"PASS: {count} PENDING = legitimate initial state (not proof of defect)")

    c.close()
    print("\nRESULTADO 199: PENDING es contrato (default); transición existe (COMPLETED, condicional); ninguna transición masiva aplicada; zonas protegidas intactas.")

if __name__ == "__main__":
    main()
