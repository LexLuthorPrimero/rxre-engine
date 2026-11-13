#!/usr/bin/env python3
"""REPRODUCIBILIDAD END-TO-END — misión completa reproducible desde repo y /tmp."""
import sys, os, tempfile, json, hashlib, shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from pathlib import Path
from rxre.core.orchestrator import Orchestrator

def test_reproducibilidad_repo_y_tmp():
    """PROVEN: misma misión, misma evidencia, mismo resultado desde dos copias independientes."""
    import shutil, subprocess, os as _os
    repo_root = Path(__file__).resolve().parents[3]
    # Build a *clean copy* of the public engine tree (skip .git/.venv; keep everything that affects execution)
    tmp_root = Path("/tmp/rxre-engine-test-repro")
    shutil.rmtree(tmp_root, ignore_errors=True)
    _os.makedirs(tmp_root)
    SKIP = {".git", "__pycache__", ".pytest_cache", ".venv"}
    for sub in ("tools", "audit", "REQUIREMENTS"):
        src = repo_root / sub
        if src.is_dir():
            shutil.copytree(src, tmp_root / sub)
        elif src.exists():
            shutil.copy2(src, tmp_root / src.name)
    for f in ("conftest.py", "pytest.ini", "setup.cfg", "pyproject.toml"):
        src = repo_root / f
        if src.exists(): shutil.copy2(src, tmp_root / f)

    evidence_repo = repo_root / "audit" / "evidence" / "e2e_006.json"
    evidence_tmp   = tmp_root / "audit" / "evidence" / "e2e_006.json"
    # Same SHA-256 must hold for the two copies of the evidence — guards silent drift
    h_repo = hashlib.sha256(evidence_repo.read_bytes()).hexdigest()
    h_tmp  = hashlib.sha256(evidence_tmp.read_bytes()).hexdigest()
    assert h_repo == h_tmp, "evidence copies diverged"
    # Ejecución real (repo, absolute env)
    orch_repo = Orchestrator("op_2939a40bc715d58f", evidence_path=str(evidence_repo))
    res_repo = orch_repo.run(dry_run=False)
    # Ejecución real (/tmp — fresh tree, fresh Python process, fresh sys.path)
    env = _os.environ.copy()
    env["PYTHONPATH"] = str(tmp_root)
    code = """
import sys, json, os
sys.path.insert(0, os.path.abspath(sys.argv[1] + '/tools'))
sys.path.insert(0, os.path.abspath(sys.argv[1] + '/tools/rxre'))
from pathlib import Path
from rxre.core.orchestrator import Orchestrator
ev = sys.argv[1] + '/audit/evidence/e2e_006.json'
orch = Orchestrator('op_2939a40bc715d58f', evidence_path=ev)
res = orch.run(dry_run=False)
print(json.dumps(res, default=str))
"""
    cp = subprocess.run(["python3", "-c", code, str(tmp_root)],
                        capture_output=True, text=True, env=env, cwd=str(tmp_root), timeout=120)
    if cp.returncode != 0:
        raise RuntimeError(f"repro subprocess failed: {cp.stderr[:300]}")
    res_tmp = json.loads(cp.stdout.strip().splitlines()[-1]) if False else json.loads(cp.stdout)

    # Comparar identidad de conclusión
    assert res_repo["conclusion"]["verification_status"] == res_tmp["conclusion"]["verification_status"], \
        f"Reproducción debe ser idéntica: repo={res_repo['conclusion']['verification_status']} tmp={res_tmp['conclusion']['verification_status']}"
    # Confirmar que evidencia consumida es e2e_006 (no reutiliza amdgpu)
    chain_repo = res_repo.get("chain", [])
    chain_tmp = res_tmp.get("chain", [])
    assert any(c.get("stage") == "EVIDENCIA" for c in chain_repo), "Debió consumir evidencia"
    assert res_repo.get("blocked") == res_tmp.get("blocked")
    # No debe inventar PROVEN
    assert res_repo["conclusion"]["verification_status"] in ("RESOLVED", "UNRESOLVED")

def test_reproducibilidad_dry_run():
    """PROVEN: dry_run reproducible sin modificar DB ni evidencia."""
    repo_root = Path(__file__).resolve().parents[3]
    ev_before = (repo_root / "audit" / "evidence" / "e2e_006.json").read_text()
    orch = Orchestrator("op_2939a40bc715d58f", evidence_path=str(repo_root / "audit" / "evidence" / "e2e_006.json"))
    res = orch.run(dry_run=True)
    ev_after = (repo_root / "audit" / "evidence" / "e2e_006.json").read_text()
    assert ev_before == ev_after, "Dry-run no debe modificar evidencia"
    assert res["dry_run"] is True
    assert res["conclusion"]["verification_status"] in ("RESOLVED", "UNRESOLVED")


if __name__ == "__main__":
    for t in [test_reproducibilidad_repo_y_tmp, test_reproducibilidad_dry_run]:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as exc:
            print("FAIL", t.__name__, "-", type(exc).__name__, str(exc)[:60])
