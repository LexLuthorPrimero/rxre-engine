"""M651 CLOSE CHECK acotado: rutas locales flush/close/fail_output."""
from __future__ import annotations
def summary_close(flush_ret, close_ret):
    # flush_ret None => flush FILE* NOT_DETERMINED
    return {"flush":"NOT_DETERMINED (FILE* libc)",
            "close_fail":"fail_output@514d" if close_ret!=0 else "continue",
            "order":"flush@4dff -> close@4e0b -> fail_output (ramas test/jne)",
            "evidence":"0x4dff test jne 0x4e04, 0x4e10 test jne 514d"}
def route_normal():
    return {"flush":"NOT_DETERMINED","close":"0","exit":"0","status":"LOCAL"}
def route_write_fail():
    return {"route":"fail_output@0x4f43","exit":"1","status":"LOCAL"}
