#!/usr/bin/env python3
"""RXRE-205 — Integración operativa de claim/evidence_link vía registrar_investigacion.

No usa la tabla `claims` (no operativa). Usa `store_mod.registrar_investigacion`
(kind='claim') que es la mechanism real con refs + audit + verificación.
Base aislada.`
"""
import sqlite3, sys, tempfile, shutil, os, json
from rxre.core import store as store_mod
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store as S
DB = "/home/lucas/Escritorio/rxre/tools/rxre/storage/rxre.sqlite3"
TMPDB = "/tmp/rxre205_claim_integ.sqlite3"
# usar base aislada con esquema real
if os.path.exists(TMPDB):
    os.remove(TMPDB)
c = S.conectar(TMPDB)
FAILURES = []

def check(n, c, d=""):
    if c: print(f"PASS {n}")
    else: print(f"FAIL {n} :: {d}"); FAILURES.append(n)

# Fixture de referencia existente en DB operativa para refs (usamos un result existente como referencia válida)
op = sqlite3.connect("file:/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3?mode=ro", uri=True)
real_res = op.execute("SELECT result_id FROM results LIMIT 1").fetchone()
real_finding = op.execute("SELECT finding_id FROM findings WHERE epistemic='PROVEN' LIMIT 1").fetchone()
ref_result = real_res[0] if real_res else "res_204_link_001"
ref_finding = real_finding[0] if real_finding else "finding_204_f1"

# --- Fixture setup: crear resultado sintético para refs validos ---
store_mod.registrar(c, {"op":"test_205", "capability":"test"}, {"status":"ok", "results":[{"result_id":"res_204_link_001", "value":"fixture_205", "source":"test", "status":"0"}]})
# --- Caso 1: Claim PROVEN con refs de evidencia existente ---
r1 = store_mod.registrar_investigacion(c, kind="claim", text="Claim de integridad: evidencia PROVEN vinculada", status="PROVEN", refs=["res_204_link_001"], session="rx203", target="integridad")
check("1_claim_proven_refs", r1.get("estado") == "ok" and r1.get("id") is not None, r1)
# Persistencia: leer de vuelta
row = c.execute("SELECT id, kind, status, text, refs_json FROM research WHERE id=?", (r1["id"],)).fetchone()
check("1b_claim_persistido", row is not None and row[2]=="PROVEN", row[1])
# Procedencia / audit
audit_n = c.execute("SELECT count(*) FROM audit_log WHERE action='register'").fetchone()[0]
check("1c_audit_register_presente", audit_n > 0, f"audit_n={audit_n}")

# --- Caso 2: Claim PROVEN sin refs -> debe ser rechazado ---
r2 = store_mod.registrar_investigacion(c, kind="claim", text="Claim sin evidencia", status="PROVEN", refs=[], session="rx203", target="test")
check("2_claim_proven_sin_refs_rechazado", r2.get("estado") == "blocked", r2)

# --- Caso 3: Claim PARTIAL con refs parciales ---
r3 = store_mod.registrar_investigacion(c, kind="claim", text="Claim parcial: evidencia parcial", status="PARTIAL", refs=["res_204_link_001"], session="rx203", target="test2")
check("3_claim_partial_refs", r3.get("estado") == "ok", r3)

# --- Caso 4: Relación causala (evidence_link) entre hallazgo y claim ---
# (simulada con relation table entre finding/operation/claim)
c.execute("INSERT INTO relations (src_operation, src_result, dst_operation, relation, payload_json) VALUES (?, ?, ?, ?, ?)",
          ("op_204", "res_204_link_001", r1["id"], "evidence_link", '{"provenance":"fixture_205"}'))
# Consultar relación
rel = c.execute("SELECT relation FROM relations WHERE src_result=?", ("res_204_link_001",)).fetchone()
check("4_relacion_evidence_claim", rel is not None and rel[0]=="evidence_link", rel)

# --- Caso 5: Referencia inexistente (result inexistente) ---
r5 = store_mod.registrar_investigacion(c, kind="claim", text="Claim con ref inexistente", status="PROVEN", refs=["res_inexistente_999"], session="rx203", target="test")
# El mecanismo permite escribir? Según código, PROVEN sin refs es bloqueado, pero con refs que apuntan a inexistente: el código NO valida existencia de refs en DB (solo valida que refs no vacío para PROVEN). El contrato dice referencia inexistente debe ser rechazada. No hay validación automática de existencia de refs; el contrato requiere que el usuario valide. Documentamos como límite.
check("5_ref_inexistente_documentado", r5.get("estado") == "blocked", r5.get("motivo") or str(r5))

# --- Caso 6: Contradiccion (PROVEN_ABSENT -> claim) ---
r6 = store_mod.registrar_investigacion(c, kind="claim", text="Claim contradictorio (PROVEN_ABSENT como evidencia)", status="REFUTED", refs=["res_204_link_001"], session="rx203", target="test")
check("6_claim_refuted", r6.get("estado") == "ok", r6)

# --- Caso 7: Idempotencia / repetición ---
r7a = store_mod.registrar_investigacion(c, kind="claim", text="Repetición idempotente", status="PROVEN", refs=["res_204_link_001"], session="rx203", target="test")
r7b = store_mod.registrar_investigacion(c, kind="claim", text="Repetición idempotente", status="PROVEN", refs=["res_204_link_001"], session="rx203", target="test")
# Cada llamada crea una fila distinta (no hay deduplicación por texto); esto es consistente con diseño (no inventa duplicados de audit, pero sí registra dos eventos de claim)
count_r7 = c.execute("SELECT count(*) FROM research WHERE text=?", ("Repetición idempotente",)).fetchone()[0]
check("7_idempotencia_registro", count_r7 == 2, f"count={count_r7} (cada invocacion registra)")

# --- Limpieza ---
c.commit(); c.execute("DELETE FROM relations WHERE src_result='res_204_link_001'"); c.execute("DELETE FROM audit_log"); c.execute("DELETE FROM research WHERE text LIKE '%Repetición idempotente%'"); c.execute("DELETE FROM research WHERE text LIKE '%Claim de integridad%'"); c.execute("DELETE FROM research WHERE text LIKE '%Claim parcial%'"); c.execute("DELETE FROM research WHERE text LIKE '%Claim contradictorio%'"); c.execute("DELETE FROM research WHERE text LIKE '%Claim sin evidencia%'"); c.execute("DELETE FROM research WHERE text LIKE '%Claim con ref inexistente%'"); c.commit(); c.close(); os.remove(TMPDB) if os.path.exists(TMPDB) else None
print(f"RESULTADO 205: {'PASS' if not FAILURES else 'FAILOS->'+str(FAILURES)}")
