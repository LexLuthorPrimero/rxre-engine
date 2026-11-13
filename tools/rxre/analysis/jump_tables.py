"""M633 JUMP TABLES acotadas: base+index*scale relativos (s32) con guard demostrados.
Estados como M632. Nunca inventa exhaustividad sin limites."""
from __future__ import annotations
import struct

SINGLE_TARGET_PROVEN="SINGLE_TARGET_PROVEN"
FINITE_TARGET_SET="FINITE_TARGET_SET"
MAY_TARGET="MAY_TARGET"
UNKNOWN="UNKNOWN"

def decode_offsets(data: bytes, count, width=4):
    if len(data) < count*width:
        return None  # truncada
    return [struct.unpack("<i", data[i*width:(i+1)*width])[0] for i in range(count)]

def resolve_relative(base, data, idx_lo, idx_hi, width=4, exec_lo=0x0, exec_hi=0x0):
    offs = decode_offsets(data, idx_hi-idx_lo+1)
    if offs is None:
        return (UNKNOWN, [], "truncada")
    # idx range fuera de lo alcanzado es MAY (no exhaustivo sin guard completo)
    dests=[]
    for i, off in enumerate(offs):
        idx = idx_lo+i
        d = base + off
        if exec_lo<=d<exec_hi:
            dests.append(d)
        else:
            # entrada inválida: no se promueve; el resto puede ser MAY, no FINITE exhaustivo
            return (MAY_TARGET, dests, f"dest fuera .text idx {idx}")
    return (FINITE_TARGET_SET, dests, "ok")

def resolve_absolute(base, data, count, width=8):
    # absoluta (8B LE): dest = entrada
    if len(data) < count*width:
        return (UNKNOWN, [], "truncada")
    return (FINITE_TARGET_SET, [struct.unpack("<Q", data[i*width:(i+1)*width])[0] for i in range(count)], "ok")

def invalidated_by_write(summary_known=True):
    return not summary_known  # alias/CALL unknown => invalida
