#!/usr/bin/env python3
"""RXRE-STRACE-ADAPTER. Reutiliza contratos existentes (results/findings/evidence).
No inventa campos nuevos; usa raw_json para preservar texto original.
Separado: parseo -> interpretacion -> claim (opcional, manual).
"""
import os, re, hashlib, json, time, sqlite3
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Regex básico para líneas strace conocidas
LINE_RE = re.compile(
    r"^(?P<pid>\d+)(?::(?P<tid>\d+))?\s+(?P<call>[a-zA-Z_][a-zA-Z0-9_]*)\((?P<args>.*)\)\s+=\s+(?P<res>-?\d+|0x[0-9a-fA-F]+)(?:\s+(?P<err>[A-Z_]+))?(?:\s+\((?P<note>.*)\))?$"
)
# Línea incompleta / desconocida: conservar tal cual con metadatos mínimos

def parse_strace(path, max_lines=None):
    h = hashlib.sha256()
    events = []
    with open(path, "rb") as f:
        content = f.read()
        h.update(content)
    artifacts_hash = h.hexdigest()
    # Procesar línea por línea con offset (bytes aproximado por línea para trazabilidad)
    lines = content.decode("utf-8", errors="replace").splitlines()
    byte_offset = 0
    for idx, line in enumerate(lines[:max_lines]):
        line_bytes = line.encode("utf-8") + b"\n"
        m = LINE_RE.match(line)
        event = {
            "source_file": path,
            "artifact_hash": artifacts_hash,
            "line_number": idx + 1,
            "byte_offset_approx": byte_offset,
            "original_text": line,
            "parsed": False,
            "pid": None,
            "tid": None,
            "syscall": None,
            "args_raw": None,
            "result_raw": None,
            "error_code": None,
            "note": None,
        }
        if m:
            event.update({
                "parsed": True,
                "pid": m.group("pid"),
                "tid": m.group("tid"),
                "syscall": m.group("call"),
                "args_raw": m.group("args"),
                "result_raw": m.group("res"),
                "error_code": m.group("err"),
                "note": m.group("note"),
            })
        events.append(event)
        byte_offset += len(line_bytes)
    return {"artifact": path, "hash": artifacts_hash, "total_lines": len(lines),
            "parsed_events": sum(1 for ev in events if ev["parsed"]),
            "unparsed_lines": len(events) - sum(1 for ev in events if ev["parsed"]),
            "events": events}

if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "audit/strace/glxinfo_trace_20261019_005110.txt"
    res = parse_strace(target)
    print(json.dumps({"artifact": res["artifact"], "hash": res["hash"],
                      "total_lines": res["total_lines"],
                      "parsed": res["parsed_events"],
                      "unparsed": res["unparsed_lines"],
                      "first_parsed": res["events"][0] if res["events"] else None}, default=str))
