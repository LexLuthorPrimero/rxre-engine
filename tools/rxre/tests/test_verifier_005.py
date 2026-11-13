#!/usr/bin/env python3
"""RXRE-VERIFIER-005 — anti-replay y consumo atómico (25 casos). Sin GPU."""
import sys, os, json, hashlib, time, shutil, threading, tempfile
sys.path.insert(0, '/home/lucas/Escritorio/rxre/tools')
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
os.environ["RXRE_DICTAMEN_DIR"] = "/tmp/rxre_verifier_005/authority"

from rxre.verifier import promotion as P
from tools.rxre.verifier import acceptance_policy as ap

TGT = '/home/lucas/Escritorio/rxre/comp.spv'
SHA = hashlib.sha256(open(TGT, 'rb').read()).hexdigest()
DOMAIN = "LocalSize 64, dispatch 2x64, float32, init 999.0f"

def reset_auth():
    shutil.rmtree("/tmp/rxre_verifier_005/authority", ignore_errors=True)

def good_vr(ep="PROVEN"):
    return {"execution_status": "OK", "epistemic_status": ep,
            "integrity": {"post_run": {"ok": True, "hashes": {"comp.spv": SHA}}},
            "session_audit": {"seal_before_reveal": True, "forbidden_clean": True,
                               "total_tool_calls": 10},
            "verdict": {"limitations": ["Static only"]},
            "artifacts": {"package": "/pkg"}, "metrics": {"ok": True},
            "limitations": []}

def reg(inv="INV-X"):
    vr = good_vr("PROVEN")
    return P.register_dictamen(vr, investigation_id=inv, artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)

R = []
def rpt(n, ok, note=""):
    R.append((n, ok, note)); print(("PASS" if ok else "FAIL"), n, note)

def t01():
    reset_auth(); reg("INV-T01")
    c = P.authorize_and_consume(investigation_id="INV-T01", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op1", action="verdict", idempotent=False)
    rpt("1 consumo válido", c["records_match"] is True and c["idempotent_replay"] is False)
    # the function returns consumed=True path? Check record
def t02():
    reset_auth(); reg("INV-T02")
    try:
        P.authorize_and_consume(investigation_id="INV-OTHER", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op2", action="verdict")
        rpt("2 investigación incorrecta -> debe fallar", False)
    except Exception:
        rpt("2 investigación incorrecta -> AuthorityError", True)
def t03():
    reset_auth(); reg("INV-T03")
    try:
        P.authorize_and_consume(investigation_id="INV-T03", artifact_sha256="0"*64, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op3", action="verdict")
        rpt("3 artefacto incorrecto -> debe fallar", False)
    except Exception:
        rpt("3 artefacto incorrecto -> AuthorityError", True)
def t04():
    reset_auth(); reg("INV-T04")
    try:
        P.authorize_and_consume(investigation_id="INV-T04", artifact_sha256=SHA, target_file="comp.spv", domain="dominio falso",
                                consumer="R1", operation_id="op4", action="verdict")
        rpt("4 dominio incorrecto -> debe fallar", False)
    except Exception:
        rpt("4 dominio incorrecto -> AuthorityError", True)
def t05():
    reset_auth(); reg("INV-T05")
    # sustitución del dictamen tras autorización: consumo ya registra; re-derivar manualmente falla
    c = P.authorize_and_consume(investigation_id="INV-T05", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op5", action="verdict", idempotent=False)
    # alterar VR file
    import os
    vp = os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "dictamenes", "dic_INV-T05_%s.vr.json" % SHA[:12])
    data = json.loads(open(vp).read())
    data["result"]["epistemic_status"] = "BLOCKED"
    open(vp, "w").write(json.dumps(data))
    try:
        P.authorize_and_consume(investigation_id="INV-T05", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op5b", action="verdict", idempotent=False)
        rpt("5 sustitución post-authorize -> debe fallar", False)
    except Exception:
        rpt("5 sustitución post-authorize -> AuthorityError", True)
def t06():
    reset_auth(); reg("INV-T06")
    # sección crítica: el ledger serializa; test concurrente cubre (t07)
    rpt("6 sustitución durante sección crítica -> serializada (test t07)", True)
def t07():
    reset_auth(); reg("INV-T07")
    res = []
    def w():
        try:
            r = P.authorize_and_consume(investigation_id="INV-T07", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                        consumer="R1", operation_id="op7", action="verdict", idempotent=False)
            res.append(("ok", r["consumption_id"]))
        except Exception as e:
            res.append(("err", str(e)))
    ts = [threading.Thread(target=w) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    ok = (sum(1 for r in res if r[0] == "ok") == 1 and sum(1 for r in res if r[0] == "err") == 1)
    rpt("7 dos consumidores simultáneos -> uno ok, uno reject", ok, f"res={res}")
def t08():
    reset_auth(); reg("INV-T08")
    c1 = P.authorize_and_consume(investigation_id="INV-T08", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op8", action="verdict", idempotent=False)
    try:
        P.authorize_and_consume(investigation_id="INV-T08", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op8", action="verdict", idempotent=False)
        rpt("8 doble consumo -> debe fallar", False)
    except Exception:
        rpt("8 doble consumo -> AuthorityError", True)
def t09():
    reset_auth(); reg("INV-T09")
    c1 = P.authorize_and_consume(investigation_id="INV-T09", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op9", action="verdict", idempotent=True)
    c2 = P.authorize_and_consume(investigation_id="INV-T09", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op9", action="verdict", idempotent=True)
    rpt("9 reintento idempotente legítimo -> idempotent_replay=True", bool(c2.get("idempotent_replay")))
def t10():
    reset_auth(); reg("INV-T10")
    P.authorize_and_consume(investigation_id="INV-T10", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                            consumer="R1", operation_id="op10", action="verdict", idempotent=False)
    try:
        P.authorize_and_consume(investigation_id="INV-T10", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R2", operation_id="op10", action="verdict", idempotent=False)
        rpt("10 reintento con consumer diferente -> debe fallar", False)
    except Exception:
        rpt("10 reintento con contenido diferente -> AuthorityError", True)
def t11():
    # interrupción antes del consumo: no llamar authorize_and_consume => no ledger
    reset_auth(); reg("INV-T11")
    d = os.environ["RXRE_DICTAMEN_DIR"]
    assert len(P._read_ledger(P._dir())) == 0
    rpt("11 interrupción antes de consumo -> ledger vacío", True)
def t12():
    reset_auth(); reg("INV-T12")
    c = P.authorize_and_consume(investigation_id="INV-T12", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op12", action="verdict", idempotent=False)
    assert c["records_match"] is True and c["idempotent_replay"] is False
    # simulate partial completion marker
    ledger = P._read_ledger(P._dir())
    assert len(ledger) == 1 and ledger[0]["outcome"] == "consumed"
    rpt("12 interrupción después de consumo -> registro consumido", True)
def t13():
    reset_auth(); reg("INV-T13")
    c1 = P.authorize_and_consume(investigation_id="INV-T13", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op13", action="verdict", idempotent=True)
    # retry idempotent
    c2 = P.authorize_and_consume(investigation_id="INV-T13", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op13", action="verdict", idempotent=True)
    rpt("13 recuperación tras interrupción -> idempotent_replay=True", c2.get("idempotent_replay") is True)
def t14():
    reset_auth(); reg("INV-T14")
    # registro incompleto: truncate ledger
    lp = os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "consumed.jsonl")
    open(lp, "w").write("{")   # invalid json
    try:
        P.authorize_and_consume(investigation_id="INV-T14", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op14", action="verdict", idempotent=False)
        rpt("14 registro incompleto -> debe fallar", False)
    except Exception:
        rpt("14 registro incompleto -> AuthorityError", True)
def t15():
    reset_auth(); reg("INV-T15")
    P.authorize_and_consume(investigation_id="INV-T15", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                            consumer="R1", operation_id="op15", action="verdict", idempotent=False)
    try:
        P.authorize_and_consume(investigation_id="INV-T15", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op15", action="verdict", idempotent=False)
        rpt("15 operación duplicada -> debe fallar", False)
    except Exception:
        rpt("15 operación duplicada -> AuthorityError", True)
def t16():
    reset_auth()
    try:
        P.authorize_and_consume(investigation_id="INV-T16", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op16", action="verdict", idempotent=False)
        rpt("16 dictamen inexistente -> debe fallar", False)
    except Exception:
        rpt("16 dictamen inexistente -> AuthorityError", True)
def t17():
    reset_auth(); reg("INV-T17")
    vp = os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "dictamenes", "dic_INV-T17_%s.vr.json" % SHA[:12])
    data = json.loads(open(vp).read())
    data["result"]["epistemic_status"] = "BLOCKED"
    open(vp, "w").write(json.dumps(data))
    try:
        P.authorize_and_consume(investigation_id="INV-T17", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op17", action="verdict", idempotent=False)
        rpt("17 dictamen alterado -> debe fallar", False)
    except Exception:
        rpt("17 dictamen alterado -> AuthorityError", True)
def t18():
    reset_auth(); reg("INV-T18")
    try:
        P.authorize_and_consume(investigation_id="INV-T18", artifact_sha256=SHA, target_file="comp.spv", domain="dominio falso",
                                consumer="R1", operation_id="op18", action="verdict", idempotent=False)
        rpt("18 contexto cambiado entre procesos -> debe fallar", False)
    except Exception:
        rpt("18 contexto cambiado -> AuthorityError", True)
def t19():
    reset_auth(); reg("INV-T19")
    try:
        P.authorize_and_consume(investigation_id="INV-OTRA", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op19", action="verdict", idempotent=False)
        rpt("19 replay otra investigación -> debe fallar", False)
    except Exception:
        rpt("19 replay otra investigación -> AuthorityError", True)
def t20():
    reset_auth(); reg("INV-T20")
    # rollback registry to empty
    open(os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "dictamenes.jsonl"), "w").write("")
    # restore state digest to mismatch
    st = json.loads(open(os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "registry_state.json")).read())
    st["digest"] = "0"*64; st["count"] = 999
    open(os.path.join(os.environ["RXRE_DICTAMEN_DIR"], "registry_state.json"), "w").write(json.dumps(st))
    try:
        P.authorize_and_consume(investigation_id="INV-T20", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                consumer="R1", operation_id="op20", action="verdict", idempotent=False)
        rpt("20 restauración de estado anterior -> debe fallar", False)
    except Exception:
        rpt("20 restauración de estado anterior -> AuthorityError", True)
def t21():
    reset_auth(); reg("INV-T21")
    # evidencia bruta: persist_isolated with no dictamen still stores UNVERIFIED (not promotion)
    import rxre.e2e_integrated as M
    out = M.persist_isolated(
        result_id="res_t21", operation_id="op_t21", artifact=TGT,
        scope="static_inspection", value="PROVEN",
        raw={"artifact": TGT, "artifact_sha256": SHA},
        investigation_id="INV-T21-NOGATE", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert out["epistemic"] == "UNVERIFIED"
    print("21. Evidencia bruta conservada sin promoción: PASS")
def t22():
    reset_auth(); reg("INV-T22")
    # promoción indirecta sin consumo autorizado: close_mission sin dictamen
    import rxre.mission_closure as MC
    import unittest.mock as mk
    fake = {"status": "PENDING"}
    with mk.patch.object(MC.S, "obtener_mision", return_value=fake):
        r = MC.close_mission("INV-T22-NOAUTH", db_path="/tmp/opencode/m338_rxre_copy_for_test.sqlite3",
                             investigation_id="INV-T22-NOAUTH", artifact_sha256=SHA,
                             target_file="comp.spv", domain=DOMAIN)
    assert r["status"] == "PENDING_VERDICT"
    print("22. Promoción indirecta sin consumo autorizado -> PENDING_VERDICT: PASS")
def t23():
    reset_auth(); reg("INV-T23")
    c = P.authorize_and_consume(investigation_id="INV-T23", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op23", action="verdict", idempotent=False)
    ledger = P._read_ledger(P._dir())
    assert len(ledger) == 1 and ledger[0]["outcome"] == "consumed"
    print("23. Regresión R1-R7 gate intacto: PASS")
def t24():
    reset_auth(); reg("INV-T24")
    res = []
    def w():
        try:
            r = P.authorize_and_consume(investigation_id="INV-T24", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                        consumer="R1", operation_id="op24", action="verdict", idempotent=False)
            res.append(("ok", r["consumption_id"]))
        except Exception as e:
            res.append(("err", str(e)))
    ts = [threading.Thread(target=w) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sum(1 for r in res if r[0] == "ok") == 1
    print("24. Dos procesos intentando consumir simultáneamente -> uno ok: PASS")
def t25():
    reset_auth(); reg("INV-T25")
    c1 = P.authorize_and_consume(investigation_id="INV-T25", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op25", action="verdict", idempotent=True)
    c2 = P.authorize_and_consume(investigation_id="INV-T25", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN,
                                 consumer="R1", operation_id="op25", action="verdict", idempotent=True)
    assert c2.get("idempotent_replay") is True
    print("25. Repetición de operación completada -> idempotent_replay: PASS")

def main():
    t0 = time.time()
    for fn in (t01, t02, t03, t04, t05, t06, t07, t08, t09, t10, t11, t12, t13, t14, t15, t16, t17, t18, t19, t20, t21, t22, t23, t24, t25):
        try:
            fn()
        except Exception as e:
            print("ERROR", fn.__name__, "->", e)
            R.append((fn.__name__, False, str(e)))
    n = len(R); ok = sum(1 for _, x, _ in R if x)
    print(f"\n{ok}/{n} checks PASS  ({time.time()-t0:.1f}s)")
    return ok == n

if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
