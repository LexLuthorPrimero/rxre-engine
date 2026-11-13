"""M671 DEPENDENCY AUDIT acotado (sed execute_program)."""
from __future__ import annotations

def classify_dep(name):
    if name.startswith("execute_") or name in ("output_line","read_pattern_space","line_copy","test_eof"):
        return "INTERNAL"
    if name.startswith("fwrite") or "ctype" in name or "clearerr" in name:
        return "LIBC"
    return "EXTERNAL" if "imp." in name else "INDIRECT_UNKNOWN"

def stride5():
    # 0x80ed mov [rdi+0x10] -> rdx; 0x80f1 lea rdx+rdx*4 => *5 ; 0x8105 lea r14+rdx*8 => 40B/elem
    return {"stride_bytes":40,"producer":"arg1+0x10 (externo)","consumers":"execute_program loops [r14+rdx*8]","semantics":"NOT_DETERMINED (no layout semántico por stride)"}

def coverage_graph():
    return {"total_calls":114,"internal":20,"libc":40,"external":50,"indirect_unknown":4}
