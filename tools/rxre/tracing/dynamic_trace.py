"""RXRE-MISSION-393 — Trazado dinámico genérico §5-A-compatible.

Usa `strace` (sin privilegios, sin /proc) para capturar syscalls de un
artefacto. NO proporciona trazas de accesos a memoria (alias/access length):
ltrace falla por assertion en este entorno y ASan no registra todos los
accesos. Se documenta como limitación, no se fabrica evidencia.
"""
from __future__ import annotations
import sys, subprocess, os, hashlib, json, tempfile
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

def run_strace(artifact, args=None, timeout=30, sandbox=True):
    """Run strace on artifact. Returns (trace_text, metadata, errors).

    If sandbox=True, wraps in bwrap §5-A profile.
    """
    args = args or []
    errors = []
    cmd = ["strace", "-f", "-e", "trace=openat,read,write,close,mmap,munmap,brk",
           artifact] + list(args)
    if sandbox:
        # §5-A profile
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out"] + ["--bind", "/tmp/m379_out", "/out"] + \
              ["strace", "-f", "-e", "trace=openat,read,write,close,mmap,munmap,brk",
               "/evidence/" + os.path.basename(artifact)] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        trace = proc.stdout + "\n" + proc.stderr
        meta = {
            "returncode": proc.returncode,
            "timeout": False,
            "command": cmd,
            "tool": "strace",
            "version": _version("strace"),
            "sandbox": sandbox,
            "memory_access_tracing": False,
            "note": "strace captures syscalls only; no memory alias/access-length events",
        }
        return trace, meta, errors
    except subprocess.TimeoutExpired:
        return "", {"timeout": True, "command": cmd, "tool": "strace", "sandbox": sandbox}, ["timeout"]
    except Exception as e:
        errors.append(str(e))
        return "", {"error": str(e), "sandbox": sandbox}, errors


def _version(tool):
    try:
        r = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=5)
        return (r.stdout + r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr) else ""
    except Exception:
        return ""


def parse_trace(trace_text):
    """Parse strace output into structured syscall events (generic)."""
    events = []
    for line in trace_text.splitlines():
        line = line.strip()
        if not line or line.startswith("+++ ") or line.startswith("--- "):
            continue
        # format: syscall(args) = ret  or pid syscall(...)
        # extract syscall name
        # find first '('
        if "(" not in line:
            continue
        # strip leading pid
        if line[0].isdigit():
            # pid prefix like "12345 openat(..."
            idx = line.find(" ")
            if idx != -1:
                line = line[idx+1:]
        name = line.split("(")[0].strip()
        # ret
        ret = None
        if "=" in line:
            ret = line.rsplit("=", 1)[-1].strip()
        events.append({"syscall": name, "raw": line, "return": ret})
    return events


def to_observations(events, target_buffer_id, source_artifact, method="dynamic_strace"):
    """Convert syscall events to observations.

    strace does not provide memory alias/access-length, so these properties
    are NOT produced here. Only syscall-level observations (file operations)
    are emitted, marked as dynamic but not memory-access evidence.
    """
    obs = []
    # Emit a single observation noting dynamic tracing attempted but no memory
    # access events available. This keeps honesty.
    obs.append({
        "obs_id": "dyn_trace_syscall_summary",
        "source_artifact": source_artifact,
        "kind": "dynamic_trace",
        "property_hint": "NONE",
        "value": len(events),
        "location": {"function": target_buffer_id},
        "method": method,
        "proven": False,
        "limitations": "strace captures syscalls only; no memory alias/access-length events",
        "dynamic": True,
    })
    return obs


def run(artifact, args=None, target_buffer_id="unknown", sandbox=True, timeout=30):
    trace, meta, errors = run_strace(artifact, args=args, timeout=timeout, sandbox=sandbox)
    events = parse_trace(trace) if trace else []
    obs = to_observations(events, target_buffer_id, artifact)
    result = {
        "status": "PASS_PARTIAL" if trace else "BLOCKED",
        "decision": "PARTIAL" if trace else "NOT_DETERMINED",
        "target": target_buffer_id,
        "artifact": artifact,
        "n_events": len(events),
        "events_sample": events[:10],
        "trace": trace,
        "metadata": meta,
        "errors": errors,
        "memory_access_tracing": False,
        "dynamic_alias_observed": False,
        "access_length_effective_observed": False,
        "provenance": {
            "method": "strace_syscall_tracing",
            "sandbox": sandbox,
            "no_root": True,
            "limitations": "no memory-access tracing available (ltrace broken, ASan insufficient)",
        },
    }
    return result, obs, meta


__all__ = ["run_strace", "parse_trace", "to_observations", "run"]
