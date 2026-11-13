"""M650 FAIL OUTPUT local acotado: rutas cerradas a fail_output con offsets, resto libc NOT_DETERMINED."""
from __future__ import annotations

def summary_fwrite_fail(ret, errno_v):
    if ret is None: return {"route":"NOT_DETERMINED"}
    if ret<0: return {"route":"fail_output","off":"0x4f1c js","errno":"via __errno_location","status":"LOCAL"} 
    return {"route":"continue","off":"0x4f22","status":"LOCAL"}

def summary_flush_fail(ret):
    # NOTE: flush FILE* interno libc no probado
    return {"route":"retry_or_error","off":"0x4dff test jne 0x4e04","libc":"NOT_DETERMINED"}

def summary_close_fail(ret):
    return {"route":"fail_output@514d" if ret!=0 else "continue","off":"0x4e12 test jne 514d","libc":"FILE* NOT_DETERMINED"}

def summary_full(ret=None):
    return {"fail_output_local":"0x4a30 (framesize, errno+strerror helpers)","transitions":3,"libc_calls":"clearerr 780, __errno_location 730","status":"PARTIAL_LOCAL"}
