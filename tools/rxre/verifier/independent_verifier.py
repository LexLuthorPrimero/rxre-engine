#!/usr/bin/env python3
"""RXRE IndependentVerifier — contrato y lógica de aislamiento/integridad.

Implementa el flujo: prepare clean-room package -> lock -> sesión confinada
(vía backend inyectado) -> sellado -> revelación auditable -> comparación
-> dictamen. Fail-closed: integridad comprometida nunca produce PROVEN.

Clases y funciones no ejecutan GPU ni lógica de física; sólo aislamiento,
integridad y auditoría. El backend de confinamiento vive en sandbox.py.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, stat, subprocess, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

EXECUTION_RUNNING, EXECUTION_OK, EXECUTION_BLOCKED = "RUNNING", "OK", "BLOCKED"
EPISTEMIC_PROVEN, EPISTEMIC_PARTIAL = "PROVEN", "PARTIAL"
EPISTEMIC_NOT_DETERMINED = "NOT_DETERMINED"
EPISTEMIC_BLOCKED, EPISTEMIC_ABSTAINED = "BLOCKED", "ABSTAINED"

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()

@dataclass
class CaseSpec:
    case_id: str
    target: str                 # path relativo dentro del paquete (ej. "comp.spv")
    artifact_sha256: str
    objective: str              # neutral
    dispatch_description: Dict[str, Any]
    readback_name: str = "readback.txt"
    extra_init: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VerificationRequest:
    target: str                          # ruta host del artefacto objetivo
    evidence_package: Optional[str]      # ruta a paquete ya preparado (None = construir desde target)
    case: CaseSpec
    verification_policy: Dict[str, Any] = field(default_factory=lambda: {
        "forbidden_refs": ["SEALED_PREDICTION.json", "oracle_comp", "RXRE_PLAN_MAESTRO",
                           "rxre_discovery_001", "rxre_discovery_002", "rxre_discovery_003"],
        "seal_must_precede_readback": True,
    })
    execution_profile: Dict[str, Any] = field(default_factory=lambda: {
        "backend": "bwrap", "model": "kilogateway/kilo-auto-free", "gpu": False,
    })
    investigation_id: str = ""
    domain: str = ""
    register_dictamen: bool = True
    workdir: str = ""

@dataclass
class VerificationResult:
    execution_status: str
    epistemic_status: str
    verdict: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    integrity: Dict[str, Any] = field(default_factory=dict)
    session_audit: Dict[str, Any] = field(default_factory=dict)

def build_clean_room(target_path, files, case: CaseSpec, package_dir) -> str:
    """Construye paquete mínimo sellado (sin conclusiones). Devuelve ruta."""
    package_dir = Path(package_dir)
    if package_dir.exists():
        def _onerr(func, path, exc):
            import os as _os
            parent = path if _os.path.isdir(path) else _os.path.dirname(path)
            _os.chmod(parent, stat.S_IRWXU)
            if _os.path.isdir(path):
                _os.chmod(path, stat.S_IRWXU)
            try:
                func(path)
            except Exception:
                pass
        shutil.rmtree(package_dir, onerror=_onerr)
    package_dir.mkdir(parents=True)
    manifest = {}
    def put(src, name=None):
        src = Path(src); name = name or src.name
        shutil.copyfile(src, package_dir / name)
        manifest[name] = sha256_file(package_dir / name)
    put(target_path, Path(target_path).name)
    for f in files:
        put(f)
    # neutral case brief — NEVER investigator conclusions
    brief = {"case_id": case.case_id, "artifact": Path(target_path).name,
             "artifact_sha256": case.artifact_sha256,
             "dispatch": case.dispatch_description,
             "verifier_objective": case.objective,
             "output_preinit": case.extra_init.get("output_preinit", 999.0)}
    (package_dir / "CASE_BRIEF.json").write_text(json.dumps(brief, indent=2))
    manifest["CASE_BRIEF.json"] = sha256_file(package_dir / "CASE_BRIEF.json")
    text = "".join(f"{h}  {n}\n" for n, h in sorted(manifest.items()))
    (package_dir / "SHA256_MANIFEST.txt").write_text(text)
    return str(package_dir)

def lock_package(package_dir):
    for root, dirs, files in os.walk(package_dir):
        for f in files:
            os.chmod(os.path.join(root, f), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        for d in dirs:
            os.chmod(os.path.join(root, d), (os.stat(os.path.join(root, d)).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
    os.chmod(package_dir, (os.stat(package_dir).st_mode | stat.S_IXUSR) & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)

def unlock_package(package_dir):
    for root, dirs, files in os.walk(package_dir):
        for f in files: os.chmod(os.path.join(root, f), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)
        for d in dirs: os.chmod(os.path.join(root, d), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
    os.chmod(package_dir, stat.S_IRWXU)

def verify_manifest(package_dir):
    package_dir = Path(package_dir)
    files, hashes, ok = {}, {}, True
    manifest = package_dir / "SHA256_MANIFEST.txt"
    if not manifest.exists():
        return {"files": {}, "hashes": {}, "ok": False, "error": "manifest missing"}
    expected_names = []
    for line in manifest.read_text().splitlines():
        if not line.strip(): continue
        h, name = line.split(None, 1)
        name = name.strip(); expected_names.append(name)
        fp = package_dir / name
        got = sha256_file(fp) if fp.exists() else None
        files[name] = got == h; hashes[name] = got or ""
        ok = ok and got == h
    # fail-closed: no ficheros extra permitidos
    extra = sorted(set(os.listdir(package_dir)) - set(expected_names) - {"SHA256_MANIFEST.txt"})
    if extra:
        return {"files": files, "hashes": hashes, "ok": False, "extra_files": extra}
    return {"files": files, "hashes": hashes, "ok": ok}

def check_seal(prediction_file, sealed_file=None):
    pred = Path(prediction_file)
    sealed = None
    if sealed_file:
        sealed = json.loads(Path(sealed_file).read_text()).get("sealed_sha256")
    else:
        sealed = json.loads(pred.read_text()).get("sealed_sha256")
    actual = sha256_file(pred)
    return {"actual": actual, "expected": sealed, "ok": actual == sealed}

def audit_export(export_path: str, forbidden: List[str], seal_hint: str, readback_hint: str,
                 pre_sealed: bool = False):
    data = json.loads(Path(export_path).read_text())
    calls = []
    for i, m in enumerate(data.get("messages", [])):
        for c in m.get("content", []):
            if c.get("type") == "tool":
                calls.append({"msg": i, "time": (m.get("time") or {}).get("created"),
                              "cmd": str(c.get("state", {}).get("input", {}))})
    joined = "\n".join(c["cmd"] for c in calls)
    hits = {f: (f in joined) for f in forbidden}
    seal_idx = next((k for k, c in enumerate(calls) if re.search(seal_hint, c["cmd"])), None)
    read_idx = next((k for k, c in enumerate(calls)
                     if re.search(readback_hint, c["cmd"]) and
                     re.search(r"(cat|head|tail|less|more|sed|awk|python3?)[^;&|']*" + readback_hint, c["cmd"])), None)
    if pre_sealed:
        _seal_before_reveal = True
    else:
        _seal_before_reveal = (read_idx is None or (seal_idx is not None and seal_idx < read_idx))
    return {"forbidden_hits": hits, "forbidden_clean": not any(hits.values()),
            "seal_index": seal_idx, "readback_index": read_idx,
            "seal_before_reveal": _seal_before_reveal,
            "total_tool_calls": len(calls)}

def verify(request: VerificationRequest, runner: Optional[Callable[[VerificationRequest, str], Dict[str, Any]]] = None) -> VerificationResult:
    """Contrato público verify(). runner inyectado: recibe (request, package_dir) y
    ejecuta el backend; debe devolver dict con keys: session_id, export_path, outputs_dir.
    Si runner es None, sólo valida paquete (modo dry-run, BLOCKED para ejecución)."""
    req, res = request, VerificationResult(EXECUTION_RUNNING, EPISTEMIC_NOT_DETERMINED)
    pkg = req.evidence_package
    if pkg is None:
        if not req.workdir:
            res.execution_status, res.epistemic_status = EXECUTION_BLOCKED, EPISTEMIC_BLOCKED
            res.limitations.append("workdir required to build clean-room package")
            return res
        artifacts_dir = Path(req.workdir)
        pkg = build_clean_room(req.target, [], req.case, artifacts_dir / "package")
        res.artifacts["package"] = pkg
    lock_package(pkg)
    pre = verify_manifest(pkg)
    res.integrity["pre_run"] = pre
    if not pre["ok"]:
        unlock_package(pkg)
        res.execution_status, res.epistemic_status = EXECUTION_BLOCKED, EPISTEMIC_BLOCKED
        res.limitations.append(f"package integrity compromised BEFORE run: {pre}")
        return res
    if runner is None:
        unlock_package(pkg)
        res.execution_status = EXECUTION_BLOCKED
        res.epistemic_status = EPISTEMIC_NOT_DETERMINED
        res.limitations.append("no runner injected (dry-run): execution not performed")
        return res
    run_info = runner(req, pkg)
    post = verify_manifest(pkg)
    res.integrity["post_run"] = post
    unlock_package(pkg)   # restaurar permisos (reversible)
    res.artifacts.update(run_info.get("artifacts", {}))
    res.session_audit = audit_export(
        run_info["export_path"], req.verification_policy.get("forbidden_refs", []),
        r"SEALED_VERIFIER_PREDICTION\.json", r"(Read|read|cat|open|with open|read_text|less|sed|head|tail|grep|python3? )[^\n]*gpu_output\.txt|gpu_output\.txt")
    integrity_ok = post.get("ok") and res.session_audit.get("seal_before_reveal") and res.session_audit.get("forbidden_clean")
    verdict_path = Path(run_info.get("outputs_dir", "")) / "VERDICT.json"
    verdict = json.loads(verdict_path.read_text()) if verdict_path.exists() else {}
    res.verdict = verdict
    if not post.get("ok"):
        res.execution_status, res.epistemic_status = EXECUTION_BLOCKED, EPISTEMIC_BLOCKED
        res.limitations.append("package integrity compromised AFTER run")
    elif integrity_ok:
        res.execution_status = EXECUTION_OK
        res.epistemic_status = verdict.get("epistemic_status", EPISTEMIC_NOT_DETERMINED)
        if res.epistemic_status not in (EPISTEMIC_PROVEN, EPISTEMIC_PARTIAL):
            res.limitations.append("verifier did not produce PROVEN/PARTIAL; see verdict")
    else:
        res.execution_status = EXECUTION_BLOCKED
        res.epistemic_status = EPISTEMIC_BLOCKED
        res.limitations.append("temporal sealing or forbidden-reference audit failed")
    res.metrics = {"package_files_ok": post.get("files"),
                   "seal_before_reveal": res.session_audit.get("seal_before_reveal"),
                   "forbidden_clean": res.session_audit.get("forbidden_clean"),
                   "total_tool_calls": res.session_audit.get("total_tool_calls")}
    if req.register_dictamen:
        try:
            from dataclasses import asdict as _asdict
            from . import promotion as _P
            _rec = _P.register_dictamen(
                _asdict(res),
                investigation_id=req.investigation_id or req.case.case_id or "inv-unknown",
                artifact_sha256=req.case.artifact_sha256,
                target_file=Path(req.target).name,
                domain=req.domain or "unspecified")
            _P.attach_verification_result(_rec, _asdict(res))
            res.artifacts["dictamen_id"] = _rec["dictamen_id"]
            res.artifacts["dictamen_decision"] = _rec["decision"]
            res.artifacts["dictamen_accepted"] = str(_rec.get("accepted"))
        except Exception as _e:
            res.limitations.append(f"dictamen no registrado: {_e}")
    return res
