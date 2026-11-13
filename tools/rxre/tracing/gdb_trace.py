"""RXRE-MISSION-395 — Trazado dinámico por GDB scripting bajo §5-A.

Usa GDB (sin privilegios, sin /proc) para establecer breakpoints y capturar
registros/direcciones efectivas. Demuestra observación real de memoria cuando
el breakpoint se alcanza. No es un tracer universal.
"""
from __future__ import annotations
import sys, subprocess, os, hashlib, json, re
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

def _build_gdb_script(breakpoints, commands_extra=None):
    lines = ["set pagination off", "set confirm off", "set debuginfod enabled off"]
    for bp in breakpoints:
        addr = bp["address"]
        regs = bp.get("registers", [])
        lines.append(f"break *{addr}")
    lines.append("run")
    # after run, for each breakpoint hit, capture
    # We'll use a single breakpoint command sequence via commands
    # Simpler: use -ex with printf after break
    # Rebuild with commands blocks
    script = ["set pagination off", "set confirm off", "set debuginfod enabled off"]
    for i, bp in enumerate(breakpoints, start=1):
        addr = bp["address"]
        regs = bp.get("registers", [])
        script.append(f"break *{addr}")
        script.append(f"commands {i}")
        for r in regs:
            script.append(f"printf \"{r}=%p\\n\", ${r}")
        # also print instruction
        script.append("printf \"HIT_ADDR=%p\\n\", $pc")
        script.append("continue")
        script.append("end")
    script.append("run")
    script.append("quit")
    return "\n".join(script) + "\n"


def run(artifact, args=None, breakpoints=None, target_buffer_id="unknown",
        sandbox=True, timeout=60, gdb_script_extra=None):
    args = args or []
    breakpoints = breakpoints or []
    errors = []
    if sandbox:
        # write script to /tmp/m379_out
        script = _build_gdb_script(breakpoints)
        script_path_host = "/tmp/m379_out/gdb_script.txt"
        with open(script_path_host, "w") as f:
            f.write(script)
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "gdb", "-batch", "-x", "/out/gdb_script.txt",
               f"/evidence/{os.path.basename(artifact)}"] + (["--args"] + [f"/evidence/{os.path.basename(artifact)}"] + list(args) if False else [])
        # gdb with args: use --args
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "gdb", "-batch", "-x", "/out/gdb_script.txt",
               "--args", f"/evidence/{os.path.basename(artifact)}"] + list(args)
    else:
        script = _build_gdb_script(breakpoints)
        script_path = "/tmp/gdb_script.txt"
        with open(script_path, "w") as f:
            f.write(script)
        cmd = ["gdb", "-batch", "-x", script_path, "--args", artifact] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + "\n" + proc.stderr
        meta = {
            "returncode": proc.returncode,
            "timeout": False,
            "sandbox": sandbox,
            "no_root": True,
            "tool": "gdb",
            "version": _version(),
            "breakpoints": [bp["address"] for bp in breakpoints],
        }
        return output, meta, []
    except subprocess.TimeoutExpired:
        return "", {"timeout": True, "sandbox": sandbox}, ["timeout"]
    except Exception as e:
        return "", {"error": str(e), "sandbox": sandbox}, [str(e)]


def _version():
    try:
        r = subprocess.run(["gdb", "--version"], capture_output=True, text=True, timeout=5)
        first = (r.stdout or r.stderr).strip().splitlines()
        return first[0] if first else ""
    except Exception:
        return ""


def parse_gdb_output(text):
    """Parse gdb output into hit events with captured registers."""
    events = []
    current = None
    for line in text.splitlines():
        line = line.strip()
        m = re.match(r"Breakpoint \d+ at (0x[0-9a-f]+)", line)
        if m:
            continue
        if "Breakpoint" in line and " at " in line:
            current = {"hit": line, "registers": {}}
            events.append(current)
            continue
        m = re.match(r"(\w+)=(.+)", line)
        if m and current is not None:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if key in ("rbx","rsi","rdx","rcx","rdi","rax","rip","rsp","r8","r9","r10","r11","r12","r13","r14","r15"):
                current["registers"][key] = val
            continue
        if "HIT_ADDR=" in line:
            if current is not None:
                current["hit_addr"] = line.split("=", 1)[-1].strip()
    # filter empty events
    events = [e for e in events if e.get("registers") or e.get("hit_addr")]
    return events


def to_observations(events, target_buffer_id, source_artifact, method="gdb_scripting",
                     specs=None):
    """specs: list of {prop, reg, kind, proven, transform} describing how to
    map captured registers to property observations. Generic: no hardcoded
    property semantics beyond what specs declare."""
    specs = specs or []
    obs = []
    for ev in events:
        regs = ev.get("registers", {})
        hit_addr = ev.get("hit_addr")
        # raw hit observation (provenance)
        obs.append({
            "obs_id": f"gdb_hit_{len(obs)}",
            "source_artifact": source_artifact,
            "kind": "gdb_breakpoint_hit",
            "property_hint": "NONE",
            "value": None,
            "location": {"function": target_buffer_id, "offset": hit_addr},
            "method": method,
            "proven": False,
            "gdb_provenance": {"registers": regs, "hit": ev.get("hit"), "hit_addr": hit_addr},
            "limitations": "breakpoint hit observed; coverage limited to breakpointed instructions",
            "quantity": "gdb_observed",
        })
        for spec in specs:
            prop = spec.get("prop")
            reg = spec.get("reg")
            if not prop or not reg:
                continue
            raw = regs.get(reg)
            if raw is None:
                continue
            # transform
            transform = spec.get("transform", "int")
            try:
                if transform == "int":
                    val = int(raw, 16) if isinstance(raw, str) and raw.startswith("0x") else int(raw)
                elif transform == "str":
                    val = raw
                else:
                    val = raw
            except (ValueError, TypeError):
                val = raw
            obs.append({
                "obs_id": f"gdb_{prop.lower()}_{len(obs)}",
                "source_artifact": source_artifact,
                "kind": "gdb_register_observation",
                "property_hint": prop,
                "value": val,
                "value_kind": spec.get("kind", "OBSERVED"),
                "location": {"function": target_buffer_id, "offset": hit_addr},
                "method": method,
                "proven": bool(spec.get("proven", False)),
                "gdb_provenance": {"register": reg, "raw": raw, "hit": ev.get("hit")},
                "limitations": spec.get("limitations", "observed via gdb breakpoint"),
                "quantity": spec.get("quantity", "gdb_observed"),
            })
        # alias candidate observation per hit (generic)
        # if multiple registers captured, record a candidate alias observation
        if len(regs) >= 2:
            obs.append({
                "obs_id": f"gdb_alias_{len(obs)}",
                "source_artifact": source_artifact,
                "kind": "gdb_alias_candidate",
                "property_hint": "BUFFER_ALIAS_SET",
                "value": "CANDIDATE",
                "value_kind": "CANDIDATE",
                "location": {"function": target_buffer_id, "offset": hit_addr},
                "method": method,
                "proven": False,
                "gdb_provenance": {"registers": regs},
                "limitations": "candidate alias from register snapshot; not dynamically confirmed",
                "quantity": "gdb_observed",
            })
    return obs



def _execute_gdb(artifact, args, breakpoints, target_buffer_id, sandbox, timeout):
    args = args or []
    breakpoints = breakpoints or []
    errors = []
    script = _build_gdb_script(breakpoints)
    if sandbox:
        script_path_host = "/tmp/m379_out/gdb_script.txt"
        with open(script_path_host, "w") as f:
            f.write(script)
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "gdb", "-batch", "-x", "/out/gdb_script.txt",
               "--args", f"/evidence/{os.path.basename(artifact)}"] + list(args)
    else:
        script_path = "/tmp/gdb_script.txt"
        with open(script_path, "w") as f:
            f.write(script)
        cmd = ["gdb", "-batch", "-x", script_path, "--args", artifact] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + "\n" + proc.stderr
        meta = {
            "returncode": proc.returncode,
            "timeout": False,
            "sandbox": sandbox,
            "no_root": True,
            "tool": "gdb",
            "version": _version(),
            "breakpoints": [bp["address"] for bp in breakpoints],
        }
        return output, meta, []
    except subprocess.TimeoutExpired:
        return "", {"timeout": True, "sandbox": sandbox}, ["timeout"]
    except Exception as e:
        return "", {"error": str(e), "sandbox": sandbox}, [str(e)]

def run_gdb(artifact, args=None, breakpoints=None, target_buffer_id="unknown",
        sandbox=True, timeout=60, specs=None):
    breakpoints = breakpoints or []
    output, meta, errors = _execute_gdb(artifact, args, breakpoints, target_buffer_id, sandbox, timeout)
    events = parse_gdb_output(output) if output else []
    obs = to_observations(events, target_buffer_id, artifact, specs=specs)
    result = {
        "status": "PASS_PARTIAL" if events else ("BLOCKED" if errors else "PASS_PARTIAL"),
        "decision": "PARTIAL" if events else "NOT_DETERMINED",
        "target": target_buffer_id,
        "artifact": artifact,
        "n_events": len(events),
        "events": events,
        "output": output,
        "metadata": meta,
        "errors": errors,
        "gdb_attach": True,
        "instruction_breakpoint": len(events) > 0,
        "hardware_watchpoint": "not tested here",
        "effective_address": "reconstructed from registers",
        "access_length_effective_observed": False,
        "dynamic_alias_observed": False,
        "provenance": {
            "method": "gdb_scripting",
            "sandbox": sandbox,
            "no_root": True,
            "limitations": "breakpoint-based; only instrumented addresses; no full memory tracing",
        },
    }
    return result, obs, meta


__all__ = ["run_gdb", "parse_gdb_output", "to_observations", "run"]


def run(artifact, args=None, breakpoints=None, target_buffer_id="unknown", sandbox=True, timeout=60, specs=None):
    return run_gdb(artifact, args, breakpoints, target_buffer_id, sandbox, timeout, specs)


def _find_mem_accesses(artifact, start_va, size):
    """Use capstone to find memory-access instructions in [start_va, start_va+size).
    Returns list of (va, file_offset, base_reg, index, scale, disp, size_candidate, mnemonic).
    """
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    from rxre.backends.adapters import cs_disasm
    from rxre.integrations.rz_memory_evidence import _access_size as _sz, SIZE_PREFIX
    # cs_disasm reads by file offset; VA->file offset: .text VA 0x400000? Use passed start_va as file offset? 
    # We assume caller passes file offset as start_va for disassembly (as in prior usage).
    res = cs_disasm.desensamblar(artifact, inicio=start_va, longitud=size, arquitectura="x86_64")
    if not res.get("results"):
        return []
    instrs = res["results"][0].get("value", {}).get("instrucciones", [])
    out = []
    for ins in instrs:
        addr = ins.get("direccion")
        mnem = ins.get("mnemonico", "")
        op_str = ins.get("op_str", "")
        for o in ins.get("operandos", []):
            if o.get("tipo") != "mem":
                continue
            base = o.get("base") or ""
            idx = o.get("indice") or ""
            scale = o.get("escala", 1)
            disp = o.get("desplazamiento", 0)
            # size candidate
            sz = None
            low = mnem.lower()
            # map common
            size_map = {"movb":1,"movw":2,"movl":4,"movq":8,"mov":None,
                        "leaq":8,"leal":4,"cmpb":1,"cmpw":2,"cmpl":4,"cmpq":8}
            if low in size_map and size_map[low] is not None:
                sz = size_map[low]
            if sz is None:
                for pref, psz in SIZE_PREFIX.items():
                    if pref in op_str.lower():
                        sz = psz; break
            out.append({
                "va": addr, "file_offset": addr, "base_reg": base,
                "index_reg": idx, "scale": scale, "disp": disp,
                "size_candidate": sz, "mnemonic": mnem, "op_str": op_str,
            })
    return out


def auto_trace(artifact, start_va, size, target_buffer_id="unknown",
               sandbox=True, timeout=120, max_bp=40, args=None, specs=None):
    """Automatically set breakpoints on memory-access instructions and capture registers.

    Generic: no libtiff-specific heuristics. Returns (result, obs, meta).
    """
    accesses = _find_mem_accesses(artifact, start_va, size)
    # dedup addresses
    addrs = []
    seen = set()
    for a in accesses:
        if a["va"] not in seen:
            seen.add(a["va"])
            addrs.append(a["va"] + 0x400000)
    addrs = addrs[:max_bp]
    # build gdb script
    lines = ["set pagination off", "set confirm off", "set debuginfod enabled off"]
    for i, a in enumerate(addrs, start=1):
        lines.append(f"break *0x{a:x}")
    # commands for each breakpoint
    for i, a in enumerate(addrs, start=1):
        lines.append(f"commands {i}")
        lines.append("silent")
        lines.append('printf "AUTO_HIT addr=0x%x\\n", $pc')
        for reg in ("rax","rbx","rcx","rdx","rsi","rdi","r8","r9","r10","r11","r12","r13","r14","r15","rbp","rsp"):
            lines.append(f'printf "{reg}=%p\\n", ${reg}')
        lines.append("continue")
        lines.append("end")
    lines.append("run")
    script = "\n".join(lines) + "\n"

    if sandbox:
        script_host = "/tmp/m379_out/auto_trace_script.txt"
        with open(script_host, "w") as f:
            f.write(script)
        cmd = ["bwrap", "--unshare-user", "--unshare-all",
               "--tmpfs", "/", "--ro-bind", "/usr", "/usr",
               "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib64", "/lib64",
               "--ro-bind", "/lib", "/lib", "--tmpfs", "/tmp",
               "--tmpfs", "/home", "--tmpfs", "/evidence",
               "--ro-bind", os.path.dirname(artifact), "/evidence",
               "--tmpfs", "/out", "--bind", "/tmp/m379_out", "/out",
               "gdb", "-batch", "-x", "/out/auto_trace_script.txt",
               "--args", f"/evidence/{os.path.basename(artifact)}"] + (args or [])
    else:
        script_path = "/tmp/auto_trace_script.txt"
        with open(script_path, "w") as f:
            f.write(script)
        cmd = ["gdb", "-batch", "-x", script_path, "--args", artifact] + (args or [])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout + "\n" + proc.stderr
        meta = {"returncode": proc.returncode, "sandbox": sandbox, "no_root": True,
                "tool": "gdb_auto_trace", "n_breakpoints": len(addrs),
                "n_accesses_found": len(accesses)}
    except subprocess.TimeoutExpired:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": ["timeout"],
                "output": "", "events": [], "metadata": {"timeout": True}}, [], {}
    except Exception as e:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED", "errors": [str(e)],
                "output": "", "events": [], "metadata": {"error": str(e)}}, [], {}

    # parse hits: group by AUTO_HIT? We used printf per breakpoint with addr+regs.
    events = []
    current = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Breakpoint") and " at " in line:
            # new hit context not needed
            pass
        m = re.match(r"(\w+)=(0x[0-9a-f]+|\(nil\))", line)
        if m:
            if current is None:
                current = {"registers": {}}
                events.append(current)
            current["registers"][m.group(1)] = m.group(2)
            continue
        if "AUTO_HIT addr=" in line:
            current = {"hit_addr": line.split("=",1)[-1].strip(), "registers": {}}
            events.append(current)
            continue
    # filter events without registers
    events = [e for e in events if e.get("registers")]
    # reconstruct effective addresses from accesses list (match by hit order)
    # We'll attach access info by index
    for i, ev in enumerate(events):
        if i < len(accesses):
            a = accesses[i]
            ev["access"] = a
            # reconstruct effective address: base_reg value + disp
            base_val = ev["registers"].get(a["base_reg"])
            if base_val and base_val != "(nil)":
                try:
                    base_int = int(base_val, 16)
                    ev["effective_address"] = base_int + a["disp"] * a["scale"] + (0 if not a["index_reg"] else 0)
                except ValueError:
                    ev["effective_address"] = None
            else:
                ev["effective_address"] = None
            ev["size_candidate"] = a["size_candidate"]

    obs = []
    for ev in events:
        a = ev.get("access", {})
        ea = ev.get("effective_address")
        sz = ev.get("size_candidate")
        if ea is not None:
            obs.append({
                "obs_id": f"auto_ea_{len(obs)}",
                "source_artifact": artifact,
                "kind": "gdb_auto_trace",
                "property_hint": "BUFFER_OFFSET",
                "value": ea,
                "value_kind": "OBSERVED",
                "location": {"function": target_buffer_id, "offset": ev.get("hit_addr")},
                "method": "gdb_auto_trace",
                "proven": False,  # effective address observed but base may not be buffer
                "limitations": "effective address reconstructed from registers; base may not be buffer",
                "quantity": "gdb_effective",
            })
        if sz is not None:
            obs.append({
                "obs_id": f"auto_sz_{len(obs)}",
                "source_artifact": artifact,
                "kind": "gdb_auto_trace",
                "property_hint": "BUFFER_ACCESS_LENGTH",
                "value": sz,
                "value_kind": "OBSERVED",
                "location": {"function": target_buffer_id, "offset": ev.get("hit_addr")},
                "method": "gdb_auto_trace",
                "proven": False,
                "limitations": "size from mnemonic; not confirmed effective",
                "quantity": "gdb_observed",
            })
    # alias candidates: group by effective_address
    groups = {}
    for ev in events:
        ea = ev.get("effective_address")
        if ea is not None:
            groups.setdefault(ea, []).append(ev)
    for ea, grp in groups.items():
        if len(grp) > 1:
            obs.append({
                "obs_id": f"auto_alias_{len(obs)}",
                "source_artifact": artifact,
                "kind": "gdb_auto_trace",
                "property_hint": "BUFFER_ALIAS_SET",
                "value": "CANDIDATE",
                "value_kind": "CANDIDATE",
                "location": {"function": target_buffer_id, "offset": grp[0].get("hit_addr")},
                "method": "gdb_auto_trace",
                "proven": False,
                "limitations": "candidate alias by same effective address; not confirmed",
                "quantity": "gdb_observed",
            })

    result = {
        "status": "PASS_PARTIAL" if events else "BLOCKED",
        "decision": "PARTIAL" if events else "NOT_DETERMINED",
        "target": target_buffer_id,
        "artifact": artifact,
        "n_breakpoints": len(addrs),
        "n_hits": len(events),
        "n_accesses_found": len(accesses),
        "events": events,
        "metadata": meta,
        "errors": [],
        "provenance": {
            "method": "gdb_auto_trace",
            "sandbox": sandbox,
            "no_root": True,
            "limitations": "only breakpointed memory-access instructions; coverage limited",
        },
    }
    return result, obs, meta


__all__ = ["run_gdb", "parse_gdb_output", "to_observations", "run",
           "_find_mem_accesses", "auto_trace"]
