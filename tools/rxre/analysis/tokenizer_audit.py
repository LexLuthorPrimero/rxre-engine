"""M668 TOKENIZER AUDIT acotado: frontera tokenizer->estructura->consumidor (grep)."""
from __future__ import annotations

def describe_pattern_entry():
    # main getopt -> ... -> GEAcompile 0xd370 -> kwsprep 0xa850 (arg1 struct prep)
    return {"caller":"GEAcompile 0xd370","callee":"kwsprep 0xa850",
            "args":"arg1 struct ptr (rdi)","ret":"struct lifecycle (sin demostrar ret valor)",
            "fields_demostrados":["0x58","0x60","0x68","0x70","0x980"],
            "fields_partial":"0x948 stack buffer lifecycle NO resuelta"}

def classify_token(transform):
    if transform=="copy_memset_xmm": return "PARTIAL (runtime byte class, no tabla transiciones)"
    if transform=="dfa_transitions": return "NOT_DETERMINED"
    return "SUPPORTED (oraculo externo)"

def consumer_relation():
    return {"feeds_kwset":"NOT_DETERMINED (sin flujo datos mostrado)","feeds_dfa":"NOT_DETERMINED","literal":"NOT_DETERMINED (salvo grep mensual rc0/1/2 observable)"}
