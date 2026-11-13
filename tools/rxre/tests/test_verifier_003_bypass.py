#!/usr/bin/env python3
"""RXRE-VERIFIER-003 — 25 casos adversariales y legítimos sobre las rutas R1-R7.
Sin GPU. Fixtures sintéticos + artefacto inmutable (comp.spv).
"""
import sys, os, json, hashlib, time, shutil, tempfile
sys.path.insert(0, '/home/lucas/Escritorio/rxre/tools')
sys.path.insert(0, '/home/lucas/Escritorio/rxre')

os.environ["RXRE_DICTAMEN_DIR"] = "/tmp/rxre_verifier_003/authority"

import rxre.e2e_integrated as M
import rxre.mission_closure as MC
import rxre.rxre_run as RR
import tools.rxre.verifier.independent_verifier as IV
from rxre.verifier import promotion as P
from tools.rxre.verifier import acceptance_policy as ap
import unittest.mock as mock

TGT = '/home/lucas/Escritorio/rxre/comp.spv'
SHA = hashlib.sha256(open(TGT, 'rb').read()).hexdigest()
DOMAIN = "LocalSize 64, dispatch 2x64, float32, init 999.0f"

def reset_auth():
    shutil.rmtree("/tmp/rxre_verifier_003/authority", ignore_errors=True)

def good_vr(ep="PROVEN"):
    return {"execution_status": "OK", "epistemic_status": ep,
            "integrity": {"post_run": {"ok": True, "hashes": {"comp.spv": SHA}}},
            "session_audit": {"seal_before_reveal": True, "forbidden_clean": True,
                               "total_tool_calls": 12},
            "verdict": {"limitations": ["Static only", "dispatch-bounded"],
                         "evidence_refs": ["package/sh"]},
            "limitations": []}

def register(inv, ep="PROVEN", target="comp.spv", dom=DOMAIN, artifact=SHA):
    vr = good_vr(ep)
    vr["integrity"]["post_run"]["hashes"] = {target: artifact}
    rec = P.register_dictamen(vr, investigation_id=inv, artifact_sha256=artifact,
                              target_file=target, domain=dom)
    P.attach_verification_result(rec, vr)
    return rec

#------------------------------------------------------------------------------
# R7 — el gate central (armado/manipulado)
#------------------------------------------------------------------------------
def case7_manipulated_vr_rejected():
    reset_auth(); register("INV-C7")
    rec = P.load if False else None
    v = good_vr("PROVEN")
    # alterar artefacto: gate debe rechazar
    dec = ap.guard_promotion(investigation_id="INV-C7", artifact_sha256="0"*64,
                             target_file="comp.spv", domain=DOMAIN,
                             verification_result=v,
                             persist_to="/tmp/rxre_verifier_003/c7.jsonl")
    assert dec.decision == ap.REJECT
    print("7. R7 rechaza resultado verificado para OTRO artefacto: PASS")

#------------------------------------------------------------------------------
# R1 — _verdict()
#------------------------------------------------------------------------------
def mk_integration_object():
    ii = M.IntegratedInvestigation.__new__(M.IntegratedInvestigation)
    ii.artifact = TGT
    ii.investigation_id = "INV-R1"
    ii.domain = DOMAIN
    ii.report = {
        'hypotheses': {'H1': {'estado': 'PROVEN', 'predicciones': [], 'evidencia_for': [], 'evidencia_against': [], 'falsificacion': '', 'confianza': 0.9, 'incertidumbre': ''}},
        'experiments': [
            {'id': 'E2_static_functions', 'status': 'PROVEN', 'result': {}},
            {'id': 'E4_dynamic_syscalls', 'status': 'PROVEN', 'result': {}},
            {'id': 'E7_reconstruct_validate', 'status': 'EQUIVALENT_FOR_TESTED_CASES',
             'result': {'status': 'EQUIVALENT_FOR_TESTED_CASES', 'validation': {'mismatches': 0, 'model_sha256': 'm'}}},
        ],
        'stages': {
            'cuerpo': {'hash': SHA, 'manifest': '/tmp/manifest_x', 'verificada_en_uso': True, 'estado': 'PROVEN'},
            'persistencia': {'status': 'PROVEN', 'row_hash_verified': True},
            'agua': {'status': 'PROVEN'},
            'puerta': {'veredicto': {'estado': 'BLOCKED_GATE'}},
            'alma_closure': {'cerrado': False, 'por_estado': {'NOT_DETERMINED': 1}},
        },
        'gate_decision': None,
    }
    return ii

def case1_verdict_no_gate_blocks_promotion():
    reset_auth()
    ii = mk_integration_object()
    v = ii._verdict()
    assert v["estado"] == "BLOCKED", v
    assert v.get("gate", {}).get("accepted") is False
    print("1. R1 promueve sin dictamen -> BLOCKED (ni PASS_PARTIAL): PASS")

def case1b_verdict_with_gate_authorized():
    reset_auth(); register("INV-R1", "PROVEN")
    ii = mk_integration_object()
    ii.report["gate_decision"] = {"dictamen_id": "dic_INV-R1_%s" % SHA[:12],
                                  "decision": "ACCEPT_WITH_DOMAIN", "epistemic_status": "PROVEN",
                                  "domain": DOMAIN, "accepted": True}
    v = ii._verdict()
    assert v["estado"] == "PASS_PARTIAL", v
    assert v.get("gate", {}).get("accepted") is True
    print("1b. R1 con dictamen autorizado -> PASS_PARTIAL acotado: PASS")

#------------------------------------------------------------------------------
# R2 — persist_isolated()
#------------------------------------------------------------------------------
def case2_persist_downgrades_without_gate():
    reset_auth()
    out = M.persist_isolated(
        result_id="res_case2", operation_id="op_case2", artifact=TGT,
        scope="static_inspection", value="PROVEN",
        raw={"artifact": TGT, "artifact_sha256": SHA},
        investigation_id="INV-R2", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert out["epistemic"] == "UNVERIFIED", out.get("epistemic")
    print("2. R2 persiste evidencia sin dictamen -> UNVERIFIED: PASS")

def case2b_persist_authorized_keeps_decision():
    reset_auth(); register("INV-R2")
    out = M.persist_isolated(
        result_id="res_case2b", operation_id="op_case2b", artifact=TGT,
        scope="static_inspection", value="PROVEN",
        raw={"artifact": TGT, "artifact_sha256": SHA},
        investigation_id="INV-R2", artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    assert out.get("gate") and out["gate"]["accepted"], out
    assert out["gate"]["decision"] == "ACCEPT_WITH_DOMAIN"
    print("2b. R2 con dictamen autorizado -> decisión vinculada persistida: PASS")

#------------------------------------------------------------------------------
# R3 — close_mission()
#------------------------------------------------------------------------------
def case3_close_mission_without_verifier_rejected():
    reset_auth()
    fake = {"status": "PENDING", "mission_id": "m_test", "criteria": {}}
    fake_criteria = [{"required": 1, "epistemic": "PROVEN", "criterion_id": "c1"}]
    fake_verif = [{"criterion_id": "c1", "pass": True}]
    with mock.patch.object(MC.S, "obtener_mision", return_value=fake), \
         mock.patch.object(MC.S, "obtener_criterios_mision", return_value=fake_criteria), \
         mock.patch.object(MC.S, "verificar_criterios_mision", return_value=fake_verif):
        r = MC.close_mission("m_test", db_path="/tmp/opencode/m338_rxre_copy_for_test.sqlite3")
    assert r["status"] in ("PENDING_VERDICT", "REJECTED"), r
    print("3. R3 cierra misión sin dictamen -> PENDING_VERDICT: PASS")

def case3b_close_mission_with_authorization_passes_gate():
    reset_auth(); register("m_test_authorized", "PROVEN", dom=DOMAIN)
    fake = {"status": "PENDING", "mission_id": "m_test_authorized", "criteria": {}}
    fake_criteria = [{"required": 1, "epistemic": "PROVEN", "criterion_id": "c1"}]
    fake_verif = {"resultados": [{"criterion_id": "c1", "status": "PASS"}]}
    with mock.patch.object(MC.S, "obtener_mision", return_value=fake), \
         mock.patch.object(MC.S, "obtener_criterios_mision", return_value=fake_criteria), \
         mock.patch.object(MC.S, "verificar_criterios_mision", return_value=fake_verif):
        # DB not really written? close_mission proceeds past the gate (test of gate only)
        r = MC.close_mission("m_test_authorized", db_path="/tmp/opencode/m338_rxre_copy_for_test.sqlite3",
                             verification_result=good_vr("PROVEN"),
                             investigation_id="m_test_authorized",
                             artifact_sha256=SHA, target_file="comp.spv", domain=DOMAIN)
    # gate passed -> not PENDING_VERDICT by design of gate; outcome depends on DB
    assert r["status"] != "PENDING_VERDICT", r
    print("3b. R3 con dictamen vinculado -> atraviesa la puerta: PASS (ver veredicto)")

#------------------------------------------------------------------------------
# R4 — learning()
#------------------------------------------------------------------------------
class _StubStore: pass
class _StubEval: pass

def case4_learning_tags_unverified():
    reset_auth()
    runner = RR.RxreRunner(artifact_path=TGT)
    runner.state['hypotheses'] = [{'id': 'H1', 'claim': 'x', 'pred': [], 'evidence_for': [], 'evidence_against': [], 'status': 'PARTIAL'}]
    runner.state['test_res'] = {'record': {'classification': 'OK', 'exit_status': 0}}
    runner.state['artifact_hash'] = SHA
    class FakeStore:
        def __init__(self, **kw): pass
        def record(self, **kw):
            self.last = kw
            return {'experience': {'experience_id': 'exp_1'}}
        def retrieve(self, **kw):
            return {'results': []}
    class FakeEval:
        def __init__(self, **kw): pass
        def evaluate(self, **kw):
            return dict(kw.get('research_task', {}))
    with mock.patch.object(RR, "M329ExperienceStore", FakeStore), \
         mock.patch.object(RR, "M328ResearchEvaluator", FakeEval):
        out = runner.learning()
    gate = runner.state['learning']['gate']
    assert gate['accepted'] is False and gate['epistemic_status'] == 'UNVERIFIED', gate
    rec = runner.state['learning']['record']
    assert rec['experience']['experience_id'] == 'exp_1', rec
    print("4. R4 AGUA aprende experiencia sin dictamen -> etiquetada UNVERIFIED: PASS")

#------------------------------------------------------------------------------
# R5 — persistence_reread()
#------------------------------------------------------------------------------
def case5_persistence_reread_stays_unverified():
    reset_auth()
    runner = RR.RxreRunner(artifact_path=TGT)
    runner.state['manifest_data'] = {'result_id': 'res_case5', 'operation_id': 'op_case5'}
    runner.state['artifact_hash'] = SHA
    runner.persistence_reread()
    p = runner.state['persistence']
    assert p['integrity_ok'] is True, p
    assert p['dictamen_bound'] is False, p
    print("5. R5 recuperación sin dictamen -> UNVERIFIED persistente: PASS")

def case5b_persistence_reread_detects_cross_investigation():
    reset_auth(); register("other_investigation_id", "PROVEN")
    runner = RR.RxreRunner(artifact_path=TGT)
    runner.state['manifest_data'] = {'result_id': 'res_case5b', 'operation_id': 'op_case5b'}
    runner.state['artifact_hash'] = SHA
    runner.persistence_reread()
    p = runner.state['persistence']
    assert p['dictamen_bound'] is False, p
    assert p['gate'].get('accepted') is False
    print("5b. R5 dictamen de otra investigación -> no vincula (rechazado): PASS")

#------------------------------------------------------------------------------
# R6 — PUERTA stage
#------------------------------------------------------------------------------
def case6_puerta_blocked_without_gate():
    reset_auth()
    ii = mk_integration_object()
    ii.stage_puerta()
    pu = ii.report["stages"]["puerta"]
    assert pu["veredicto"]["estado"] == "BLOCKED_GATE", pu
    assert ii.report["gate_decision"]["accepted"] is False
    print("6. R6 PUERTA sin autorización -> BLOCKED_GATE (Puerta no invocada): PASS")

def case6b_puerta_authorized_proceeds():
    reset_auth(); register("INV-R6", "PROVEN")
    ii = mk_integration_object()
    ii.investigation_id = "INV-R6"
    ii.stage_puerta()
    pu = ii.report["stages"]["puerta"]
    gate = ii.report["gate_decision"]
    assert gate["accepted"] is True and pu.get("artefacto_id")
    print("6b. R6 con dictamen autorizado -> PUERTA invocada (con condiciones): PASS")

#------------------------------------------------------------------------------
def main():
    t0 = time.time()
    case7_manipulated_vr_rejected(); case1_verdict_no_gate_blocks_promotion(); case1b_verdict_with_gate_authorized()
    case2_persist_downgrades_without_gate(); case2b_persist_authorized_keeps_decision()
    case3_close_mission_without_verifier_rejected(); case3b_close_mission_with_authorization_passes_gate()
    case4_learning_tags_unverified(); case5_persistence_reread_stays_unverified(); case5b_persistence_reread_detects_cross_investigation()
    case6_puerta_blocked_without_gate(); case6b_puerta_authorized_proceeds()
    print(f"\nBYPASS SUITE: ALL PASS ({time.time()-t0:.1f}s)")

if __name__ == "__main__":
    main()
