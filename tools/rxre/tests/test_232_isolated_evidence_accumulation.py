#!/usr/bin/env python3
"""RXRE-MISSION-232 — Prueba de aceptacion aislada de acumulacion controlada.

Invoca DIRECTAMENTE el mecanismo existente `TIERRA.Grafo.aportar`.
No modifica adapter_finding_tierra.py, machine.py, core/* ni la base operativa.
Base aislada: /tmp/rxre_232_iso.sqlite3
"""
import sys, os, sqlite3, json, traceback
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
from rxre.arquitectura import TIERRA

DB_ISO = "/tmp/rxre_232_iso.sqlite3"
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
    if not os.path.exists(DB_ISO):
        return {"claims": [], "evidence": []}
    c = sqlite3.connect(DB_ISO)
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(claims)").fetchall()]
        claims = [dict(zip(cols, r)) for r in c.execute("SELECT * FROM claims").fetchall()]
        ecols = [r[1] for r in c.execute("PRAGMA table_info(evidence)").fetchall()]
        ev = [dict(zip(ecols, r)) for r in c.execute("SELECT * FROM evidence").fetchall()]
        return {"claims": claims, "evidence": ev}
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
            "evidence_ids": eids, "falsification_test": "fixture_232_falsification",
            "object_hash": oh, "scope": sc, "contradiction_refs": []}

def aportar(claim_id, kind, payload, producer="rxre.mission_232_probe",
             transformacion="evidence_accumulation_probe", supersedes_ref=None):
    """Invoca el mecanismo EXISTente de aportacion y captura la traza SQL."""
    TRAZA[:] = []
    g = TIERRA.Grafo(DB_ISO)
    g.db.set_trace_callback(lambda s: TRAZA.append(s))
    try:
        ev_id = g.aportar(claim_id, kind, payload, producer=producer,
                          transformacion=transformacion, supersedes_ref=supersedes_ref)
        g.db.commit()
        return ev_id, None
    except Exception as exc:
        try:
            g.db.rollback()
        except Exception:
            pass
        return None, exc
    finally:
        g.db.set_trace_callback(None)
        g.db.close()

print("=== 232: aceptacion aislada de acumulacion controlada ===")
op_antes = op_rows()

# --- 1. Claim existente con evidencia inicial E1 ---
clean()
f1 = finding("stmt_232_A", "hash_232_A", "scope_232_A", ["fixture_232_E1"], "fixture_232_f1")
r1 = preintegrate_finding_to_tierra(DB_ISO, f1, resolver_refs=lambda r: True,
                                    contradiction_statements=None, explicit_enable=True)
st1 = estado()
claim = st1["claims"][0]
ev1_rows = [e for e in st1["evidence"] if e["claim_id"] == claim["claim_id"]]
E1_EV = [e["evidence_id"] for e in ev1_rows if "fixture_232_E1" in e["payload"]]
ok(r1.get("status") == "ok", "1 claim creado con E1", str(claim["claim_id"])[:16])
ok(len(E1_EV) == 1, "1b E1 persistida", E1_EV[0])
refs_antes = json.loads(claim["evidence_refs"])
ver_antes = claim["version"]
print("     evidencia_refs iniciales: %s | version=%s row_count=%s" % (refs_antes, ver_antes, claim["row_count"]))

# --- 2. Aportacion de evidencia valida adicional E2 ---
PAYLOAD_E2 = {"rxre_result_id": "fixture_232_E2", "resolved_by": "resolver_refs", "verificado": True}
ev2_id, err2 = aportar(claim["claim_id"], "artifact", PAYLOAD_E2)
ok(err2 is None and ev2_id, "2 aportacion E2 aceptada", "ev_id=%s err=%s" % (str(ev2_id)[:16], err2))

# --- 3. Relectura persistente: E1 y E2 presentes ---
st2 = estado()
claim2 = st2["claims"][0]
refs_despues = json.loads(claim2["evidence_refs"])
ev_rows = [e for e in st2["evidence"] if e["claim_id"] == claim["claim_id"]]
ok(E1_EV[0] in refs_despues, "3a E1 sigue en evidence_refs", str(refs_despues))
ok(ev2_id in refs_despues, "3b E2 anadido a evidence_refs", str(refs_despues))
ok(any(e["evidence_id"] == E1_EV[0] for e in ev_rows), "3c fila E1 intacta (no borrada)")
ok(any("fixture_232_E2" in e["payload"] for e in ev_rows), "3d fila E2 persistida")
ok(len(ev_rows) == len(ev1_rows) + 1, "3e exactamente una fila nueva", "antes=%d despues=%d" % (len(ev1_rows), len(ev_rows)))
ok(claim2["version"] > ver_antes, "3f version incrementada", "%s -> %s" % (ver_antes, claim2["version"]))
writes = [s for s in TRAZA if s.strip().upper().startswith(("INSERT", "UPDATE"))]
ok(len(writes) >= 2, "3g traza: INSERT evidence + UPDATE claims", "ops=%d" % len(writes))

# --- 4. Repeticion de E2: idempotencia (no duplica filas, no altera version) ---
ev2_id_b, err_b = aportar(claim["claim_id"], "artifact", PAYLOAD_E2)
st3 = estado()
claim3 = st3["claims"][0]
ev_rows3 = [e for e in st3["evidence"] if e["claim_id"] == claim["claim_id"]]
ok(len(ev_rows3) == len(ev_rows), "4a repeticion no duplica filas", "evidencias=%d" % len(ev_rows3))
ok(claim3["version"] == claim2["version"], "4b version sin cambios tras repeticion", "version=%s" % claim3["version"])
ok(err_b is not None, "4c la repeticion se rechaza explicitamente (no es idempotente por API)", "error=%s" % type(err_b).__name__)

# --- 5. Evidencia invalida / referencia no resoluble: rechazo sin escrituras parciales ---
st5_antes = estado()
n_ev_antes = len(st5_antes["evidence"])
n_cl_antes = len(st5_antes["claims"])
ev_bad, err_bad = aportar(claim["claim_id"], "artifact", {"rxre_result_id": "fixture_232_E9", "verificado": True},
                          producer="rxre.mission_232_probe", transformacion="probe")
st5 = estado()
ok(err_bad is None, "5a aportar NO valida referencias (limite del contrato actual)", "err=%s" % err_bad)
# La validacion de referencias vive en el adaptador (preintegracion/resolver_refs):
r_bad = preintegrate_finding_to_tierra(DB_ISO, finding("stmt_232_A", "hash_232_A", "scope_232_A", ["fixture_232_E9"], "fixture_232_f9"),
                                        resolver_refs=lambda r: False, contradiction_statements=None, explicit_enable=True)
ok(r_bad.get("status") != "ok", "5b referencia no resoluble -> rechazada en la frontera de autorizacion", str(r_bad.get("status")))
st5b = estado()
ok(len(st5b["evidence"]) == len(st5["evidence"]), "5c sin escritura parcial tras rechazo", "evidencias=%d" % len(st5b["evidence"]))

# --- 6. Evidencia con artefacto/alcance incompatible: la API no tiene parametro de alcance ---
ev_orphan, err_orphan = aportar("clm_inexistente_232", "artifact", PAYLOAD_E2)
st6 = estado()
ev6 = [e for e in st6["evidence"] if e["claim_id"] == "clm_inexistente_232"]
ok(err_orphan is not None, "6a aportar a claim inexistente -> error (FK)", "err=%s" % type(err_orphan).__name__)
ok(len(ev6) == 0, "6b sin escritura parcial", "filas=%d" % len(ev6))
print("     NOTA: `aportar` no recibe scope/object_hash: la compatibilidad de alcance/artefacto NO esta definida en esta capa (PENDIENTE de contrato).")

# --- 7. supersedes_ref: precondiciones ---
err_sup_mal = None
g = TIERRA.Grafo(DB_ISO)
g.db.set_trace_callback(lambda s: TRAZA.append(s))
try:
    g.aportar(claim["claim_id"], "artifact", {"rxre_result_id": "fixture_232_E3", "corregido": True},
              producer="rxre.mission_232_probe", transformacion="probe", supersedes_ref="ev_inexistente_232")
    err_sup_mal = None
except Exception as exc:
    err_sup_mal = exc
    try: g.db.rollback()
    except Exception: pass
g.db.set_trace_callback(None)
g.db.close()
st7 = estado()
ok(err_sup_mal is not None, "7a supersedes_ref inexistente -> rechazo explicito", "err=%s" % type(err_sup_mal).__name__)
ok(not any("fixture_232_E3" in e["payload"] for e in st7["evidence"]), "7b sin escritura tras rechazo de supersedes_ref")

# 7c: supersedes_ref valido (aporta correccion conservando la anterior)
ev_sup_ok, err_sup_ok = aportar(claim["claim_id"], "artifact",
                                 {"rxre_result_id": "fixture_232_E3", "corregido": True},
                                 producer="rxre.mission_232_probe", transformacion="probe",
                                 supersedes_ref=E1_EV[0])
st7c = estado()
ev7c = [e for e in st7c["evidence"] if e["claim_id"] == claim["claim_id"]]
ok(err_sup_ok is None and ev_sup_ok, "7c supersedes_ref valido -> aceptado", "ev_id=%s" % str(ev_sup_ok)[:16])
ok(any(e["evidence_id"] == E1_EV[0] for e in ev7c), "7d evidencia previa NO borrada (coexiste)")
ok(any(e.get("supersedes_ref") == E1_EV[0] for e in ev7c), "7e lineage supersedes_ref registrado")

# --- 8. Procedencia y hashes conservados tras cerrar y reabrir ---
g = TIERRA.Grafo(DB_ISO)
verif = []
for e in ev7c:
    d = g.leer_evidencia(e["evidence_id"], verificar=True)
    verif.append((d["evidence_id"][:14], d["hash_verificado"]))
claim_final = g.leer(claim["claim_id"])
g.db.close()
ok(all(v[1] for v in verif), "8a hashes de fila verificados tras reabrir", str(verif))
ok(claim_final is not None, "8b claim legible tras reabrir")
ref_list = claim_final["evidence_refs"] if isinstance(claim_final["evidence_refs"], list) else json.loads(claim_final["evidence_refs"])
# 8c: evidence_refs no incluye la fila 'observation' creada por adapter; los artifacts coinciden.
ref_artifacts = [r["evidence_id"] for r in ev7c if r.get("kind") != "observation"]
ref_refs = claim_final["evidence_refs"] if isinstance(claim_final["evidence_refs"], list) else json.loads(str(claim_final["evidence_refs"]))
ok(len(ref_refs) == len(ref_artifacts), "8c refs de evidencia == filas de evidencia (excluye observation del adapter)", "refs=%d artifacts_evid=%d" % (len(ref_refs), len(ref_artifacts)))
ok(any("fixture_232_E1" in e["payload"] for e in ev7c), "8d procedencia E1 conservada")
ok(any("fixture_232_E2" in e["payload"] for e in ev7c), "8e procedencia E2 conservada")

# --- Integridad operativa y zonas protegidas ---
op_despues = op_rows()
ok(op_antes == op_despues, "DB operativa sin escrituras", "%s == %s" % (op_antes, op_despues))
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py",
          "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py",
          "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3",
          "/home/lucas/Escritorio/rxre/.rxre/gpu0/original"):
    ok(os.path.exists(p), "zona protegida presente: %s" % os.path.basename(p))

print("\n=== RESUMEN 232 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("232 OK")
