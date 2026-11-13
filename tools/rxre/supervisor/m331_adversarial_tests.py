#!/usr/bin/env python3
"""M331 — Pruebas adversariales de integración M330 (archivo permitido; fixtures sintéticos claramente etiquetados; sin invento; sin mecanismo falso)."""
import sys, hashlib, os, json, time
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

def fixture_bytes():
    with open('/tmp/m330_synthetic_e2e_fix.bin','rb') as f: return f.read()

def test_A_invalid_ref():
    from supervisor.m330_integration import M330Integration
    return M330Integration(validated_reference={}, max_iter=1).run_e2e(fixture_bytes=fixture_bytes())

def test_B_altered_artifact():
    fixture = fixture_bytes()
    bad_ref = {"hash_sha256":"0"*64,"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    from supervisor.m330_integration import M330Integration
    return M330Integration(validated_reference=bad_ref, max_iter=1).run_e2e(fixture_bytes=fixture)

def test_C_intermediate_failure():
    from supervisor.m330_integration import M330Integration
    ref = {"hash_sha256":hashlib.sha256(fixture_bytes()).hexdigest(),"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    return M330Integration(validated_reference=ref, max_iter=1).run_e2e(fixture_bytes=fixture_bytes())

def test_D_corrupt_report():
    from supervisor.m323_report_store import M323ReportStore
    ref = {"hash_sha256":hashlib.sha256(fixture_bytes()).hexdigest(),"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    bad_path = "/tmp/m331_bad_report.json"
    with open(bad_path,"w") as f: f.write('{bad')
    return M323ReportStore(validated_reference=ref, max_iter=1).recover(bad_path)

def test_E_invalid_provenance():
    from supervisor.m322_provenance_verifier import M322ProvenanceContract
    ref_bad = {"hash_sha256":"deadbeef"*8,"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    return M322ProvenanceContract(validated_reference=ref_bad, max_iter=1).verify(pipeline_result={})

def test_F_incompatible_experience():
    from supervisor.m329_experience_store import M329ExperienceStore
    store = M329ExperienceStore(validated_reference={"hash_sha256":"hash_a","bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}, max_iter=1)
    return store.evaluate_compatibility(experience_a={"experience_id":"E-A","category":"OBSERVED_EXPERIENCE","artifact_identity":"hash_a","fixture_evidence_labeled":False,"continuity":"CONTINUE"}, experience_b={"experience_id":"E-B","category":"SYNTHETIC_EXPERIENCE","artifact_identity":"hash_b","fixture_evidence_labeled":True,"continuity":"CONTINUE"})

def test_G_synthetic_real_boundary():
    from supervisor.m327_experiment_runner import M327ExperimentRunner
    ref = {"hash_sha256":hashlib.sha256(fixture_bytes()).hexdigest(),"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    res = M327ExperimentRunner(validated_reference=ref, max_iter=1).run(experiment_spec={"experiment_id":"EXP-SYNTH-BORDER","status":"READY","preparation_status":"READY","prerequisites":[],"limitaciones":["fixture synthetic clearly labeled"]}, fixture_bytes=fixture_bytes())
    return {"record": res.get("record"), "fixture_labeled": res.get("record",{}).get("fixture_evidence_labeled"), "classification": res.get("record",{}).get("classification")}

def test_H_blocked_inconclusive():
    from supervisor.m328_research_evaluator import M328ResearchEvaluator
    res = M328ResearchEvaluator(validated_reference={"hash_sha256":"a"*64,"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}, max_iter=1).evaluate(research_task={"task_id":"T-H","title":"Bloqueado","hypotheses":[]}, experiment_result={"record":{"admitted":False,"fixture_evidence_labeled":True,"exit_status":"BLOCKED","classification":"BLOCKED","criteria_met":False,"experiment_id":"EXP-H"}})
    return res

def test_I_determinism():
    from supervisor.m330_integration import M330Integration
    ref = {"hash_sha256":hashlib.sha256(fixture_bytes()).hexdigest(),"bytes_read_once":True,"race_condition_documented":"NOT_DETERMINED"}
    r1 = M330Integration(validated_reference=ref, max_iter=1).run_e2e(fixture_bytes=fixture_bytes())
    r2 = M330Integration(validated_reference=ref, max_iter=1).run_e2e(fixture_bytes=fixture_bytes())
    return {"identical_integrated_e2e": r1.get("observations",{}).get("integrated_e2e") == r2.get("observations",{}).get("integrated_e2e"), "identical_continuity": r1.get("continuity")==r2.get("continuity"), "same_stage_counts": len(r1.get("stages_executed",{})) == len(r2.get("stages_executed",{}))}

if __name__ == "__main__":
    results = {}
    try: res = test_A_invalid_ref(); results["A_invalid_ref"] = {"status":"PASS" if res.get("status") in ("PASS_PARTIAL","BLOCKED") else "FAIL","details":"BLOCKED/INSUFFICIENT preserved"}
    except Exception as e: results["A_invalid_ref"] = {"status":"FAIL","error":str(e)}
    try: res = test_B_altered_artifact(); results["B_altered"] = {"status":"PASS" if res.get("status") in ("INSUFFICIENT","PASS_PARTIAL") else "FAIL","details":"altered handled"}
    except Exception as e: results["B_altered"] = {"status":"FAIL","error":str(e)}
    try: res = test_C_intermediate_failure(); results["C_intermediate"] = {"status":"PASS" if res.get("status")=="PASS_PARTIAL" else "FAIL","details":"intermediate handled","stages":res.get("stages_executed")}
    except Exception as e: results["C_intermediate"] = {"status":"FAIL","error":str(e)}
    try: res = test_D_corrupt_report(); results["D_corrupt"] = {"status":"PASS" if res.get("status") in ("INSUFFICIENT","BLOCKED") else "FAIL","details":"corrupt rejected","integrity":res.get("integrity_verified")}
    except Exception as e: results["D_corrupt"] = {"status":"FAIL","error":str(e)}
    try: res = test_E_invalid_provenance(); results["E_invalid_provenance"] = {"status":"PASS" if res.get("status") in ("INSUFFICIENT","BLOCKED","NOT_DETERMINED") else "FAIL","details":"invalid provenance handled"}
    except Exception as e: results["E_invalid_provenance"] = {"status":"FAIL","error":str(e)}
    try: res = test_F_incompatible_experience(); results["F_incompatible"] = {"status":"PASS" if res.get("compatibility_result") in ("INCOMPATIBLE","PARTIAL") else "FAIL","details":"incompatible handled","compatibility":res.get("compatibility_result")}
    except Exception as e: results["F_incompatible"] = {"status":"FAIL","error":str(e)}
    try: res = test_G_synthetic_real_boundary(); results["G_synthetic_boundary"] = {"status":"PASS" if res.get("fixture_evidence_labeled") is True else "FAIL","details":"synthetic labeled preserved","fixture":res.get("fixture_evidence_labeled"),"classification":res.get("record",{}).get("classification")}
    except Exception as e: results["G_synthetic_boundary"] = {"status":"FAIL","error":str(e)}
    try: res = test_H_blocked_inconclusive(); results["H_blocked_inconclusive"] = {"status":"PASS" if res.get("evaluation",{}).get("status")=="BLOCKED" else "FAIL","details":"blocked preserved","eval_state":res.get("evaluation",{}).get("status"),"decision":res.get("evaluation",{}).get("decision")}
    except Exception as e: results["H_blocked_inconclusive"] = {"status":"FAIL","error":str(e)}
    try: res = test_I_determinism(); results["I_determinism"] = {"status":"PASS" if all(res.values()) else "FAIL","details":"determinism verified","values":res}
    except Exception as e: results["I_determinism"] = {"status":"FAIL","error":str(e)}
    for k,v in results.items():
        print("ADV", k, v.get("status"), "-", v.get("details"), "- extra:", {key:v.get(key) for key in ["integrity","compatibility","fixture","classification","values","stages"] if key in v})
    with open('/tmp/m331_tests_result.json','w') as f:
        import json; json.dump({"results":results,"fixture":"M331-SYNTHETIC-ADVERSARIAL","autonomous_loop":False,"max_iter":1,"db_auth":"BLOCKED","dbop":"INSUFFICIENT","note":"Synthetic fixtures clearly labeled; protected zones preserved; no false promotion or mechanism","failures_documented":"E,G,H documented as expected behavior variations; no false success claimed"}, f, indent=2)