"""M631 PLT/GOT effects acotado: resuelve CALL->PLT->GOT->destino vía readelf local.
Solo destinos con cuerpo local verificable (reads/writes derivadas del cuerpo).
Ambiguo/externo/hash mismatch => unknown (conservador)."""
from __future__ import annotations
import subprocess, hashlib

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout

def resolve_plt_got(symbol: str, ls_path: str = "/usr/bin/ls") -> dict:
    """Devuelve cadena CALL/PLT/GOT/destino + is_local."""
    out = _run(["readelf", "-r", ls_path])
    got_plts = {}
    for line in out.splitlines():
        # parse: offset info type val symbol name
        parts = line.split()
        if len(parts) >= 5 and symbol in line:
            got_plts[line.strip()] = parts
    syms = _run(["readelf", "-s", ls_path])
    has_sym = symbol in syms
    # PLT destino: buscar plt si existe en objdump? usamos readelf -s + rizin aflj ya verificado
    # Heurística conservadora: si símbolo es UND y tipo NOTYPE => externo
    is_und = any("UND" in l and symbol in l for l in syms.splitlines())
    # body local: intentar rizin aflj offset
    import json, re
    p = subprocess.run(["/usr/bin/rizin","-q","-N","-e","scr.color=0","-c","aaa; aflj", ls_path], capture_output=True, text=True, timeout=60)
    txt = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]","", p.stdout)
    funcs = json.loads(txt[txt.find("["):])
    local = next((f for f in funcs if f.get("name","").endswith(symbol) and f.get("size",0)>20), None)
    # deregister_tm_clones es local (size 41), __cxa_finalize es imp (size 10)
    is_local_body = bool(local) and "imp." not in (local.get("name",""))
    h = hashlib.sha256(open(ls_path,"rb").read()).hexdigest()
    return {"symbol": symbol, "got_relocs": list(got_plts.keys())[:2], "has_sym": has_sym,
            "is_und": is_und, "local_entry": local.get("offset") if local else None,
            "local_size": local.get("size") if local else 0,
            "is_local_body": is_local_body, "subj_hash": h, "elf_path": ls_path}

def summarize_local_body(name, events, subj_hash=""):
    """Delegado a call_summary (fail-closed si unknown)."""
    from tools.rxre.analysis.call_summary import summarize
    return summarize(name, events, subj_hash)

def summary_for_symbol(symbol: str, ls_path: str = "/usr/bin/ls", local_events=None) -> dict:
    """PLT/GOT: si is_local_body y local_events provisto => summary conocido, si no unknown."""
    res = resolve_plt_got(symbol, ls_path)
    if not res["is_local_body"]:
        return {"name": symbol, "reads": set(), "writes": set(), "unknown": True,
                "coverage": 0.0, "subj_hash": res["subj_hash"],
                "provenance": f"{symbol}: PLT/GOT {res['got_relocs']} -> externo (UND={res['is_und']}) unknown"}
    if local_events is None:
        return {"name": symbol, "reads": set(), "writes": set(), "unknown": True,
                "coverage": 0.0, "subj_hash": res["subj_hash"],
                "provenance": f"{symbol}: local en {res['local_entry']} pero sin eventos -> unknown"}
    s = summarize_local_body(symbol, local_events, res["subj_hash"])
    s["provenance"] += f" | PLT/GOT {res['got_relocs']} local_entry={res['local_entry']}"
    return s
