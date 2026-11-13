"""M672 STRIDE SEM acotado: mapa accesos por elemento 40B (sed execute)."""
from __future__ import annotations

FIELDS = [
    ("+0","8","ptr (read (%r12))","PROVEN"),
    ("+8","8","ptr ([r12+8] mov rcx)","PROVEN"),
    ("+0x10","4","int type/state (mov eax/cmp 1,2 + store 1)","PROVEN"),
    ("+0x15","1","char flag (cmp byte [r12+0x15],0x7d)","SUPPORTED"),
    ("0..0x27 resto","NA","sin acceso observado","NOT_DETERMINED"),
]

def classify_field(off):
    for o,w,op,st in FIELDS:
        if o==f"+{off}" or off==o:
            return st
    return "NOT_DETERMINED"

def map_accesses():
    return [{"offset":o,"width":w,"op":op,"status":st} for o,w,op,st in FIELDS]

def producer_of(field):
    if field=="+0x10": return "internal store 0x817d (movl 1)"
    return "arg1 producer (externo ui) - NOT_DETERMINED"
