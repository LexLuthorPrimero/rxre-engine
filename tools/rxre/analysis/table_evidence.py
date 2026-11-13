"""M662 TABLE EVIDENCE acotado: candidatos DFA en grep sin declarar reconstrucción."""
from __future__ import annotations

STATUS = {"CONFIRMED_TABLE":"PROVEN","MATERIALIZED":"SUPPORTED","RUNTIME_BUILT":"PARTIAL","INACCESSIBLE":"NOT_DETERMINED"}

def classify(has_bytes, has_ref, has_consumer, materialized=True):
    if has_bytes and has_ref and has_consumer and materialized:
        return "CONFIRMED_TABLE"
    if has_bytes and has_ref and materialized:
        return "MATERIALIZED"
    if has_bytes and has_ref and not materialized:
        return "RUNTIME_BUILT"
    if not has_bytes or not has_ref:
        return "INACCESSIBLE"
    return "RUNTIME_BUILT"

def searchable_regions():
    return [".rodata",".data",".text(kwsprep stacks)"]

def coverage():
    return "309+ sec 0xa850-0xbc43 objdump/rizin; límites stack/executable no exhaustivos; ausencia != inexistencia"
