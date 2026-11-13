"""M644 BUFFER COPY TRACE acotado: read→buffer→write (sin inferir aliasing)."""
from __future__ import annotations

def describe_read(src, size, buf):
    return f"read(fd={src}, buf={buf}, size={size})"

def describe_write(buf, offset, length):
    return f"write(buf={buf}+{offset}, len={length})"

def trace_read_write(read_events, write_events):
    # reutilizado solo si mismo buf base y secuencia read; subsequent writes van en orden
    buf = read_events[0]["buf"] if read_events else None
    writes = [w for w in write_events if w.get("buf")==buf]
    return {"buf":buf,"reuse":len(writes)>0,"writes":writes,"reread_propagation":{"same_buf":True,"len_tied_to_ret":True}}

def classify_mechanism(has_read, has_write, has_sizevar, has_alt):
    if not has_read or not has_write:
        return "NOT_DETERMINED"
    if has_alt:
        return "ALTERNATIVE_ROUTES_PARTIAL"
    if has_sizevar:
        return "VAR_REUSE"
    return "FIXED_REUSE"
