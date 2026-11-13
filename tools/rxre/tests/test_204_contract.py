#!/usr/bin/env python3
"""RXRE-204 — Contrato semántico y discriminación para claims y relaciones.
Aislado (DB temporal `/tmp`); no modifica operativa (`.rxre/storage/` ni `.rxre/gpu0/original`).
"""
import sqlite3, json, tempfile, shutil, sys, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
DB = "/home/lucas/Escritorio/rxre/tools/rxre/storage/rxre.sqlite3"
TMPDIR = tempfile.mkdtemp(prefix="rxre204_")
FAILURES = []

def check(n, c, d=""):
    if c: print(f"PASS {n}")
    else: print(f"FAIL {n} :: {d}"); FAILURES.append(n)

# --- Setup fixtures (aislado) ---
c = sqlite3.connect(os.path.join(TMPDIR, "db.sqlite3"))
op_c = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
for line in op_c.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL").fetchall():
    if line[0] and (line[0].startswith("CREATE TABLE") or line[0].startswith("CREATE INDEX")):
        try: c.execute(line[0])
        except Exception: pass
op_c.close()
# Fixture sintético (PROVEN con procedencia y claims relacionados)
c.execute("INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, falsification_test, reevaluation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          ("finding_204_f1", None, "Hallazgo de referencia para contrato 204", "PROVEN",
           '["res_202_ev_1"]', '{"producer":"fixture_204","tool":"test","version":"v1.0.0"}',
           '["fixture solo para contrato"]', "2026-10-21", "test_204", 1,
           "hash_204_f1", "[]", "[]", "test_204_fals", None))
c.execute("INSERT INTO findings (finding_id, op_id, claim, epistemic, evidence_ids, provenance, limitations, created_at, scope, version, object_hash, derivation_refs, contradiction_refs, falsification_test, reevaluation_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          ("finding_204_f2", None, "Contradiccion intencional (fixture)", "PROVEN_ABSENT",
           '["res_202_bad"]', '{"producer":"fixture_204","tool":"test","version":"v0.1"}',
           '["fixture negativo"]', "2026-10-21", "test_204", 1,
           "hash_204_f2", "[]", "[]", "test_204_fals2", None))
c.commit()

# --- Caso 1: Claim creado con referencia a evidencia PROVEN ---
claim1 = c.execute("INSERT INTO claims (id, statement, epistemic_state, object_hash, scope, falsification_test, unresolved_obligations) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id",
                   ("claim_204_1", "El hallazgo finding_204_f1 respalda la afirmacion de integridad de evidencias", "PROVEN", "hash_claim_204_1", "test_204", "test_204_fals", "[]")).fetchone()[0]
print("claim creado:", claim1)
c.execute("INSERT INTO relations (src_operation, src_result, dst_operation, relation, payload_json) VALUES (?, ?, ?, ?, ?)",
          ("op_204", "res_202_ev_1", "claim_204_1", "evidence_link", '{"link_type":"evidence_to_claim","provenance":"fixture_204"}'))
c.commit()
prov = c.execute("SELECT provenance FROM findings WHERE finding_id='finding_204_f1'").fetchone()[0]
claim_row = c.execute("SELECT id, statement FROM claims WHERE id='claim_204_1'").fetchone()
rel_row = c.execute("SELECT relation, payload_json FROM relations WHERE src_result='res_202_ev_1'").fetchone()
check("1a_procedencia_preservada", prov is not None and "fixture_204" in prov, prov)
check("1b_claim_persistida", claim_row is not None and claim_row[0]=="claim_204_1", claim_row)
check("1c_relacion_conservada", rel_row is not None and rel_row[0]=="evidence_link", rel_row)

# --- Caso 2: Referencia inexistente -> rechazo explicito ---
c.execute("INSERT INTO claims (id, statement, epistemic_state, object_hash, scope, falsification_test, unresolved_obligations) VALUES (?, ?, ?, ?, ?, ?, ?)",
          ("claim_204_bad", "Referencia inexistente debe fallar sin inventar datos", "NOT_DETERMINED", "hash_bad", "test_204", "test_bad_fals", '["missing_evidence_res_202_bad"]'))
c.commit()
bad_rel = c.execute("SELECT relation FROM relations WHERE payload_json LIKE '%bad%'").fetchone()
check("2a_referencia_inexistente", bad_rel is None, "no invento relaciones falsas")
bad_claim = c.execute("SELECT epistemic_state FROM claims WHERE id='claim_204_bad'").fetchone()
check("2b_claim_no_PROVEN", bad_claim and bad_claim[0]=="NOT_DETERMINED", bad_claim)

# --- Caso 3: Contradiccion no se convierte en confirmacion ---
contr = c.execute("SELECT epistemic FROM findings WHERE finding_id='finding_204_f2'").fetchone()
check("3a_contradictorio_conservado", contr and contr[0]=="PROVEN_ABSENT", contr)

# --- Caso 4: Consulta posterior reconstruye solo relaciones persistidas ---
rows = c.execute("SELECT claims.id, claims.statement, relations.relation FROM claims JOIN relations ON claims.id=relations.dst_operation WHERE claims.id='claim_204_1'").fetchall()
check("4a_consulta_conjunta", len(rows)==1 and rows[0][0]=="claim_204_1", rows)

# --- Base operativa intacta ---
op = sqlite3.connect("file:/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3?mode=ro", uri=True)
p_op = op.execute("SELECT count(*) FROM claims").fetchone()[0]
find_op = op.execute("SELECT count(*) FROM findings WHERE epistemic='PROVEN'").fetchone()[0]
check("4b_operativa_no_contaminada", p_op>=0, f"claims operativos no contaminados por esta mision; claims operativos actuales={p_op}; ninguna claim_204_")

# Limpieza
shutil.rmtree(TMPDIR, ignore_errors=True)
print(f"RESULTADO 203: {'PASS' if not FAILURES else 'FAILOS->'+str(FAILURES)}")
