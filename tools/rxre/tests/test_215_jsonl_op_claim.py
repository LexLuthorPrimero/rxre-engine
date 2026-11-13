#!/usr/bin/env python3
"""RXRE-215 — Compatibilidad JSONL y contrato de entrada de op:claim.

Fixtures SINTETICAS identificadas con 'fixture_215_'.
DB_T aislada en /tmp; DB operativa solo lectura.
"""
import sys, os, json, sqlite3
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import procesar_linea, HANDLERS

DB_ISO = "/tmp/rxre_215_iso.sqlite3"
OP_DB = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
FALLOS = []

FINDING = {
    "finding_id": "fixture_215_ok",
    "statement": "fixture_215: statement formal sintetica",
    "epistemic": "PROVEN",
    "evidence_ids": ["fixture_215_ref_1"],
    "falsification_test": "fixture_215_falsification",
    "object_hash": "fixture_215_hash",
    "scope": "fixture_215_scope",
    "contradiction_refs": [],
}

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def clean():
    for suf in ("", "-wal", "-shm"):
        p = DB_ISO + suf
        if os.path.exists(p):
            os.remove(p)

def claims_t():
    if not os.path.exists(DB_ISO):
        return 0
    c = sqlite3.connect(DB_ISO)
    try:
        return c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    except sqlite3.Error:
        return -1
    finally:
        c.close()

def op_rows():
    c = sqlite3.connect(OP_DB)
    try:
        return tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),"
                               "(SELECT COUNT(*) FROM research),"
                               "(SELECT COUNT(*) FROM missions)").fetchone())
    finally:
        c.close()

print("=== 215: contrato JSONL de op:claim ===")

# --- caso 1: formato canonico top-level (como _handle_research) -> debe funcionar
clean()
r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                "autorizacion": True, "db_path": DB_ISO,
                                "finding_dict": dict(FINDING),
                                "resolver_refs": ["fixture_215_ref_1"],
                                "contradiction_statements": []}))
ok(r.get("status") == "ok" and r.get("claim_id"),
   "C1 top-level (canonico) -> claim creado", "claim_id=%s" % (r.get("claim_id") or "")[:12])
ok(r.get("epistemic_state") == "PROVEN", "C1 epistemic_state preservado", str(r.get("epistemic_state")))
CLAIM1 = r.get("claim_id")

# --- caso 2: args anidado -> debe rechazarse con motivo explicito
clean()
r = procesar_linea(json.dumps({"op": "claim", "args": {
    "explicit_enable": True, "autorizacion": True, "db_path": DB_ISO,
    "finding_dict": dict(FINDING), "resolver_refs": ["fixture_215_ref_1"]}}))
ok(r.get("status") == "blocked" and "top-level" in (r.get("motivo") or ""),
   "C2 args anidado -> rechazado explicitamente", r.get("decision"))
ok(claims_t() == 0, "C2 sin escritura en DB_T")

# --- caso 3: params (no existe en el contrato de machine) -> no llega a activarse
clean()
r = procesar_linea(json.dumps({"op": "claim", "params": {
    "explicit_enable": True, "autorizacion": True, "db_path": DB_ISO,
    "finding_dict": dict(FINDING)}}))
ok(r.get("status") == "blocked" and r.get("decision") == "NOT_ACTIVATED",
   "C3 params no admitido -> bloqueado", r.get("decision"))
ok(claims_t() == 0, "C3 sin escritura en DB_T")

# --- caso 4: ambos presentes y contradictorios -> rechazo, no precedencia silenciosa
clean()
r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                "autorizacion": True, "db_path": DB_ISO,
                                "finding_dict": dict(FINDING),
                                "args": {"explicit_enable": False, "db_path": "/tmp/otro.sqlite3"}}))
ok(r.get("status") == "blocked", "C4 contradictorio -> rechazado (no precedencia silenciosa)", r.get("decision"))
ok(claims_t() == 0, "C4 sin escritura en DB_T")

# --- caso 5: campos obligatorios ausentes
for campo in ("explicit_enable", "autorizacion", "db_path", "finding_dict"):
    clean()
    req = {"op": "claim", "explicit_enable": True, "autorizacion": True,
           "db_path": DB_ISO, "finding_dict": dict(FINDING)}
    req.pop(campo)
    r = procesar_linea(json.dumps(req))
    ok(r.get("status") == "blocked", "C5 falta '%s' -> bloqueado" % campo, r.get("decision"))
    ok(claims_t() == 0, "  sin escritura (falta %s)" % campo)

# --- caso 6: explicit_enable truthy no booleano
for valor in (False, None, 0, 1, "true", "false", "True", [], {}):
    clean()
    r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": valor,
                                    "autorizacion": True, "db_path": DB_ISO,
                                    "finding_dict": dict(FINDING)}))
    ok(r.get("status") == "blocked" and r.get("decision") == "NOT_ACTIVATED",
       "C6 explicit_enable=%r -> bloqueado" % (valor,), r.get("decision"))
    ok(claims_t() == 0, "  sin escritura (%r)" % (valor,))

# --- caso 7: autorizacion ausente / no exacta
for valor in (None, False, 0, 1, "true", "false", "True", [], {}):
    clean()
    req = {"op": "claim", "explicit_enable": True, "autorizacion": valor,
           "db_path": DB_ISO, "finding_dict": dict(FINDING)}
    if valor is None:
        req.pop("autorizacion")
    r = procesar_linea(json.dumps(req))
    ok(r.get("status") == "blocked" and r.get("decision") == "NOT_ACTIVATED",
       "C7 autorizacion=%r -> bloqueado" % (valor,), r.get("decision"))
    ok(claims_t() == 0, "  sin escritura (autorizacion %r)" % (valor,))

# --- caso 8: referencias inexistentes + destino operativo
clean()
r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                "autorizacion": True, "db_path": DB_ISO,
                                "finding_dict": dict(FINDING),
                                "resolver_refs": []}))
ok(r.get("status") == "blocked", "C8 refs inexistentes -> bloqueado", r.get("decision"))
ok(claims_t() == 0, "C8 sin escritura (refs inexistentes)")

clean()
r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                "autorizacion": True, "db_path": OP_DB,
                                "finding_dict": dict(FINDING)}))
ok(r.get("status") == "blocked" and "operativa" in (r.get("motivo") or "").lower(),
   "C8 destino operativo -> rechazado", r.get("decision"))

# --- caso 9: claim valido en base aislada + lectura posterior
clean()
r = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                "autorizacion": True, "db_path": DB_ISO,
                                "finding_dict": dict(FINDING),
                                "resolver_refs": ["fixture_215_ref_1"],
                                "contradiction_statements": []}))
ok(r.get("status") == "ok" and r.get("claim_id"), "C9 claim valido -> ok", str(r.get("claim_id"))[:12])
import rxre.arquitectura.TIERRA as TIERRA
g = TIERRA.Grafo(DB_ISO)
leido = g.leer(r["claim_id"])
ok(leido and leido.get("epistemic_state") == "PROVEN", "C9 lectura posterior canonica", str(leido.get("epistemic_state") if leido else None))
ok(claims_t() == 1, "C9 exactamente 1 claim en DB_T", "claims=%d" % claims_t())

# --- caso 10: reintento identico y contenido conflictivo con misma identidad
antes = claims_t()
r2 = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                 "autorizacion": True, "db_path": DB_ISO,
                                 "finding_dict": dict(FINDING),
                                 "resolver_refs": ["fixture_215_ref_1"],
                                 "contradiction_statements": []}))
ok(r2.get("claim_id") == r.get("claim_id"), "C10 reintento identico -> mismo claim_id")
ok(claims_t() == antes, "C10 reintento no duplica", "%d -> %d" % (antes, claims_t()))
ok(r2.get("ya_existia") is True, "C10 ya_existia=True", str(r2.get("ya_existia")))

conf = dict(FINDING)
conf["statement"] = FINDING["statement"] + " (contenido conflictivo)"
r3 = procesar_linea(json.dumps({"op": "claim", "explicit_enable": True,
                                 "autorizacion": True, "db_path": DB_ISO,
                                 "finding_dict": conf,
                                 "resolver_refs": ["fixture_215_ref_1"],
                                 "contradiction_statements": []}))
print("     C10 contenido conflictivo -> status=%s decision=%s" % (r3.get("status"), r3.get("decision")))
ok(claims_t() == antes, "C10 contenido conflictivo no altera claims existentes", "claims=%d" % claims_t())
leido2 = TIERRA.Grafo(DB_ISO).leer(r["claim_id"])
ok(leido2.get("statement") == FINDING["statement"], "C10 statement original intacta")

# --- regresion: op:research intacto
antes_op = op_rows()
r = procesar_linea('{"op":"research","args":{"kind":"frontier","text":"fixture_215_research","status":"OPEN"}}')
ok(r.get("status") == "ok", "REGRESION op:research ok", r.get("status"))
despues_op = op_rows()
ok(despues_op[1] == antes_op[1] + 1, "REGRESION research +1 (operativo)")
ok(despues_op[0] == antes_op[0], "REGRESION findings sin cambios")
ok(despues_op[2] == antes_op[2], "REGRESION missions sin cambios")

print("\n=== RESUMEN 215 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("215 OK")
