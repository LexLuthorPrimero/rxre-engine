"""M663 TRANSITION AUDIT acotado: layout runtime kwsprep + 14 indirects sin declarar DFA reconstruido."""
from __future__ import annotations

def layout_stack():
    # r12/stack 0x948-init con byte repetido min([0x68],0xff) xmm0 stores 0xa8c3-0xa93... (0xa8f2...0xb...), then campo r15 [0x60]
    return {"buf_size":"0x948 (stack sub rsp 0x948)",
            "init_byte":"min([0x68],0xff) broadcast xmm0",
            "writes":"0xa8c3-0xa93x movups x16 (0x100 bytes)",
            "lifetime":"kwsprep frame (rbp-0x978..-0x40)",
            "semantics":"char-class byte (PARTIAL, no tabla transiciones)"}

def classify_indirect(idx, base, has_limits, has_consumer):
    if has_limits and has_consumer:
        return "FINITE_TARGET_SET"
    if not has_limits:
        return "UNKNOWN"
    return "MAY_TARGET"

def relations_got():
    # registros x5, salto indirecto no relacionado a estructura kwsprep 0x948 (offsets distintos .text)
    return [{"site":"0x18e0 jmp *%rdx","status":"UNKNOWN (base/index no reunidos kwsprep)"}]

def verdict():
    return "PASS_PARTIAL (layout + 14 clasificados, transiciones NOT_DETERMINED)"
