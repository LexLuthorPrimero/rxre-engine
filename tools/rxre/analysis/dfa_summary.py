"""M661 DFA SUMMARY acotado: frontera kwsprep->DFA->search (sin tabla transiciones)."""
from __future__ import annotations

def describe_kwsprep(rdi_fields):
    return {"init":"arg1 struct prep","fields":list(rdi_fields),
            "writes":"stack memset 0x948 + xmm stores a8c3-a8e5",
            "evidence":"0xa850-0xb775 objdump (48 8b 43 68 + xmm stores)"}

def dfa_consumes(memset_dest, treenext_via):
    return {"dfa_input": memset_dest, "via": treenext_via,
            "status":"NOT_DETERMINED (transiciones internas)"}

def search_result(state):
    # state: "match" -> stdout+rc0 ; "nomatch" -> rc1 ; "error" -> stderr+rc2
    return 0 if state=="match" else (1 if state=="nomatch" else 2)

def claim_status(name):
    return {"kwsprep_prep":"PROVEN","DFA_transitions":"NOT_DETERMINED",
            "search_result":"SUPPORTED (oráculo OS)","kwsprep_callees":"PARTIAL"}[name]
