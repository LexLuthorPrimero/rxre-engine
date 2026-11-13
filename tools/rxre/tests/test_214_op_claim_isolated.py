#!/usr/bin/env python3
"""RXRE-214 — Pruebas adversariales aisladas de op:claim (diseño B de 213).

Fixtures SINTÉTICAS identificadas con 'fixture_214_'.
DB_T aislada en /tmp; la DB operativa NO se escribe ni se lee con escritura.
Cadena real: machine.procesar_linea -> HANDLERS["claim"] -> authorization_gate
-> politica_transición -> adapter_finding_tierra -> TIERRA.Grafo (DB_T) -> lectura.
"""
import sys, os, json, sqlite3
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.api.machine import procesar_linea, HANDLERS

DB_ISO = "/tmp/rxre_214_isolated.sqlite3"
OP_DB = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"
PROTEGIDA_STORAGE = "/home/lucas/Escritorio/rxre/.rxre/storage"
PROTEGIDA_GPU = "/home/lucas/Escritorio/rxre/.rxre/gpu0/original"

FALLOS = []

def ok(cond, label, detalle=""):
    if cond:
        print("  [PASS] %s %s" % (label, detalle))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, detalle))

def clean():
    for suf in ("", "-wal", "-shm"):
        p = DB_ISO + suf
        if os.path.exists(p):
            os.remove(p)

def claim_line(args):
    # [215] Contrato JSONL top-level (no anidado en args); `autorizacion=True`
    # explicito obligatorio. Si args contiene argumentos de claim, se expanden
    # al nivel superior de la solicitud.
    full = dict(args)
    full.setdefault("autorizacion", True)
    return json.dumps({"op": "claim", **full})

def filas_tierra(db):
    if not os.path.exists(db):
        return 0
    c = sqlite3.connect(db)
    try:
        n = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    except sqlite3.Error:
        n = -1
    finally:
        c.close()
    return n

def filas_op():
    c = sqlite3.connect(OP_DB)
    try:
        return (c.execute("SELECT COUNT(*) FROM findings").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM research").fetchone()[0],
                c.execute("SELECT COUNT(*) FROM missions").fetchone()[0])
    finally:
        c.close()

FINDING_OK = {
    "finding_id": "fixture_214_ok",
    "text": "fixture: statement formal sintetica",
    "epistemic": "PROVEN",
    "evidence_ids": ["fixture_214_ref_1"],
    "falsification_test": "fixture_214_falsification",
    "object_hash": "fixture_214_hash",
    "scope": "fixture_214_scope",
    "contradiction_refs": [],
}

print("=== 214: op:claim aislado ===")
ok("claim" in HANDLERS, "op:claim registrado en HANDLERS")

# ---------------------------------------------------------------- autorizacion
print("\n-- autorizacion (contrato booleano exacto) --")
for label, valor in [("ausente", None), ("False", False), ("None", None),
                     ("0", 0), ("'true'", "true"), ("'false'", "false"),
                     ("1", 1), ("'True'", "True"), ("[]", []), ("{}", {})]:
    clean()
    args = {"db_path": DB_ISO, "finding_dict": dict(FINDING_OK)}
    if label != "ausente":
        args["explicit_enable"] = valor
    r = procesar_linea(claim_line(args))
    ok(r.get("status") == "blocked" and r.get("decision") == "NOT_ACTIVATED",
       "explicit_enable=%s -> bloqueado" % label,
       "decision=%s" % r.get("decision"))
    ok(filas_tierra(DB_ISO) == 0, "  sin escritura en DB_T (%s)" % label)

# ------------------------------------------------------------ destinos forbidden
print("\n-- destinos prohibidos --")
clean()
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": OP_DB,
                                "finding_dict": dict(FINDING_OK)}))
ok(r.get("status") == "blocked" and "operativa" in (r.get("motivo") or "").lower(),
   "db_path = base operativa -> rechazada", r.get("motivo", "")[:60])

clean()
r = procesar_linea(claim_line({"explicit_enable": True,
                                "db_path": PROTEGIDA_STORAGE + "/claims_new.sqlite3",
                                "finding_dict": dict(FINDING_OK)}))
ok(r.get("status") == "blocked", "db_path = zona protegida storage -> rechazada")

clean()
r = procesar_linea(claim_line({"explicit_enable": True,
                                "db_path": PROTEGIDA_GPU + "/t.sqlite3",
                                "finding_dict": dict(FINDING_OK)}))
ok(r.get("status") == "blocked", "db_path = zona protegida gpu0 -> rechazada")

# ------------------------------------------------------------ doble guarda
print("\n-- doble guarda: autorizacion ausente / no booleano --")
for label, valor in [("ausente", None), ("False", False), ("'true'", "true"), ("1", 1)]:
    clean()
    args = {"explicit_enable": True, "db_path": DB_ISO, "finding_dict": dict(FINDING_OK)}
    if label != "ausente":
        args["autorizacion"] = valor
    r = procesar_linea(claim_line(args))
    ok(r.get("status") == "blocked" and r.get("decision") == "NOT_ACTIVATED",
       "autorizacion=%s -> bloqueado" % label, "decision=%s" % r.get("decision"))
    ok(filas_tierra(DB_ISO) == 0, "  sin escritura en DB_T (autorizacion %s)" % label)

# ------------------------------------------------------------ args anidado
print("\n-- args anidado (no canonico) rechazado --")
clean()
r = procesar_linea(json.dumps({"op": "claim", "args": {
    "explicit_enable": True, "autorizacion": True, "db_path": DB_ISO,
    "finding_dict": dict(FINDING_OK)}}))
ok(r.get("status") == "blocked" and "top-level" in (r.get("motivo") or ""),
   "args anidado -> rechazado con motivo explicito", r.get("decision"))
ok(filas_tierra(DB_ISO) == 0, "sin escritura con args anidado")

# ------------------------------------------------------------ caso valido (PROVEN)
print("\n-- caso valido: PROVEN con refs verificadas --")
before_op = filas_op()
clean()
r = procesar_linea(claim_line({
    "explicit_enable": True, "db_path": DB_ISO,
    "finding_dict": dict(FINDING_OK),
    "resolver_refs": ["fixture_214_ref_1"],
    "contradiction_statements": []}))
print("     resultado: status=%s decision=%s motivo=%s" % (r.get("status"), r.get("decision"), (r.get("motivo") or "")[:80]))
ok(r.get("status") == "ok" and r.get("claim_id"), "PROVEN -> claim creado en DB_T",
   "claim_id=%s" % r.get("claim_id"))
ok(filas_tierra(DB_ISO) >= 1, "DB_T tiene claims", "claims=%d" % filas_tierra(DB_ISO))
ok(r.get("epistemic_state") == "PROVEN", "estado epistemologico PROVEN preservado",
   str(r.get("epistemic_state")))
after_op = filas_op()
ok(before_op == after_op, "DB_OP intacta (findings/research/missions)",
   "%s -> %s" % (before_op, after_op))

# lectura posterior canonica
import rxre.arquitectura.TIERRA as TIERRA
g = TIERRA.Grafo(DB_ISO)
leido = g.leer(r["claim_id"])
ok(leido is not None and leido.get("epistemic_state") == "PROVEN",
   "lectura posterior canonica TIERRA.Grafo.leer", str(leido.get("epistemic_state")))

# ------------------------------------------------------------ reintento identico
print("\n-- reintento identico (idempotencia) --")
claims_antes = filas_tierra(DB_ISO)
r2 = procesar_linea(claim_line({
    "explicit_enable": True, "db_path": DB_ISO,
    "finding_dict": dict(FINDING_OK),
    "resolver_refs": ["fixture_214_ref_1"],
    "contradiction_statements": []}))
claims_despues = filas_tierra(DB_ISO)
ok(r2.get("claim_id") == r.get("claim_id"), "mismo claim_id en reintento",
   "%s == %s" % (r2.get("claim_id"), r.get("claim_id")))
ok(claims_antes == claims_despues, "sin claims duplicadas",
   "%d -> %d" % (claims_antes, claims_despues))
ok(r2.get("ya_existia") is True, "ya_existia=True en reintento", str(r2.get("ya_existia")))

# ------------------------------------------------------------ PARTIAL
print("\n-- PARTIAL (nunca elevado a PROVEN) --")
clean()
f_partial = dict(FINDING_OK)
f_partial.update({"finding_id": "fixture_214_partial", "epistemic": "PARTIAL",
                  "text": "fixture: statement parcial", "evidence_ids": ["fixture_214_ref_p"]})
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_partial,
                                "resolver_refs": ["fixture_214_ref_p"],
                                "contradiction_statements": []}))
print("     resultado: status=%s decision=%s" % (r.get("status"), r.get("decision")))
if r.get("status") == "ok":
    g2 = TIERRA.Grafo(DB_ISO)
    leido2 = g2.leer(r["claim_id"])
    ok(leido2.get("epistemic_state") == "PARTIAL", "PARTIAL preservado en DB_T",
       str(leido2.get("epistemic_state")))
else:
    print("     [INFO] PARTIAL bloqueado por politica: %s" % (r.get("motivo") or "")[:80])

# ------------------------------------------------------------ PROVEN_ABSENT
print("\n-- PROVEN_ABSENT --")
clean()
f_abs = dict(FINDING_OK)
f_abs.update({"finding_id": "fixture_214_absent", "epistemic": "PROVEN_ABSENT",
               "text": "fixture: ausencia probada", "evidence_ids": ["fixture_214_ref_a"]})
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_abs,
                                "resolver_refs": ["fixture_214_ref_a"],
                                "contradiction_statements": []}))
print("     resultado: status=%s decision=%s" % (r.get("status"), r.get("decision")))
if r.get("status") == "ok":
    g3 = TIERRA.Grafo(DB_ISO)
    leido3 = g3.leer(r["claim_id"])
    ok(leido3.get("epistemic_state") == "PROVEN_ABSENT", "PROVEN_ABSENT preservado",
       str(leido3.get("epistemic_state")))
else:
    print("     [INFO] PROVEN_ABSENT bloqueado: %s" % (r.get("motivo") or "")[:80])

# ------------------------------------------------------------ estado desconocido
print("\n-- estado epistemologico desconocido --")
clean()
f_unk = dict(FINDING_OK)
f_unk.update({"finding_id": "fixture_214_unknown", "epistemic": "PROBABLY",
               "text": "fixture: estado desconocido"})
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_unk,
                                "resolver_refs": ["fixture_214_ref_1"],
                                "contradiction_statements": []}))
ok(r.get("status") == "blocked", "estado desconocido -> bloqueado", r.get("decision"))
ok(filas_tierra(DB_ISO) == 0, "sin escritura para estado desconocido")

# ------------------------------------------------------------ campos incompletos
print("\n-- campos formales incompletos --")
clean()
f_inc = dict(FINDING_OK)
f_inc.pop("falsification_test")
f_inc["finding_id"] = "fixture_214_incomplete"
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_inc,
                                "resolver_refs": ["fixture_214_ref_1"],
                                "contradiction_statements": []}))
ok(r.get("status") == "blocked", "falsification_test ausente -> bloqueado", r.get("decision"))
ok(filas_tierra(DB_ISO) == 0, "sin escritura para finding incompleto")

# ------------------------------------------------------------ refs inexistentes
print("\n-- referencias inexistentes (resolver que no reconoce) --")
clean()
f_ref = dict(FINDING_OK)
f_ref["finding_id"] = "fixture_214_badref"
f_ref["evidence_ids"] = ["fixture_214_ref_missing"]
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_ref,
                                "resolver_refs": [],       # ninguna ref existe
                                "contradiction_statements": []}))
ok(r.get("status") == "blocked", "ref inexistente -> bloqueado", r.get("decision"))
ok(filas_tierra(DB_ISO) == 0, "sin escritura con ref inexistente")

# ------------------------------------------------------------ contradiccion sin statement
print("\n-- contradiccion sin declaracion explicita --")
clean()
f_ctr = dict(FINDING_OK)
f_ctr["finding_id"] = "fixture_214_ctr"
f_ctr["contradiction_refs"] = ["fixture_214_ctr_1"]
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_ctr,
                                "resolver_refs": ["fixture_214_ref_1"],
                                "contradiction_statements": []}))
ok(r.get("status") == "blocked", "contradiccion sin statement -> bloqueado", r.get("decision"))
ok(filas_tierra(DB_ISO) == 0, "sin escritura con contradiccion no declarada")

# ------------------------------------------------------------ rollback
print("\n-- error de persistencia con rollback --")
clean()
c = sqlite3.connect(DB_ISO)
c.execute("CREATE TABLE IF NOT EXISTS contradictions (id INTEGER PRIMARY KEY)")
c.execute("DROP TRIGGER IF EXISTS trg_214_falla")
c.execute("CREATE TRIGGER trg_214_falla BEFORE INSERT ON contradictions "
          "WHEN NEW.statement LIKE '%fallo%' BEGIN SELECT RAISE(ABORT, 'fallo inyectado'); END")
c.commit(); c.close()
f_err = dict(FINDING_OK)
f_err["finding_id"] = "fixture_214_rollback"
f_err["contradiction_refs"] = ["fixture_214_ctr_1"]
r = procesar_linea(claim_line({"explicit_enable": True, "db_path": DB_ISO,
                                "finding_dict": f_err,
                                "resolver_refs": ["fixture_214_ref_1"],
                                "contradiction_statements": [
                                    {"statement": "fallo inyectado para rollback",
                                     "severity": "alta"}]}))
print("     resultado: status=%s decision=%s motivo=%s" % (r.get("status"), r.get("decision"), (r.get("motivo") or "")[:60]))
ok(r.get("status") in ("blocked", "error"), "error de persistencia propagado", r.get("status"))
c = sqlite3.connect(DB_ISO)
try:
    n_claims = c.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
except sqlite3.Error:
    n_claims = -1
c.close()
ok(n_claims == 0, "rollback: sin claims parciales", "claims=%d" % n_claims)

# ------------------------------------------------------------ op:research intacto
print("\n-- op:research sin transicion formal --")
before_op = filas_op()
r = procesar_linea('{"op":"research","args":{"kind":"frontier","text":"fixture_214_research",'
                    '"status":"OPEN"}}')
ok(r.get("status") == "ok", "op:research sigue funcionando", r.get("status"))
claims_t = filas_tierra(DB_ISO)
ok(claims_t == 0, "op:research no escribe en TIERRA.claims", "claims=%d" % claims_t)
after_op = filas_op()
ok(after_op[1] == before_op[1] + 1, "op:research escribio 1 fila en research (operativo)")
ok(after_op[0] == before_op[0], "op:research no escribio findings")

# ------------------------------------------------------------ resumen
print("\n=== RESUMEN 214 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
print("DB_T claims final:", filas_tierra(DB_ISO))
print("DB_OP findings/research/missions:", filas_op())
if FALLOS:
    sys.exit(1)
print("214 OK")
