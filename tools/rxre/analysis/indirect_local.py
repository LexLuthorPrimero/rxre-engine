"""M636 INDIRECT LOCAL acotado: resuelve tablas con base/idx/scale/limites demostrados (lea+cmp+movslq).
Mantiene MAY para GOT runtime (deregister jmp rax) y PLT externos."""
from __future__ import annotations
from tools.rxre.analysis.jump_tables import resolve_relative

# Tablas demostradas en ls (de objdump, sin inventar):
TABLES = [
    {"site": 0x16da, "base": 0x1b214, "lo": 0, "hi": 0x114, "count": 277, "id": "getopt"},  # M633
    {"site": 0xb519, "base": 0x1b200, "lo": 0, "hi": 4, "count": 5, "id": "b519"},
]

def resolve_table(base, data, lo, hi):
    return resolve_relative(base, data, lo, hi, exec_lo=0x10c0, exec_hi=0x181d2)

def classify_indirect(kind):
    # kind: "got_local" | "got_plt" | "got_external" | "table" | "unknown"
    if kind in ("got_local", "table"):
        return "FINITE_TARGET_SET"
    if kind in ("got_external", "got_plt"):
        return "MAY_TARGET"
    return "UNKNOWN"
