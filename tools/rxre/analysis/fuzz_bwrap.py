"""M592 FUZZER BWRAP: mutador M584 + bwrap sandboxed (binario inocuo sintético)."""
import subprocess
from tools.rxre.analysis.fuzz import mutate, classify

BWRAP_BASE = ["bwrap","--unshare-user","--unshare-pid","--unshare-net",
    "--ro-bind","/bin","/bin","--ro-bind","/lib64","/lib64","--ro-bind","/usr","/usr"]

def run_sandboxed(bin_path: str, timeout=5) -> str:
    cmd = BWRAP_BASE + ["--ro-bind","/tmp","/tmp", bin_path]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc = p.returncode
        if rc == 0: return "OK:exit0"
        if rc == 139 or rc == 134: return f"CRASH:rc{rc}"
        if rc < 0: return f"CRASH:signal{-rc}"
        return f"OK:rc{rc}" if rc==0 else f"CRASH:rc{rc}"
    except subprocess.TimeoutExpired:
        return "HANG:timeout"

def classify_sandbox(bin_path, timeout=5) -> str:
    return classify(run_sandboxed(bin_path, timeout=timeout))
