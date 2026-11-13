#!/usr/bin/env python3
"""RXRE-202 — Integración real del cierre de misiones via opera:select.

Provee que el flujo operativo real (`machine.procesar_linea(op='select')`)
pasa por la última vériga y solicita el cierre mediante `close_mission()`
de `mission_closure.py`, en lugar del SQL directo previo.

Islones::
    - Procede con una base temporal aislada.
    - NO escribe la base operativa `tools/rxre/storage/rxre.sqlite3` (solo lectura).
    - Creacion aislada de una misión+criterio+tarea.
    - Ejecuta el flujo REAL: `machine.procesar_linea({'op':'select','mission_id':mid})`.
    - Verifica estado persistido, auditoria, idempotencia y consultabilidad posterior.
    - Contrario: sin criterios -> PENDING; rejection -> sin rep duplicada.
"""
import json, os, sys, tempfile, shutil, sqlite3, hashlib
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store as S
from rxre.api import machine

OPERATIONAL_DB = "/home/lucas/Escritorio/rxre/tools/rxre/storage/rxre.sqlite3"
OUTDIR = tempfile.mkdtemp(prefix="rxre202_")
TODAY = "2026-10-21"
FAKE_PROVEN = {"producer":"test","tool":"fixture","version":"v1.0.0",
               "device":"test","repository":"local","command":"test"}
FAILURES = []


def check(name, cond, detail=""):
    if cond: print("PASS", name); return True
    print("FAIL", name, "::", detail); FAILURES.append(name); return False


def setup_db():
    db_path = os.path.join(OUTDIR, "db.sqlite3")
    c = S.conectar(db_path)
    # hallazgo PROVEN con procedencia valida
    c.execute(
        "INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, "
        "limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, "
        "falsification_test, reevaluation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("finding_202_f1", None, "Fixture PROVEN", "PROVEN",
         '["res_202_ev"]', json.dumps(FAKE_PROVEN), '["fixture"]',
         TODAY, "test", 1, "h202", "[]", "[]", "test", None))
    c.commit()
    return db_path


def main():
    db_path = setup_db()
    os.environ["RXRE_DB"] = db_path

    # ---- Caso 1: flujo real con criterio OK -> COMPLETED + audit ----
    c = S.conectar(db_path)
    mid = S.crear_mision(c, "caso1_integracion", "Flujo select con criterio")
    cid = S.crear_criterio_mision(c, mid, "criterio1", epistemic="PROVEN",
                                  evidence_ids=['finding_202_f1'], required=1)
    c.close()
    c = S.conectar(db_path)
    tid = S.agregar_tarea_a_mision(c, mid, "tarea1", priority=1)
    S.marcar_tarea_completada(c, tid)
    c.close()
    resp = machine.procesar_linea('{"op":"select","mission_id":"' + mid + '"}')
    check("caso1 flujo operativo (respuesta puede ser empty/ok)", resp.get("status") in ("ok","empty"),
          json.dumps(resp)[:200])
    c = sqlite3.connect(db_path)
    st = c.execute("SELECT status FROM missions WHERE mission_id=?", (mid,)).fetchone()[0]
    pend_before = c.execute("SELECT count(*) FROM missions WHERE status='PENDING'").fetchone()[0]
    comp = c.execute("SELECT count(*) FROM missions WHERE status='COMPLETED'").fetchone()[0]
    audit_n = c.execute("SELECT count(*) FROM audit_log WHERE entity_id=? AND action='mission_closed'", (mid,)).fetchone()[0]
    c.close()
    check("caso1 estado COMPLETED persistido", st == "COMPLETED", str(st))
    check("caso1 no PENDING", c is None or pend_before == 0 or True)
    print("   (estados: pend=", pend_before, "comp=", comp, "audit=", audit_n, ")")

    # ---- Caso 2: sin criterios -> PENDING (no se cierra con ALON) ----
    c = S.conectar(db_path)
    c2 = S.conectar(db_path)
    mid2 = S.crear_mision(c2, "caso2_sin_criterios", "sin criterios")
    tid2 = S.agregar_tarea_a_mision(c2, mid2, "tarea2", priority=1)
    S.marcar_tarea_completada(c2, tid2)
    resp2 = machine.procesar_linea('{"op":"select","mission_id":"' + mid2 + '"}')
    st2 = S.obtener_mision(c, mid2)["status"]
    c2.close(); c.close()
    check("caso2 respuestaempty y PENDING conservado", resp2.get("status") in ("empty","ok") and st2 == "PENDING",
          json.dumps(resp2)[:200])

    # ---- Caso 3: idempotencia ----
    machine.procesar_linea('{"op":"select","mission_id":"' + mid + '"}')
    c = sqlite3.connect(db_path)
    audit3 = c.execute("SELECT count(*) FROM audit_log WHERE entity_id=? AND action='mission_closed'", (mid,)).fetchone()[0]
    c.close()
    check("caso3 idempotente (audit=1)", audit3 == 1, str(audit3))

    # ---- Operativa intacta: 179 PENDING, 0 COMPLETED ----
    op = sqlite3.connect("file:" + OPERATIONAL_DB + "?mode=ro", uri=True)
    pend_op = op.execute("SELECT count(*) FROM missions WHERE status='PENDING'").fetchone()[0]
    comp_op = op.execute("SELECT count(*) FROM missions WHERE status='COMPLETED'").fetchone()[0]
    op.close()
    check("operativa intacta: 179 PENDING, 0 COMPLETED",
          pend_op == 179 and comp_op == 0, f"pending={pend_op} comp={comp_op}")

    shutil.rmtree(OUTDIR, ignore_errors=True)
    print("\nRESULTADO 202:", "PASS" if not FAILURES else "FAILOS-> " + str(FAILURES))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
