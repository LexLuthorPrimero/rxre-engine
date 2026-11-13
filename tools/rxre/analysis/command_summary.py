"""M670 COMMAND SUMMARY acotado (sed): parsing -> runtime struct -> execute."""
from __future__ import annotations

def describe_entry():
    return {"caller":"main 0x11e0","callee":"execute_program 0x80d0",
            "args":"arg1 struct ptr (rdi), arg2 idx (rsi)",
            "evidence":"aflj main callrefs + execute_program CFG 292bbs"}

def describe_struct():
    # struct arg1: [rdi+0x10] *5 factor, [rdi] base, alloc-related lea rdx,rdx*4 (objdump 0x80ed-0x80f1)
    return {"fields_demonstrados":["0x10 (*5 factor 0x80f1)","0x00 base"],
            "fields_partial":"0x948? no: stack ejecutado 0x10a8 lifetime execute_program (sin resolver alias)",
            "semantics":"PARTIAL (no DFA, no regex engine)"}

def describe_execute(cmd_class):
    return {"class":cmd_class,"effect":"sustitución/patrón visible en stdout (OS oracle)",
            "status":"SUPPORTED (oráculo OS para substitution visible)"}

def status_summary():
    return {"parsing":"PARTIAL","prep":"PARTIAL","runtime":"NOT_DETERMINED","exec":"SUPPORTED (visible)"}
