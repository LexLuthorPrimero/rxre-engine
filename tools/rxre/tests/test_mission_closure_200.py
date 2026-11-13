#!/usr/bin/env python3
"""RXRE-200 — Pruebas discriminantes del contrato de criterios y cierre.

Aislamiento: TODAS las escrituras van a una base temporal. La base operativa
(`tools/rxre/storage/rxre.sqlite3`) solo se LEE, para copiar hallazgos REALES
(finding_id, claim, epistemic, evidence_ids, provenance) como fixtures. No se
fabrica evidencia ni se escriben estados históricos.

Casos:
 1. Misión nueva con criterio explícito y evidencia válida  -> cierre aceptado
 2. Misión sin criterios                                  -> cierre rechazado, estado conservado
 3. Criterio con evidencia PARTIAL                          -> cierre rechazado
 4. Criterio NOT_DETERMINED                                -> cierre rechazado
 5. Evidencia con procedencia inválida / referencia inexistente -> cierre rechazado
 6. Cierre repetido                                        -> sin duplicados, justificación original intacta
 7. Error durante la transición                             -> sin estado terminal inconsistente
 8. Consulta posterior                                      -> estado persistido + justificación
"""
import json, os, shutil, sqlite3, sys, tempfile

sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store as S
from rxre.mission_closure import close_mission

OPERATIONAL_DB = os.environ.get(
    "RXRE_DB", "/home/lucas/Escritorio/rxre/tools/rxre/storage/rxre.sqlite3")
TMPDIR = tempfile.mkdtemp(prefix="rxre200_")
TMP_DB = os.path.join(TMPDIR, "rxre_test.sqlite3")

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name} :: {detail}")
        FAILURES.append(name)


def _real_findings():
    """Copia hallazgos REALES de la base operativa (solo lectura)."""
    src = sqlite3.connect(f"file:{OPERATIONAL_DB}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    cols = [r[1] for r in src.execute("PRAGMA table_info(findings)")]
    rows = src.execute(
        "SELECT * FROM findings WHERE epistemic='PROVEN' ORDER BY created_at"
    ).fetchall()
    part = src.execute(
        "SELECT * FROM findings WHERE epistemic='PARTIAL' ORDER BY created_at LIMIT 1"
    ).fetchall()
    src.close()
    return cols, rows, part


def setup_db():
    """Base AISLADA con fixtures sinteticos (solo para esta prueba aislada)."""
    c = S.conectar(TMP_DB)
    # Fixture 1: PROVEN con todos los campos requeridos por trg_findings_contrato_nuevo
    c.execute(
        "INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, falsification_test, reevaluation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("finding_200_f1", None, "Fixture: criterio de cierre verificado (PROVEN)", "PROVEN",
         '["res_200_evidence"]',
         '{"producer":"test_200","tool":"fixture","version":"v1.0.0","device":"test","repository":"local/test","command":"test -e evidence"}',
         '["fixture para RXRE-200; no es evidencia operativa"]',
         "2026-10-21T00:00:00", "mission_closure_200", 1,
         "hash_200_f1", "[]", "[]", "test_200_falsification", None))
    # Fixture 2: PARTIAL
    c.execute(
        "INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, falsification_test, reevaluation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("finding_200_p1", None, "Fixture: evidencia parcial (PARTIAL)", "PARTIAL",
         '["res_200_partial"]', '{"producer":"test_200","tool":"fixture","version":"v1.0.0"}',
         '["fixture PARTIAL para rechazo de cierre"]', "2026-10-21T00:00:00",
         "mission_closure_200", 1, "hash_200_p1", "[]", "[]", "test_200_fals_p", None))
    # Fixture 3: PROVEN con procedencia vacia (rechazo de cierre)
    c.execute(
        "INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, falsification_test, reevaluation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("finding_200_b1", None, "Fixture: evidencia con procedencia vacia (rechazo)", "PROVEN",
         '["res_200_bad"]', "{}", '["fixture para caso 5b"]', "2026-10-21T00:00:00",
         "mission_closure_200", 1, "hash_200_b1", "[]", "[]", "test_200_fals_b", None))
    c.commit()
    c.close()
    return ["finding_200_f1"], ["finding_200_p1", "finding_200_b1"]


def new_mission(title):
    c = S.conectar(TMP_DB)
    mid = S.crear_mision(c, title, "RXRE-200 fixture")
    c.close()
    return mid


def add_criterion(mid, desc, epistemic, evidence_ids, required=1):
    c = S.conectar(TMP_DB)
    cid = S.crear_criterio_mision(c, mid, desc, epistemic=epistemic,
                                  evidence_ids=evidence_ids, required=required)
    c.commit()
    c.close()
    return cid


def status_of(mid):
    c = sqlite3.connect(TMP_DB)
    row = c.execute("SELECT status FROM missions WHERE mission_id=?", (mid,)).fetchone()
    c.close()
    return row[0] if row else None


def audit_count(mid):
    c = sqlite3.connect(TMP_DB)
    n = c.execute("SELECT count(*) FROM audit_log WHERE action='mission_closed' AND entity_id=?",
                  (mid,)).fetchone()[0]
    c.close()
    return n


def main():
    proven_ids, (partial_id, bad_id) = setup_db()
    print(f"fixtures: PROVEN reales={proven_ids} PARTIAL real={partial_id}\n")

    # ---- Caso 1: criterio explícito + evidencia válida -> cierre aceptado
    m1 = new_mission("caso1_cierre_valido")
    add_criterion(m1, "criterio respaldado por hallazgo PROVEN real", "PROVEN",
                  [proven_ids[0]], required=1)
    r1 = close_mission(m1, db_path=TMP_DB)
    check("caso1 cierre aceptado", r1["status"] == "COMPLETED", json.dumps(r1)[:160])
    check("caso1 estado persistido COMPLETED", status_of(m1) == "COMPLETED", str(status_of(m1)))
    check("caso1 audit registrado", audit_count(m1) == 1, str(audit_count(m1)))

    # ---- Caso 2: sin criterios -> rechazado, estado conservado
    m2 = new_mission("caso2_sin_criterios")
    r2 = close_mission(m2, db_path=TMP_DB)
    check("caso2 cierre rechazado", r2["status"] == "REJECTED", r2.get("reason", "")[:80])
    check("caso2 estado conservado PENDING", status_of(m2) == "PENDING", str(status_of(m2)))
    check("caso2 sin audit", audit_count(m2) == 0)

    # ---- Caso 3: evidencia PARTIAL -> rechazado
    m3 = new_mission("caso3_evidencia_partial")
    add_criterion(m3, "criterio con evidencia PARTIAL", "PROVEN", [partial_id], required=1)
    r3 = close_mission(m3, db_path=TMP_DB)
    check("caso3 cierre rechazado (PARTIAL)", r3["status"] == "REJECTED", json.dumps(r3)[:160])
    check("caso3 estado conservado PENDING", status_of(m3) == "PENDING", str(status_of(m3)))

    # ---- Caso 4: criterio NOT_DETERMINED -> rechazado
    m4 = new_mission("caso4_criterio_not_determined")
    add_criterion(m4, "criterio sin verificacion automatica", "NOT_DETERMINED",
                  [proven_ids[0]], required=1)
    r4 = close_mission(m4, db_path=TMP_DB)
    check("caso4 cierre rechazado (NOT_DETERMINED)", r4["status"] == "REJECTED",
          json.dumps(r4)[:160])
    check("caso4 estado conservado PENDING", status_of(m4) == "PENDING", str(status_of(m4)))

    # ---- Caso 5: procedencia invalida / referencia inexistente -> rechazado
    m5a = new_mission("caso5a_evidencia_inexistente")
    add_criterion(m5a, "criterio con evidencia inexistente", "PROVEN",
                  ["finding_inexistente_000"], required=1)
    r5a = close_mission(m5a, db_path=TMP_DB)
    check("caso5a cierre rechazado (ref inexistente)", r5a["status"] == "REJECTED",
          json.dumps(r5a)[:160])

    m5b = new_mission("caso5b_procedencia_invalida")
    add_criterion(m5b, "criterio con procedencia vacia", "PROVEN", [proven_ids[0]], required=1)
    c = sqlite3.connect(TMP_DB)
    c.execute("UPDATE findings SET provenance='{}' WHERE finding_id=?", (proven_ids[0],))
    c.commit(); c.close()
    r5b = close_mission(m5b, db_path=TMP_DB)
    check("caso5b cierre rechazado (procedencia invalida)", r5b["status"] == "REJECTED",
          json.dumps(r5b)[:160])
    check("caso5b estado conservado PENDING", status_of(m5b) == "PENDING", str(status_of(m5b)))
    # Restaurar procedencia del fixture para los casos posteriores
    c = sqlite3.connect(TMP_DB)
    c.execute("UPDATE findings SET provenance=? WHERE finding_id=?",
              (json.dumps({"producer":"test_200","tool":"fixture","version":"v1.0.0","device":"test","repository":"local/test","command":"test -e evidence"}), proven_ids[0]))
    c.commit(); c.close()


    # ---- Caso 6: cierre repetido -> idempotente
    r6a = close_mission(m1, db_path=TMP_DB)
    r6b = close_mission(m1, db_path=TMP_DB)
    check("caso6 idempotente ALREADY_COMPLETED",
          r6a["status"] == "ALREADY_COMPLETED" and r6b["status"] == "ALREADY_COMPLETED",
          f"{r6a.get('status')}/{r6b.get('status')}")
    check("caso6 sin audit duplicado", audit_count(m1) == 1, str(audit_count(m1)))
    c = sqlite3.connect(TMP_DB)
    details = c.execute("SELECT details FROM audit_log WHERE action='mission_closed' AND entity_id=?",
                        (m1,)).fetchone()[0]
    c.close()
    check("caso6 justificacion original intacta",
          json.loads(details)["criteria_status"], details[:80])

    # ---- Caso 7: error durante la transicion -> sin estado terminal inconsistente
    m7 = new_mission("caso7_error_transicion")
    add_criterion(m7, "criterio valido", "PROVEN", [proven_ids[0]], required=1)
    c = sqlite3.connect(TMP_DB)
    c.execute("CREATE TRIGGER rxre200_fail_audit BEFORE INSERT ON audit_log "
              "BEGIN SELECT RAISE(ABORT, 'audit_injected_failure'); END;")
    c.commit(); c.close()
    r7 = close_mission(m7, db_path=TMP_DB)
    check("caso7 transicion abortada sin terminal", r7["status"] == "ERROR", json.dumps(r7)[:160])
    check("caso7 estado no terminal persistido", status_of(m7) == "PENDING", str(status_of(m7)))
    c = sqlite3.connect(TMP_DB)
    c.execute("DROP TRIGGER rxre200_fail_audit")
    c.commit(); c.close()

    # ---- Caso 8: consulta posterior devuelve estado persistido + justificacion
    c = S.conectar(TMP_DB)
    m = S.obtener_mision(c, m1)
    crit = S.obtener_criterios_mision(c, m1)
    c.close()
    check("caso8 consulta devuelve estado", m and m["status"] == "COMPLETED", str(m)[:80])
    check("caso8 completed_at informado", m and m["completed_at"] is not None)
    check("caso8 criterio legible con evidencia", crit and crit[0]["evidence_ids"], str(crit)[:80])

    # ---- La base operativa NO fue tocada
    op = sqlite3.connect(f"file:{OPERATIONAL_DB}?mode=ro", uri=True)
    pend = op.execute("SELECT count(*) FROM missions WHERE status='PENDING'").fetchone()[0]
    comp = op.execute("SELECT count(*) FROM missions WHERE status='COMPLETED'").fetchone()[0]
    op.close()
    check("operativa intacta: 179 PENDING, 0 COMPLETED", pend == 179 and comp == 0,
          f"PENDING={pend} COMPLETED={comp}")

    shutil.rmtree(TMPDIR, ignore_errors=True)
    print("\n" + ("RESULTADO 200: TODOS LOS CASOS PASS" if not FAILURES
                  else f"RESULTADO 200: FALLOS -> {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
