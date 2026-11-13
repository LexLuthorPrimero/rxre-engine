#!/usr/bin/env python3
"""Test suite A-J de la política de aceptación (offline, sintético)."""
import sys, json, hashlib, os, tempfile
from pathlib import Path
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.verifier import acceptance_policy as ap

SPV = "tests-target.spv"
HASH = hashlib.sha256(b"fake-spv-bytes").hexdigest()
DOMAIN = "LocalSize 64, dispatch 2x64, float32, inputativo float secuencial, init 999.0f"

def good_vr(ep="PROVEN", integrity_ok=True, seal=True, forbidden=True, target=HASH):
    return {
        "execution_status": "OK",
        "epistemic_status": ep,
        "integrity": {"post_run": {"ok": integrity_ok,
                                     "hashes": {SPV: target}}},
        "session_audit": {"seal_before_reveal": seal,
                           "forbidden_clean": forbidden,
                           "total_tool_calls": 9},
        "verdict": {"limitations": ["Static analysis only", "dispatch-bounded"]},
        "limitations": [],
    }

def run():
    td = tempfile.mkdtemp(prefix="ap_test_")
    t = 0
    ok = []
    # Caso A — PROVEN acotado
    d = ap.decide(good_vr("PROVEN"), investigation_id="inv-1", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("A PROVEN acotado", d["decision"] == ap.ACCEPT_WITH_DOMAIN and d["accepted"]))
    # Caso B — PARTIAL con límites no se promueve a PROVEN
    d = ap.decide(good_vr("PARTIAL"), investigation_id="inv-2", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("B PARTIAL limitado", d["decision"] == ap.ACCEPT_LIMITED and d["epistemic_status"] != "PROVEN"))
    # Caso C — NOT_DETERMINED sin promoción
    d = ap.decide(good_vr("NOT_DETERMINED"), investigation_id="inv-3", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("C NOT_DETERMINED withhold", d["decision"] == ap.WITHHOLD and not d["accepted"]))
    # Caso D — BLOCKED detiene
    d = ap.decide(good_vr("BLOCKED"), investigation_id="inv-4", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("D BLOCKED halt", d["decision"] == ap.DETACH and not d["accepted"]))
    # Caso E — ABSTAINED abstiene
    d = ap.decide(good_vr("ABSTAINED"), investigation_id="inv-5", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("E ABSTAINED abstain", d["decision"] == ap.ABSTAIN and not d["accepted"]))
    # Caso F — integridad comprometida rechaza
    d = ap.decide(good_vr("PROVEN", integrity_ok=False), investigation_id="inv-6", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("F integridad comprometida", d["decision"] == ap.REJECT and not d["accepted"]))
    # Caso G — verificación ausente rechaza
    d = ap.decide(None, investigation_id="inv-7", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("G verificacion ausente", d["decision"] == ap.REJECT and not d["accepted"]))
    # Caso H — dictamen de otra investigación/dominio se rechaza
    d = ap.decide(good_vr("PROVEN", target="0" * 64), investigation_id="inv-8", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("H cross-research/domain mismatch", d["decision"] == ap.REJECT and not d["accepted"]))
    # Caso I — excepción tratada como promoción bloqueada
    try:
        ap.require_promotion(investigation_id="inv-9", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN, verification_result=None)
        t += 1; ok.append(("I excepción bloquea", False))
    except ap.PromotionDenied:
        t += 1; ok.append(("I excepción bloquea", True))
    # Caso J — atacante intenta rutas alternativas / estados falsificados
    fake = dict(good_vr("PROVEN")); fake["execution_status"] = "OK"
    fake["epistemic_status"] = "GARBAGE_STATE"
    d = ap.decide(fake, investigation_id="inv-10", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("J estado desconocido rechazado", d["decision"] == ap.REJECT))
    fake2 = dict(good_vr("PROVEN")); fake2["session_audit"]["seal_before_reveal"] = False
    d = ap.decide(fake2, investigation_id="inv-11", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("J seal ausente rechazado", d["decision"] == ap.REJECT))
    fake3 = dict(good_vr("PROVEN", forbidden=False))
    d = ap.decide(fake3, investigation_id="inv-12", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("J forbidden refs rechazado", d["decision"] == ap.REJECT))
    fake4 = dict(good_vr("PROVEN")); fake4["verdict"] = {"limitations": []}
    fake4["limitations"] = []
    # PROVEN sin límites persistentes: permitido dentro de dominio (limites opcionales para aceptar)
    # pero si execution_status cambia -> rechazado
    fake5 = dict(good_vr("PROVEN")); fake5["execution_status"] = "BLOCKED"
    d = ap.decide(fake5, investigation_id="inv-13", artifact_sha256=HASH, target_file=SPV, domain=DOMAIN)
    t += 1; ok.append(("J execution BLOCKED -> DETACH", d["decision"] == ap.DETACH and not d["accepted"]))
    # Domain ausente -> REJECT
    d = ap.decide(good_vr("PROVEN"), investigation_id="inv-14", artifact_sha256=HASH, target_file=SPV, domain="")
    t += 1; ok.append(("J dominio ausente rechazado", d["decision"] == ap.REJECT))
    for name, res in ok:
        print(("PASS" if res else "FAIL"), "-", name)
    total = len(ok); passed = sum(1 for _, r in ok if r)
    print(f"\n{passed}/{total} checks PASS")
    if passed != total:
        sys.exit(1)
    print("ACCEPTANCE POLICY SUITE: ALL PASS")

if __name__ == "__main__":
    run()
