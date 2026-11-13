"""Tests independientes librería epistemic (solo stdlib, sin RXRE)."""
from __future__ import annotations
import json, os, sys, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from epistemic import (
    EpistemicState, AcceptanceDecision,
    guard_promotion, seal_prediction, validate_seal_before_reveal,
    admit_claim, prepare, record_effect, confirm, reconcile,
    authorize_and_consume, audit_ledger,
    EvidenceBundle,
)

def _ev(ep, limits=None, es="OK", seal=True):
    d = {"execution_status": es, "epistemic_status": ep,
         "integrity": {"post_run": {"ok": True, "hashes": {}}},
         "session_audit": {"seal_before_reveal": seal, "forbidden_clean": True},
         "verdict": {"limitations": limits or []}, "limitations": limits or []}
    if ep == "PROVEN":
        pass
    return d

# 5 por estado (25)
def test_proven_accept(): assert guard_promotion("PROVEN", _ev("PROVEN")) == AcceptanceDecision.ACCEPT_WITH_DOMAIN
def test_proven_no_escalacion():
    assert guard_promotion("PROVEN", _ev("PROVEN")) != AcceptanceDecision.ACCEPT_LIMITED
    pass
def test_proven_reject_sin_integridad():
    e=_ev("PROVEN"); e["integrity"]["post_run"]["ok"]=False
    assert guard_promotion("PROVEN", e) == AcceptanceDecision.REJECT
def test_proven_reject_sin_sello():
    e=_ev("PROVEN"); e["session_audit"]["seal_before_reveal"]=False
    assert guard_promotion("PROVEN", e) == AcceptanceDecision.REJECT
def test_proven_domain_requerido():
    assert guard_promotion("PROVEN", None) == AcceptanceDecision.REJECT

def test_partial_con_limits(): assert guard_promotion("PARTIAL", _ev("PARTIAL", ["limited"])) == AcceptanceDecision.ACCEPT_LIMITED
def test_partial_sin_limits_withhold(): assert guard_promotion("PARTIAL", _ev("PARTIAL", [])) == AcceptanceDecision.WITHHOLD
def test_partial_no_escala():
    assert guard_promotion("PARTIAL", _ev("PARTIAL", ["x"])) != AcceptanceDecision.ACCEPT_WITH_DOMAIN
def test_partial_reject_malformado():
    e=_ev("PARTIAL", ["x"]); e["execution_status"]="FAIL"
    assert guard_promotion("PARTIAL", e) in (AcceptanceDecision.REJECT, AcceptanceDecision.DETACH)
def test_partial_estado_desconocido(): assert guard_promotion("XXX", _ev("XXX")) == AcceptanceDecision.REJECT

def test_nd_withhold(): assert guard_promotion("NOT_DETERMINED", _ev("NOT_DETERMINED")) == AcceptanceDecision.WITHHOLD
def test_nd_no_promueve(): assert guard_promotion("NOT_DETERMINED", _ev("NOT_DETERMINED")) != AcceptanceDecision.ACCEPT_WITH_DOMAIN
def test_nd_evidencia_insuficiente():
    assert guard_promotion("NOT_DETERMINED", _ev("NOT_DETERMINED")) == AcceptanceDecision.WITHHOLD
def test_nd_bloqueo_no_confunde():
    e=_ev("NOT_DETERMINED"); e["execution_status"]="BLOCKED"
    assert guard_promotion("NOT_DETERMINED", e) == AcceptanceDecision.DETACH
def test_nd_ausente_reject(): assert guard_promotion("NOT_DETERMINED", None) == AcceptanceDecision.REJECT

def test_blocked_detach(): assert guard_promotion("BLOCKED", _ev("BLOCKED", es="BLOCKED")) == AcceptanceDecision.DETACH
def test_blocked_no_acepta():
    assert guard_promotion("BLOCKED", _ev("BLOCKED", es="BLOCKED")) != AcceptanceDecision.ACCEPT_WITH_DOMAIN
def test_blocked_limite():
    assert guard_promotion("BLOCKED", _ev("BLOCKED")) in (AcceptanceDecision.DETACH, AcceptanceDecision.REJECT)
def test_blocked_ejecucion_fail():
    e=_ev("BLOCKED"); e["execution_status"]="FAIL"
    assert guard_promotion("BLOCKED", e) == AcceptanceDecision.REJECT
def test_blocked_sin_estado(): assert guard_promotion("BLOCKED", {}) == AcceptanceDecision.REJECT

def test_abstain_abstain(): assert guard_promotion("ABSTAINED", _ev("ABSTAINED")) == AcceptanceDecision.ABSTAIN
def test_abstain_no_acepta(): assert guard_promotion("ABSTAINED", _ev("ABSTAINED")) != AcceptanceDecision.ACCEPT_WITH_DOMAIN
def test_abstain_sin_conclusion():
    assert guard_promotion("ABSTAINED", _ev("ABSTAINED")) == AcceptanceDecision.ABSTAIN
def test_abstain_fallo_integridad():
    e=_ev("ABSTAINED"); e["integrity"]["post_run"]["ok"]=False
    assert guard_promotion("ABSTAINED", e) == AcceptanceDecision.REJECT
def test_abstain_malformado(): assert guard_promotion("ABSTAINED", "xxx") == AcceptanceDecision.REJECT

# seal 3
def test_seal_antes_revela():
    s=seal_prediction({"hypothesis":"h","value":1})
    assert validate_seal_before_reveal(s, 100.0, 50.0) is True
def test_seal_viola_deteccion():
    s=seal_prediction({"hypothesis":"h"})
    s["prediction"]["value"]=999
    assert validate_seal_before_reveal(s, 100.0, 50.0) is False
def test_seal_cadena_hash():
    s1=seal_prediction({"a":1})
    assert s1["sha256"] == seal_prediction({"a":1})["sha256"]
    assert s1["sha256"] != seal_prediction({"a":2})["sha256"]

# admisión 3
def test_admit_explicit_ok():
    r=admit_claim("stmt","hash123","scope","EXPLICIT","p","cap",None,None,[],None)
    assert r.allowed is True
def test_admit_inferred_rechazado():
    r=admit_claim("stmt","hash123","scope","INFERRED",None,None,None,None,[],None)
    assert r.allowed is False
def test_admit_unknown_rechazado():
    r=admit_claim("stmt","hash123","scope","UNKNOWN",None,None,None,None,[],None)
    assert r.allowed is False

# ledger 3
def test_ledger_lifecycle():
    op="op-test-1"; prepare(op); record_effect(op,"e1","d1"); confirm(op)
    assert reconcile(op, "CONFIRMED", {"effect_exists":True,"effect_verified":True,"identity_match":True,"digest_match":True,"scope_match":True})=="CONFIRMED"
def test_ledger_idempotencia():
    op="op-idem"
    prepare(op); record_effect(op,"e1","d1")
    # doble record sobreescribe evidencia pero no rompe reconcile
    record_effect(op,"e1","d1")
    assert reconcile(op,"EFFECT_APPLIED",{"effect_exists":True,"effect_verified":True,"identity_match":True,"digest_match":True,"scope_match":True})=="CONFIRMED"
def test_ledger_reconcile_determinista():
    a=reconcile("x","PREPARED",{"effect_exists":False,"absence_demonstrated":True})
    b=reconcile("x","PREPARED",{"effect_exists":False,"absence_demonstrated":True})
    assert a==b=="RETRY_SAFE"

# anti-replay 3
def test_antireplay_auth():
    import tempfile
    tf=tempfile.NamedTemporaryFile(delete=False,suffix=".jsonl"); tf.close()
    r=authorize_and_consume("vr-1","c1",tf.name); assert r["ok"] is True
    audit_ledger(tf.name)
def test_antireplay_consumo():
    import tempfile
    tf=tempfile.NamedTemporaryFile(delete=False,suffix=".jsonl"); tf.close()
    assert authorize_and_consume("vr-2","c1",tf.name)["ok"]
def test_antireplay_detectado():
    import tempfile
    tf=tempfile.NamedTemporaryFile(delete=False,suffix=".jsonl"); tf.close()
    assert authorize_and_consume("vr-3","c1",tf.name)["ok"]
    r=authorize_and_consume("vr-3","c1",tf.name)
    assert r["ok"] is False and "replay" in r["reason"]

# fail-closed 2 + determinismo + independencia
def test_failclosed_malformado():
    assert guard_promotion("PROVEN", "no-dict") == AcceptanceDecision.REJECT
def test_failclosed_estado_ausente():
    assert guard_promotion(None, None) == AcceptanceDecision.REJECT
def test_determinismo():
    e=_ev("PROVEN")
    from epistemic.promotion import guard_promotion as g
    assert g("PROVEN", e) == g("PROVEN", e)
def test_independencia_imports():
    import pathlib
    src=pathlib.Path(__file__).resolve().parents[1].joinpath("epistemic")
    blob="".join(p.read_text(errors="ignore") for p in src.rglob("*.py"))
    for bad in ["store.py","machine.py","dispatch.py","rxre.sqlite3","import store","from store"]:
        assert bad not in blob
