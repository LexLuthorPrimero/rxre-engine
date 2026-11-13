#!/usr/bin/env python3
"""INTEGRIDAD ADVERSARIAL END-TO-END — 8 casos sistemáticos; contrato uniforme + gate."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from pathlib import Path
from rxre.core.evidence_integrity import accept_evidence, validate_evidence_path
from rxre.core.replay import evaluate_contract

def test_1_hash_alterado():
    ev = Path(__file__).resolve().parents[3] / "audit" / "evidence" / "e2e_007.json"
    meta = json.loads(ev.read_text())
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        meta["artefacto_hash_sha256"] = "0" * 64
        tmp.write(json.dumps(meta))
        p = tmp.name
    res = accept_evidence(p, "/bin/ls")
    assert res["status"] == "rejected"
    Path(p).unlink()

def test_2_esquema_invalido():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        meta = {"e2e_id":"bad","artefacto_path":"/nonexistent"}
        tmp.write(json.dumps(meta))
        p = tmp.name
    res = accept_evidence(p, "/bin/ls")
    assert res["status"] == "rejected"
    Path(p).unlink()

def test_3_procedencia_inconsistente():
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        meta = json.loads((repo_root / "audit" / "evidence" / "e2e_007.json").read_text())
        meta["artefacto_path"] = "/no/existe/archivo.ko"
        tmp.write(json.dumps(meta))
        p = tmp.name
    res = accept_evidence(p)
    assert res["status"] == "rejected"
    Path(p).unlink()

def test_4_archivo_vacio():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
        tmp.write(json.dumps({"artefacto_path":"/tmp/fix_rzre/empty","epistemic":"PROVEN"}))
        p = tmp.name
    res = accept_evidence(p, "/tmp/fix_rzre/empty")
    assert res["status"] == "rejected"
    Path(p).unlink()

def test_5_archivo_otro_artefacto():
    repo_root = Path(__file__).resolve().parents[3]
    # Evidencia (/bin/ls) solicitada para OTRO artefacto (/usr/bin/wc): ligadura debe fallar
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared"}]}, str(repo_root / "audit" / "evidence" / "e2e_007.json"), target_artifact_id="/usr/bin/wc")
    assert res["contract_state"] != "COMPLETE", f"evidencia ajena no puede aceptar: {res}"
    assert res["epistemic"] != "VALID"

def test_5b_evidencia_target_coinciden_aceptada():
    repo_root = Path(__file__).resolve().parents[3]
    # Evidencia (/bin/ls) vinculada al artefacto solicitado (/bin/ls == /usr/bin/ls): observación verificable
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},
                             "results":[{"status":"declared",
                                          "observation":{"method":"rizin_cfg_inspection",
                                                         "target": "/bin/ls",
                                                         "findings":[{"function":"main","vaddr":"0x1234"}]}}]},
                            str(repo_root / "audit" / "evidence" / "e2e_007.json"), target_artifact_id="/bin/ls")
    assert res["contract_state"] == "COMPLETE", f"evidencia vinculada e íntegra con observación debe aceptar: {res}"
    assert res["epistemic"] == "VALID"

def test_5c2_observacion_trivial_no_acepta():
    repo_root = Path(__file__).resolve().parents[3]
    # BK_OK + precheck + evidencia í�ntegra, PERO observación auto-reflexiva ('ok')ï
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared","observation":"ok"}]}, str(repo_root / "audit" / "evidence" / "e2e_007.json"), target_artifact_id="/bin/ls")
    assert res["contract_state"] != "COMPLETE"
    assert res["epistemic"] != "VALID"

def test_5d_observacion_solo_flag_no_acepta():
    repo_root = Path(__file__).resolve().parents[3]
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared","observation":{"flag": True}}]}, str(repo_root / "audit" / "evidence" / "e2e_007.json"), target_artifact_id="/bin/ls")
    assert res["contract_state"] != "COMPLETE"
    assert res["epistemic"] != "VALID"

def test_5c_resultado_declarado_sin_observacion_no_acepta():
    repo_root = Path(__file__).resolve().parents[3]
    # BK_OK + precheck ok + sin limitaciones + evidencia íntegra y vinculada,
    # PERO resultado meramente declarado (sin observación semántica verificable)
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared"}]}, str(repo_root / "audit" / "evidence" / "e2e_007.json"), target_artifact_id="/bin/ls")
    assert res["contract_state"] != "COMPLETE", f"declarado sin observación JAMÁS acepta: {res}"
    assert res["epistemic"] != "VALID"

def test_6_evidencia_correcta_aceptada():
    repo_root = Path(__file__).resolve().parents[3]
    res = accept_evidence(str(repo_root / "audit" / "evidence" / "e2e_007.json"), "/bin/ls")
    assert res["status"] == "accepted"

def test_7_dry_run_sin_efecto_lateral():
    repo_root = Path(__file__).resolve().parents[3]
    ev_before = (repo_root / "audit" / "evidence" / "e2e_007.json").read_text()
    from rxre.core.orchestrator import Orchestrator
    orch = Orchestrator("op_2939a40bc715d58f", evidence_path=str(repo_root / "audit" / "evidence" / "e2e_007.json"))
    res = orch.run(dry_run=True)
    ev_after = (repo_root / "audit" / "evidence" / "e2e_007.json").read_text()
    assert ev_before == ev_after
    assert res["dry_run"] is True

def test_8_no_puntero_dict_invalidado():
    """No debe fallar si resultado no tiene 'results' completo."""
    res = evaluate_contract({"status":"invalid_input","precheck":{"ok":False}}, "/nonexistent")
    assert res["epistemic"] == "NOT_DETERMINED"
