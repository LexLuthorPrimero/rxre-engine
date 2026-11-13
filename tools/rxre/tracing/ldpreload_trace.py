"""RXRE-MISSION-394 — Trazado dinámico por interposición LD_PRELOAD.

Interpone símbolos de biblioteca (memcpy, memmove, memset, malloc, free) para
observar operaciones de biblioteca sin privilegios y respetando §5-A. NO es un
tracer universal de memoria: no captura LOAD/STORE directos ni accesos inline.
"""
from __future__ import annotations
import sys, subprocess, os, hashlib, json, re
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

INTERPOSER_DEFAULT = "/tmp/scratchpad/libinterposer.so"


def _parse_log(text):
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # format: func key=val ...
        parts = line.split()
        if not parts:
            continue
        func = parts[0]
        ev = {"function": func, "raw": line}
        # parse key=value
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                ev[k] = v
        events.append(ev)
    return events


def run(artifact, args=None, target_buffer_id="unknown", sandbox=True,
        timeout=30, interposer_path=INTERPOSER_DEFAULT, log_path="/out/interposer.log"):
    args = args or []
    errors = []
    if not os.path.isfile(interposer_path):
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED",
                "errors": ["interposer not found"], "events": [], "metadata": {}}, [], {}

    if sandbox:
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--ro-bind", os.path.dirname(interposer_path), "/interposer",
               "--tmpfs", "/out"] + \
              ["--bind", "/tmp/m379_out", "/out"] + \
              ["/bin/sh", "-c",
               f"INTERPOSER_LOG={log_path} LD_PRELOAD=/interposer/{os.path.basename(interposer_path)} "
               f"/evidence/{os.path.basename(artifact)} " + " ".join(args) +
               f" >/out/stdout.txt 2>/out/stderr.txt; echo RC:$?"]
    else:
        env = dict(os.environ)
        env["INTERPOSER_LOG"] = log_path
        env["LD_PRELOAD"] = interposer_path
        cmd = [artifact] + list(args)
    try:
        if sandbox:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            trace_text = ""
            # read log from host-mapped out dir
            host_log = os.path.join("/tmp/m379_out", os.path.basename(log_path))
            if os.path.isfile(host_log):
                trace_text = open(host_log).read()
            meta = {
                "returncode": proc.returncode,
                "timeout": False,
                "sandbox": True,
                "no_root": True,
                "tool": "ld_preload_interposer",
                "interposer": interposer_path,
                "memory_access_coverage": "library calls only (memcpy/memmove/memset/malloc/free); no direct LOAD/STORE",
            }
            errors_list = []
            if proc.returncode != 0:
                errors_list.append(f"exit {proc.returncode}")
            return None, [], meta  # placeholder, handled below
        else:
            env = dict(os.environ)
            env["INTERPOSER_LOG"] = log_path
            env["LD_PRELOAD"] = interposer_path
            proc = subprocess.run([artifact] + list(args), capture_output=True, text=True,
                                  timeout=timeout, env=env)
            trace_text = open(log_path).read() if os.path.isfile(log_path) else ""
            meta = {"returncode": proc.returncode, "timeout": False, "sandbox": False,
                    "tool": "ld_preload_interposer", "interposer": interposer_path}
            events = _parse_log(trace_text)
            return events, meta, []
    except subprocess.TimeoutExpired:
        return None, [], {"timeout": True}
    except Exception as e:
        return None, [], {"error": str(e)}

    # sandbox path: parse log
    events = _parse_log(trace_text)
    return events, meta, errors_list


def to_observations(events, target_buffer_id, source_artifact, method="ldpreload_interposer"):
    obs = []
    # malloc -> capacity candidate
    for e in events:
        if e["function"] == "malloc":
            n = e.get("n")
            if n is not None:
                try:
                    sz = int(n)
                except ValueError:
                    sz = None
                if sz is not None:
                    obs.append({
                        "obs_id": f"ldp_malloc_{len(obs)}",
                        "source_artifact": source_artifact,
                        "kind": "library_call",
                        "property_hint": "BUFFER_CAPACITY",
                        "value": sz,
                        "value_kind": "DERIVED",
                        "location": {"function": target_buffer_id},
                        "method": method,
                        "proven": False,
                        "limitations": "malloc size is allocation size, not proven buffer capacity; library-level only",
                        "quantity": "library_malloc",
                    })
        elif e["function"] in ("memcpy", "memmove"):
            n = e.get("n")
            try:
                sz = int(n)
            except (ValueError, TypeError):
                sz = None
            if sz is not None:
                obs.append({
                    "obs_id": f"ldp_{e['function']}_{len(obs)}",
                    "source_artifact": source_artifact,
                    "kind": "library_call",
                    "property_hint": "BUFFER_ACCESS_LENGTH",
                    "value": sz,
                    "value_kind": "REQUESTED",
                    "location": {"function": target_buffer_id},
                    "method": method,
                    "proven": False,
                    "limitations": "requested length from library call; completed length not observed; direct LOAD/STORE not captured",
                    "quantity": "library_requested",
                })
            # alias candidate: src/dest pair
            src = e.get("src"); dst = e.get("dest")
            if src and dst:
                obs.append({
                    "obs_id": f"ldp_alias_{len(obs)}",
                    "source_artifact": source_artifact,
                    "kind": "library_call",
                    "property_hint": "BUFFER_ALIAS_SET",
                    "value": "CANDIDATE",
                    "value_kind": "CANDIDATE",
                    "location": {"function": target_buffer_id},
                    "method": method,
                    "proven": False,
                    "limitations": "candidate alias from library call src/dest; not dynamically confirmed as memory alias",
                    "quantity": "library_call",
                })
        elif e["function"] == "memset":
            n = e.get("n")
            try:
                sz = int(n)
            except (ValueError, TypeError):
                sz = None
            if sz is not None:
                obs.append({
                    "obs_id": f"ldp_memset_{len(obs)}",
                    "source_artifact": source_artifact,
                    "kind": "library_call",
                    "property_hint": "BUFFER_ACCESS_LENGTH",
                    "value": sz,
                    "value_kind": "REQUESTED",
                    "location": {"function": target_buffer_id},
                    "method": method,
                    "proven": False,
                    "limitations": "memset length requested; direct stores not captured",
                    "quantity": "library_requested",
                })
    return obs


def run(artifact, args=None, target_buffer_id="unknown", sandbox=True, timeout=30,
        interposer_path=INTERPOSER_DEFAULT, log_path="/out/interposer.log"):
    args = args or []
    events, meta, errors = run_strace if False else (None, None, None)
    # Actually call the internal runner
    # Re-implement cleanly:
    errors = []
    if not os.path.isfile(interposer_path):
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": ["interposer not found"],
                "events": [], "metadata": {}, "memory_access_coverage": "none"}, [], {}
    host_log = os.path.join("/tmp/m379_out", os.path.basename(log_path))
    # remove old log
    try:
        if os.path.isfile(host_log):
            os.remove(host_log)
    except Exception:
        pass
    if sandbox:
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--ro-bind", os.path.dirname(interposer_path), "/interposer",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "/bin/sh", "-c",
               f"INTERPOSER_LOG={log_path} LD_PRELOAD=/interposer/{os.path.basename(interposer_path)} "
               f"/evidence/{os.path.basename(artifact)} " + " ".join(args) +
               f" >/out/stdout.txt 2>/out/stderr.txt; echo RC:$?"]
    else:
        env = dict(os.environ)
        env["INTERPOSER_LOG"] = log_path
        env["LD_PRELOAD"] = interposer_path
        cmd = [artifact] + list(args)
        env_to_use = env
    try:
        if sandbox:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env_to_use)
    except subprocess.TimeoutExpired:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": ["timeout"],
                "events": [], "metadata": {"timeout": True}, "memory_access_coverage": "none"}, [], {}
    except Exception as e:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": [str(e)],
                "events": [], "metadata": {"error": str(e)}, "memory_access_coverage": "none"}, [], {}

    trace_text = ""
    if os.path.isfile(host_log):
        trace_text = open(host_log).read()
    events = _parse_log(trace_text)
    meta = {
        "returncode": proc.returncode,
        "timeout": False,
        "sandbox": sandbox,
        "no_root": True,
        "tool": "ld_preload_interposer",
        "interposer": interposer_path,
        "n_events": len(events),
        "memory_access_coverage": "library calls only (memcpy/memmove/memset/malloc/free); no direct LOAD/STORE",
        "host_log": host_log,
    }
    obs = to_observations(events, target_buffer_id, artifact)
    result = {
        "status": "PASS_PARTIAL" if events else "BLOCKED",
        "decision": "PARTIAL" if events else "NOT_DETERMINED",
        "target": target_buffer_id,
        "artifact": artifact,
        "n_events": len(events),
        "events_sample": events[:10],
        "trace_text": trace_text,
        "metadata": meta,
        "errors": errors,
        "memory_access_coverage": "library calls only; no direct LOAD/STORE",
        "dynamic_alias_observed": False,  # library-level alias not confirmed
        "access_length_effective_observed": False,  # requested, not effective
        "library_access_observed": len(events) > 0,
        "requested_length_observed": any(e["function"] in ("memcpy", "memmove", "memset") for e in events),
        "provenance": {
            "method": "ld_preload_interposition",
            "sandbox": sandbox,
            "no_root": True,
            "limitations": "interposes library symbols only; direct memory accesses not observed",
        },
    }
    return result, obs, meta


__all__ = ["run", "to_observations", "_parse_log"]
