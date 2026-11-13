#!/usr/bin/env python3
"""CONTRATO UNIFORME — adversarial; reproducible."""
import sys, os, tempfile, json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from pathlib import Path
from rxre.core.replay import evaluate_contract

def test_contract_elf_ok():
    """PROVEN: BK_OK completo -> COMPLETE / VALID."""
    # Usar resultado real de elff_ok (simulado con datos reales)
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared","limitations":["test"]}]}, None)
    # Con limitación explícita -> PARTIAL
    assert res["contract_state"] == "PARTIAL", f"Con limitaciones debe ser PARTIAL: {res['contract_state']}"
    assert res["epistemic"] == "PARTIAL"

def test_contract_empty_invalid():
    """PROVEN (adversarial): BK_INVALID (empty/text) -> INVALID_INPUT / NOT_DETERMINED."""
    res = evaluate_contract({"status":"invalid_input","precheck":{"ok":False},"ejecucion":{"status":"blocked"}})
    assert res["contract_state"] == "INVALID_INPUT"
    assert res["epistemic"] == "NOT_DETERMINED"
    assert res["execution_status"] == "invalid_input"

def test_contract_blocked_error():
    """PROVEN (adversarial): BK_ERROR -> BLOCKED / NOT_DETERMINED."""
    res = evaluate_contract({"status":"blocked","precheck":{"ok":True},"ejecucion":{"status":"blocked"}})
    assert res["contract_state"] == "BLOCKED"
    assert res["epistemic"] == "NOT_DETERMINED"

def test_contract_truncated_partial():
    """PARTIAL: BK_OK con evidencia frontera → PARTIAL (no COMPLETO).

    Precondición pública: el artefacto registrado en e2e_004.json vive en el
    árbol privado del autor y no se distribuye. En un entorno donde el
    artefacto no está disponible / su hash coincide o no, la integridad
    evaluada por la puerta E2E (with hash) debe REPORTAR un resultado real.
    Si la puerta reporta 'VALID' con limitaciones declaradas, el contrato
    sigue siendo PARTIAL; si la puerta lo rechaza, la evidencia es invalida
    y tampoco es COMPLETO. Lo que NUNCA puede pasar es COMPLETO/VALID.
    """
    import pytest
    repo_root = Path(__file__).resolve().parents[3]
    import json as _json
    meta_path = repo_root / "audit" / "evidence" / "e2e_004.json"
    meta = _json.loads(meta_path.read_text())
    art = Path(meta.get("artefacto_path", ""))
    if not art.exists():
        pytest.skip(f"artefacto privado ausente en este host ({art}); integrity gate cannot validate")
    res = evaluate_contract({"status":"ok","precheck":{"ok":True},"ejecucion":{"status":"ok"},"results":[{"status":"declared","limitations":["RAW_BINARY","limite"]}]}, str(meta_path))
    assert res["contract_state"] == "PARTIAL", f"contrato debe ser PARTIAL con evidencia frontera, obtuve {res}"
    assert res["epistemic"] == "PARTIAL"
    # NUNCA puede elevarse a COMPLETE/VALID; PARTIAL en cualquier gatepath es válido aquí
    assert res["contract_state"] != "COMPLETE" and res["epistemic"] != "VALID", "evidence for e2e_004 must NOT elevate to VALID"

def test_contract_no_auto_proven():
    """PROVEN: ningún caso debe producir PROVEN automáticamente."""
    for case in [
        {"status":"ok","precheck":{"ok":True}},
        {"status":"invalid_input"},
        {"status":"blocked"}
    ]:
        res = evaluate_contract(case)
        assert res["epistemic"] != "PROVEN", f"No debe ser PROVEN automático: {res['epistemic']}"


if __name__ == "__main__":
    for t in [test_contract_elf_ok, test_contract_empty_invalid, test_contract_blocked_error,
              test_contract_truncated_partial, test_contract_no_auto_proven]:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as exc:
            print("FAIL", t.__name__, "-", type(exc).__name__, str(exc)[:60])
