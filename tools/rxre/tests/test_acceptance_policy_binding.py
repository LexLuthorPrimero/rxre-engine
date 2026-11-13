#!/usr/bin/env python3
"""Binding/persistencia/bypass de la política de aceptación (offline)."""
import sys, json, hashlib, os, tempfile
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.verifier import acceptance_policy as ap

SPV = "target.spv"
HASH = hashlib.sha256(b"artifact-bytes").hexdigest()
DOMAIN = "LocalSize 64, dispatch 2x64, float32, init 999.0f, input float seq 0..127"

def good_vr():
    return {"execution_status": "OK", "epistemic_status": "PROVEN",
            "integrity": {"post_run": {"ok": True, "hashes": {SPV: HASH}}},
            "session_audit": {"seal_before_reveal": True, "forbidden_clean": True},
            "verdict": {"limitations": ["Static analysis only"]},
            "limitations": []}

def t_binding_mismatch_rejected():
    td = tempfile.mktemp(prefix="ap_bind_")
    ap_path = td + ".jsonl"
    ev = tempfile.NamedTemporaryFile(delete=False, suffix=".spv")
    ev.write(b"not the hash"); ev.close()
    dec = ap.guard_promotion(investigation_id="inv-bind-1", artifact_sha256=HASH,
                             target_file=SPV, domain=DOMAIN,
                             verification_result=good_vr(),
                             investigation_artifact=ev.name, persist_to=ap_path)
    os.unlink(ev.name)
    rec = json.loads(open(ap_path).read().strip())
    assert dec.decision == ap.REJECT and not dec.accepted
    assert rec["investigation_id"] == "inv-bind-1"
    print("T-binding investigación<->dictamen mismatch rechazado y persistido: PASS")

def t_persisted_record_content():
    td = tempfile.mkdtemp(prefix="ap_rec_")
    persist = os.path.join(td, "dictamenes.jsonl")
    dec = ap.guard_promotion(investigation_id="inv-bind-2", artifact_sha256=HASH,
                             target_file=SPV, domain=DOMAIN,
                             verification_result=good_vr(), persist_to=persist)
    recs = [json.loads(l) for l in open(persist)]
    assert dec.accepted and dec.decision == ap.ACCEPT_WITH_DOMAIN
    assert recs[0]["artifact_sha256"] == HASH and recs[0]["investigation_id"] == "inv-bind-2"
    assert recs[0]["domain"] == DOMAIN
    print("T-persistencia dictamen vinculado y dominio conservado: PASS")

def t_cross_research_reuse_rejected():
    vr = good_vr()
    d = ap.decide(vr, investigation_id="inv-bind-3", artifact_sha256="f" * 64,
                  target_file=SPV, domain=DOMAIN)
    assert d["decision"] == ap.REJECT
    print("T-dictamen reutilizado de otra investigación rechazado: PASS")

def t_alternative_path_gate_only_accepts_policy():
    # el gate es la única ruta que puede aceptar; todo lo demás queda fuera de alcance
    vr = good_vr(); vr["epistemic_status"] = "BLOCKED"
    d = ap.decide(vr, investigation_id="inv-bind-4", artifact_sha256=HASH,
                  target_file=SPV, domain=DOMAIN)
    assert d["decision"] == ap.DETACH and not d["accepted"]
    print("T-ruta alternativa con dictamen BLOCKED detenida: PASS")

def t_malformed_verification_rejected():
    for bad in [None, {}, {"execution_status": "OK"}, {"execution_status": "OK", "epistemic_status": "PROVEN", "integrity": {"post_run": {"ok": False}}}]:
        d = ap.decide(bad, investigation_id="inv-bind-5", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
        assert d["decision"] in (ap.REJECT, ap.DETACH), d
    print("T-resultados ausente/vacío/malformado rechazados: PASS")

t_binding_mismatch_rejected(); t_persisted_record_content()
t_cross_research_reuse_rejected(); t_alternative_path_gate_only_accepts_policy()
t_malformed_verification_rejected()
print("BINDING/PERSISTENCE SUITE: ALL PASS")
