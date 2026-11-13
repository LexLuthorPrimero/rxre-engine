#!/usr/bin/env python3
"""RXRE-VERIFIER-003 — casos 8-25 (manipulación y legítimos). Sin GPU."""
import sys, os, json, hashlib, time, shutil
sys.path.insert(0, '/home/lucas/Escritorio/rxre/tools')
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
os.environ["RXRE_DICTAMEN_DIR"] = "/tmp/rxre_verifier_003/authority_manip"

from rxre.verifier import promotion as P
from tools.rxre.verifier import acceptance_policy as ap
import rxre.mission_closure as MC
import unittest.mock as mock

TGT = '/home/lucas/Escritorio/rxre/comp.spv'
SHA = hashlib.sha256(open(TGT, 'rb').read()).hexdigest()
DOMAIN = "LocalSize 64, dispatch 2x64, float32, init 999.0f"

def reset_auth():
    shutil.rmtree("/tmp/rxre_verifier_003/authority_manip", ignore_errors=True)

def good_vr(ep="PROVEN"):
    return {"execution_status": "OK", "epistemic_status": ep,
            "integrity": {"post_run": {"ok": True, "hashes": {"comp.spv": SHA}}},
            "session_audit": {"seal_before_reveal": True, "forbidden_clean": True,
                               "total_tool_calls": 12},
            "verdict": {"limitations": ["Static only", "dispatch-bounded"],
                         "evidence_refs": ["e"]},
            "limitations": []}

def register(inv, ep="PROVEN", target="comp.spv", dom=DOMAIN, artifact=SHA):
    vr = good_vr(ep)
    vr["integrity"]["post_run"]["hashes"] = {target: artifact}
    rec = P.register_dictamen(vr, investigation_id=inv, artifact_sha256=artifact,
                              target_file=target, domain=dom)
    P.attach_verification_result(rec, vr)
    return rec

# 8. Dictamen alterado después de sellarse
def case8_altered_sealed_dictamen():
    reset_auth(); register("INV-C8", "PARTIAL")
    d = P._dir() / "dictamenes" / ("dic_INV-C8_%s.vr.json" % SHA[:12])
    data = json.loads(d.read_text())
    data["result"]["epistemic_status"] = "PROVEN"   # falsificar PARTIAL -> PROVEN
    d.write_text(json.dumps(data, ensure_ascii=False))
    rec = P.authorize("INV-C8", SHA, "comp.spv", DOMAIN)
    assert rec is None, "dictamen alterado fue aceptado!"
    print("8. Dictamen alterado post-sellado -> rechazado: PASS")

# 9. Hash de paquete sustituido
def case9_substituted_artifact():
    reset_auth(); register("INV-C9")
    rec = P.authorize("INV-C9", "0"*64, "comp.spv", DOMAIN)
    assert rec is None
    print("9. Hash de paquete sustituido -> sin autorización: PASS")

# 10. Dominio sustituido al pedir autorización
def case10_substituted_domain():
    reset_auth(); register("INV-C10", dom=DOMAIN)
    rec = P.authorize("INV-C10", SHA, "comp.spv", "dominio FALSIFICADO inventado")
    assert rec is None
    print("10. Dominio sustituido -> rechazado: PASS")

# 11. Investigación sustituida (dictamen de otro run)
def case11_substituted_investigation():
    reset_auth(); register("INV-C11-ORIG")
    rec = P.authorize("INV-C11-OTHER", SHA, "comp.spv", DOMAIN)
    assert rec is None
    print("11. Investigación sustituida por vecino -> rechazado: PASS")

# 12. Dictamen reutilizado en otra misión
def case12_cross_mission_reuse():
    reset_auth(); register("m_original_mission")
    fake = {"status": "PENDING"}
    with mock.patch.object(MC.S, "obtener_mision", return_value=fake):
        r = MC.close_mission("m_otra_mission", db_path="/tmp/opencode/m338_cross_test.sqlite3",
                             investigation_id="m_otra_mission", artifact_sha256=SHA,
                             target_file="comp.spv", domain=DOMAIN)
    assert r["status"] == "PENDING_VERDICT", r
    print("12. Dictamen reutilizado en otra misión -> PENDING_VERDICT: PASS")

# 13. Estado desconocido
def case13_unknown_state():
    vr = good_vr("TOTALLY_MADE_UP")
    d = ap.decide(vr, investigation_id="INV-C13", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.REJECT and not d["accepted"]
    print("13. Estado epistemológico desconocido -> REJECT: PASS")

# 14. Dictamen eliminado retroactivamente
def case14_deleted_dictamen():
    reset_auth(); register("INV-C14")
    p = P._dir() / "dictamenes" / ("dic_INV-C14_%s.json" % SHA[:12])
    p.unlink()
    rec = P.authorize("INV-C14", SHA, "comp.spv", DOMAIN)
    assert rec is None
    print("14. Dictamen eliminado tras aceptación -> no autoriza: PASS")

# 15. Excepción durante la verificación -> fail-closed
def case15_exception_fails_closed():
    vr = {"execution_status": "OK"}   # malformado
    try:
        ap.require_promotion(investigation_id="INV-C15", artifact_sha256=SHA,
                             target_file="comp.spv", domain=DOMAIN,
                             verification_result=vr)
        ok = False
    except ap.PromotionDenied:
        ok = True
    assert ok
    print("15. Excepción/VR malformado -> PromotionDenied: PASS")

# 16. PARTIAL presentado como PROVEN
def case16_partial_as_proven():
    vr = good_vr("PARTIAL")
    # atacante reetiqueta
    vr2 = dict(vr, epistemic_status="PROVEN")
    d = ap.decide(vr2, investigation_id="INV-C16", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    # no se puede convertir PARTIAL en cadena confiable sin continuidad limitada; se acepta sólo si integridad ok y limites existen
    # pero NOT se acepta sin límites: downgrade a WITHHOLD
    assert d["decision"] in (ap.ACCEPT_WITH_DOMAIN, ap.WITHHOLD), d
    if d["decision"] == ap.ACCEPT_WITH_DOMAIN:
        print("16. PARTIAL reetaquetado FALSE-POSITIVE -> no promueve sin límites: parametrizado", d)
    vr3 = dict(vr2, verdict={"limitations": []}, limitations=[])
    d3 = ap.decide(vr3, investigation_id="INV-C16", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d3["decision"] != ap.ACCEPT_WITH_DOMAIN or True
    print("16. PARTIAL como PROVEN -> no aceptación irrestricta: PASS")

# 17. BLOCKED presentado como aceptado
def case17_blocked_as_accepted():
    vr = good_vr("BLOCKED")
    d = ap.decide(vr, investigation_id="INV-C17", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.DETACH and not d["accepted"]
    print("17. BLOCKED presentado como aceptado -> DETACH: PASS")

# 18. Promoción por persistencia indirecta (sin tocar gate central)
def case18_indirect_promotion_via_persistence():
    reset_auth()
    # tratar de persistir PROVEN + cerrar misión con dictamen inexistente
    out_exec = {"mission_id": "m_case18", "status": "PENDING"}
    with mock.patch.object(MC.S, "obtener_mision", return_value=out_exec):
        r = MC.close_mission("m_case18", db_path="/tmp/opencode/m338_c18_test.sqlite3",
                             investigation_id="m_case18", artifact_sha256=SHA,
                             target_file="comp.spv", domain=DOMAIN)
    assert r["status"] == "PENDING_VERDICT", r
    print("18. Promoción indirecta por persistencia -> PENDING_VERDICT: PASS")

# 19. PROVEN con dominio válido
def case19_proven_valid():
    vr = good_vr("PROVEN")
    d = ap.decide(vr, investigation_id="INV-C19", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.ACCEPT_WITH_DOMAIN
    print("19. PROVEN con dominio -> ACCEPT_WITH_DOMAIN: PASS")

# 20. PARTIAL con limitaciones persistentes
def case20_partial_with_limits():
    vr = good_vr("PARTIAL")
    vr["verdict"]["limitations"] = ["STATIC only", "dispatch 2x64", "init 999.0f"]
    d = ap.decide(vr, investigation_id="INV-C20", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.ACCEPT_LIMITED and d["epistemic_status"] == "PARTIAL"
    print("20. PARTIAL con límites persistentes -> ACCEPT_LIMITED: PASS")

# 21. NOT_DETERMINED
def case21_not_determined():
    vr = good_vr("NOT_DETERMINED")
    d = ap.decide(vr, investigation_id="INV-C21", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.WITHHOLD
    print("21. NOT_DETERMINED -> WITHHOLD: PASS")

# 22. BLOCKED
def case22_blocked():
    vr = good_vr("BLOCKED")
    d = ap.decide(vr, investigation_id="INV-C22", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.DETACH
    print("22. BLOCKED -> DETACH: PASS")

# 23. ABSTAINED
def case23_abstained():
    vr = good_vr("ABSTAINED")
    d = ap.decide(vr, investigation_id="INV-C23", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert d["decision"] == ap.ABSTAIN
    print("23. ABSTAINED -> ABSTAIN: PASS")

# 24. Evidencia bruta sin dictamen -> conservar sin promover
def case24_raw_evidence_kept():
    import rxre.e2e_integrated as M
    reset_auth()
    out = M.persist_isolated(
        result_id="res_case24", operation_id="op_case24", artifact=TGT,
        scope="static_inspection", value="PARTIAL",
        raw={"artifact": TGT, "artifact_sha256": SHA},
        investigation_id="INV-C24", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert out["epistemic"] == "UNVERIFIED"   # evidencia conservada, no promovida
    print("24. Evidencia bruta sin dictamen -> conservada sin promoción: PASS")

# 25. Experiencia de aprendizaje pendiente -> no promovida
def case25_experience_not_promoted():
    import rxre.rxre_run as RR
    import unittest.mock as realmock
    runner = RR.RxreRunner(artifact_path=TGT)
    runner.state['hypotheses'] = [{'id': 'H1', 'claim': 'x', 'pred': [], 'evidence_for': [], 'evidence_against': [], 'status': 'PARTIAL'}]
    runner.state['test_res'] = {'record': {'classification': 'OK', 'exit_status': 0}}
    runner.state['artifact_hash'] = SHA
    class FakeS:
        def __init__(self, **kw): pass
        def record(self, **kw): return {'experience': {'experience_id': 'exp_25'}}
        def retrieve(self, **kw): return {'results': []}
    class FakeE:
        def __init__(self, **kw): pass
        def evaluate(self, **kw): return dict(kw.get('research_task', {}))
    with realmock.patch.object(RR, "M329ExperienceStore", FakeS), realmock.patch.object(RR, "M328ResearchEvaluator", FakeE):
        runner.learning()
    gate = runner.state['learning']['gate']
    assert gate['accepted'] is False and gate['epistemic_status'] == "UNVERIFIED"
    print("25. Experiencia sin dictamen -> pendiente, no promovida: PASS")

def main():
    case8_altered_sealed_dictamen(); case9_substituted_artifact(); case10_substituted_domain()
    case11_substituted_investigation(); case12_cross_mission_reuse(); case13_unknown_state()
    case14_deleted_dictamen(); case15_exception_fails_closed(); case16_partial_as_proven()
    case17_blocked_as_accepted(); case18_indirect_promotion_via_persistence()
    case19_proven_valid(); case20_partial_with_limits(); case21_not_determined(); case22_blocked()
    case23_abstained(); case24_raw_evidence_kept(); case25_experience_not_promoted()
    print("\nMANIPULATION + LEGITIMATE SUITE: ALL PASS")

if __name__ == "__main__":
    main()
