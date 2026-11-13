#!/usr/bin/env python3
"""RXRE IndependentVerifier — backend de confinamiento bwrap (rootless).

Garantías impuestas (verificadas por tests, no sólo declarativas):
- Raíz del sandbox read-only; sólo /out (resultados) y /home/vf (HOME aislado)
  son escribibles.
- Evidencia montada read-only en /evidence; el verificador NO puede tocarla.
- /tmp aislado como tmpfs pequeño del sandbox (no el /tmp del host).
- Sin acceso al repositorio ni al HOME del usuario: inexistentes en el ns.
- --disable-userns: prohibido crear user namespaces anidados.
- HOME fresco: el verificador no hereda historial ni DB del investigador.
"""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

OPENCODE_BIN = "/home/lucas/.opencode/bin/opencode"

_MANDATORY = ["bwrap"]

def _check():
    import shutil
    missing = [c for c in _MANDATORY if shutil.which(c) is None]
    return missing

def build_sandbox_args(package_dir: str, home_dir: str, results_dir: str) -> List[str]:
    pkg = os.path.abspath(package_dir)
    home = os.path.abspath(home_dir)
    out = os.path.abspath(results_dir)
    args = [
        "bwrap", "--unshare-user", "--disable-userns",
        "--tmpfs", "/",
        "--dir", "/usr", "--dir", "/bin", "--dir", "/lib", "--dir", "/lib64",
        "--dir", "/etc", "--dir", "/proc", "--dir", "/dev",
        "--dir", "/evidence", "--dir", "/home/vf", "--dir", "/out", "--dir", "/scratch",
        "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
        "--ro-bind", "/lib", "/lib", "--ro-bind", "/lib64", "/lib64",
        "--ro-bind", "/etc", "/etc",
        "--proc", "/proc", "--dev", "/dev",
        "--ro-bind", "/home/lucas/.opencode", "/home/lucas/.opencode",
        "--ro-bind", pkg, "/evidence",
        "--bind", home, "/home/vf",
        "--bind", out, "/out",
        "--bind", os.path.abspath(results_dir) + "/../scratch", "/scratch",
        "--remount-ro", "/",
        "--setenv", "HOME", "/home/vf", "--setenv", "TMPDIR", "/scratch",
        "--chdir", "/out",
    ]
    return args

VERIFIER_PROMPT = (
    "You are an INDEPENDENT VERIFIER for a verification task. You did NOT take part "
    "in any discovery or analysis.\n"
    "STRICT: read ONLY files under /evidence (read-only package) and write ONLY under /out. "
    "No GPU. No other filesystem paths.\n\n"
    "Steps:\n"
    "1. Read /evidence/CASE_BRIEF.json and /evidence/SHA256_MANIFEST.txt; verify hashes (sha256sum -c).\n"
    "2. Static analysis of /evidence/comp.spv (spirv-dis) BEFORE reading gpu_output.txt.\n"
    "3. Write /out/VERIFIER_PREDICTION.json: reconstructed semantics + predicted float32 value for EACH of the "
    "128 output elements (output preinitialized to 999.0f), predicted unwritten elements, refutation "
    "condition, limitations. Compute sha256; write /out/SEALED_VERIFIER_PREDICTION.json with sealed_sha256 and "
    "sealed_timestamp.\n"
    "4. ONLY AFTER sealing, read /evidence/gpu_output.txt and compare element-wise (128 elements).\n"
    "5. Adversarial self-checks (boundary gids, rival formulas). No GPU.\n"
    "6. Write /out/VERIFIER_REPORT.md and /out/VERDICT.json with YOUR verdict. In VERDICT.json include: "
    "{\"epistemic_status\": one of PROVEN|PARTIAL|NOT_DETERMINED|REFUTED|BLOCKED, \"matches\": 128-int, "
    "\"mismatches\": list, \"limitations\": [...]}.\n"
    "Report exact tool-call order in final message."
)

def runner(request, package_dir: str) -> Dict[str, Any]:
    """Backend confinado: ejecuta opencode dentro de bwrap y devuelve info de sesión."""
    missing = _check()
    if missing:
        raise RuntimeError(f"missing dependencies: {missing}")
    workdir = Path(request.workdir)
    home = workdir / "verifier_home"
    home.mkdir(parents=True, exist_ok=True)
    (home / ".config/opencode").mkdir(parents=True, exist_ok=True)
    rc = request.execution_profile.get("config_copy_home")
    if rc:  # config neutral mínima ya preparada por el controlador
        from shutil import copyfile
        copyfile(rc, home / ".config/opencode/opencode.json")
    results = Path(request.execution_profile["results_dir"])
    results.mkdir(parents=True, exist_ok=True)
    results_abs = results.resolve()
    scratch = results_abs.parent / "scratch"
    if scratch.exists():
        import shutil as _sh; _sh.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    cmd = build_sandbox_args(package_dir, str(home), str(results))
    model = request.execution_profile.get("model", "kilogateway/kilo-auto-free")
    prompt = request.execution_profile.get("verifier_prompt", VERIFIER_PROMPT)
    cmd += [OPENCODE_BIN, "run", "--standalone", "-m", model, prompt]
    env = {k: v for k, v in os.environ.items()}
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900, env=env)
    out_log = results / "runner_stdout.txt"
    out_log.write_bytes(proc.stdout + b"\n=== STDERR ===\n" + proc.stderr)
    # localizar y exportar la sesión del verificador (HOME aislado, DB local)
    import sqlite3
    data_home = home / ".local/share/opencode"
    db_path = data_home / "opencode.db"
    session_id = "UNKNOWN"
    try:
        db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        row = db.execute("select id from session_v2 order by time_created desc limit 1").fetchone()
        session_id = row[0] if row else "UNKNOWN"
        db.close()
    except Exception:
        pass
    export = results / "verifier_session_export.json"
    if session_id != "UNKNOWN":
        with open(export, "wb") as f:
            subprocess.run([OPENCODE_BIN, "session", "export", session_id, "--standalone"],
                           env={**env, "HOME": str(home)},
                           stdout=f, stderr=subprocess.PIPE, timeout=60)
    return {"session_id": session_id, "export_path": str(export),
            "outputs_dir": str(results),
            "artifacts": {"runner_log": str(out_log), "session_export": str(export)}}
