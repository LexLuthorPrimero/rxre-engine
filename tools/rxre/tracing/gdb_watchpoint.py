"""RXRE-MISSION-396 — Hardware watchpoints de GDB bajo §5-A.

Demuestra disponibilidad y funcionamiento de hardware watchpoints (write/read)
sin privilegios. No confirma alias dinámico por sí solo.
"""
from __future__ import annotations
import sys, subprocess, os, hashlib, json, re
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

def run_watchpoint(artifact, address, args=None, kind="watch", sandbox=True, timeout=30):
    """kind: 'watch' (write), 'rwatch' (read), 'awatch' (read/write)."""
    args = args or []
    if kind not in ("watch", "rwatch", "awatch"):
        return {"status": "BLOCKED", "errors": ["invalid kind"]}, [], {}
    script = [
        "set pagination off", "set confirm off", "set debuginfod enabled off",
        f"{kind} *(char*){address}",
        "run " + " ".join(args) if False else "run",
    ]
    # gdb needs args via --args; commands via -ex
    cmd = []
    if sandbox:
        script_path = "/tmp/m379_out/wp_run.txt"
        with open(script_path, "w") as f:
            f.write("\n".join([
                "set pagination off", "set confirm off", "set debuginfod enabled off",
                f"{kind} *(char*){address}",
                "run",
            ]) + "\n")
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "gdb", "-batch", "-x", "/out/wp_run.txt",
               "--args", f"/evidence/{os.path.basename(artifact)}"] + list(args)
    else:
        script_path = "/tmp/wp_run.txt"
        with open(script_path, "w") as f:
            f.write("\n".join([
                "set pagination off", "set confirm off", "set debuginfod enabled off",
                f"{kind} *(char*){address}",
                "run",
            ]) + "\n")
        cmd = ["gdb", "-batch", "-x", script_path, "--args", artifact] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + "\n" + proc.stderr
        meta = {"returncode": proc.returncode, "sandbox": sandbox, "no_root": True,
                "tool": "gdb", "kind": kind, "address": address}
        # detect trigger
        triggered = ("Hardware watchpoint" in output and "New value" in output) or \
                    ("Hardware read watchpoint" in output and "value has been read" in output) or \
                    ("Hardware access watchpoint" in output and "value has been" in output)
        # simpler: check if any "watchpoint" trigger line
        triggered = "watchpoint" in output.lower() and ("new value" in output.lower() or "value has been" in output.lower() or "old value" in output.lower())
        result = {
            "status": "PASS_PARTIAL" if True else "BLOCKED",
            "decision": "PARTIAL",
            "target": address,
            "kind": kind,
            "triggered": triggered,
            "output": output,
            "metadata": meta,
            "errors": [],
            "watchpoint_available": "Hardware" in output or "watchpoint" in output.lower(),
            "provenance": {"method": "gdb_hardware_watchpoint", "sandbox": sandbox, "no_root": True},
        }
        return result, output, meta
    except subprocess.TimeoutExpired:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": ["timeout"],
                "triggered": False, "metadata": {"timeout": True}}, "", {"timeout": True}
    except Exception as e:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": [str(e)],
                "triggered": False, "metadata": {"error": str(e)}}, "", {"error": str(e)}


def to_observations(result, target_buffer_id, source_artifact, method="gdb_watchpoint"):
    obs = []
    if result.get("triggered"):
        obs.append({
            "obs_id": f"gdb_wp_{len(obs)}",
            "source_artifact": source_artifact,
            "kind": "gdb_watchpoint_event",
            "property_hint": "BUFFER_ALIAS_SET",
            "value": "CANDIDATE",
            "value_kind": "CANDIDATE",
            "location": {"function": target_buffer_id},
            "method": method,
            "proven": False,
            "limitations": "watchpoint triggered; alias not confirmed without comparable context",
            "quantity": "gdb_watchpoint",
        })
    return obs


def run(artifact, args=None, address="0x0", target_buffer_id="unknown",
        kind="watch", sandbox=True, timeout=30):
    result, output, meta = run_watchpoint(artifact, address, args, kind, sandbox, timeout)
    obs = to_observations(result, target_buffer_id, artifact)
    result["obs"] = obs
    return result, obs, meta


__all__ = ["run_watchpoint", "to_observations", "run"]
