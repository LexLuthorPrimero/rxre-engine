"""M648 STDIO SUMMARY acotado (tee): fread/write_unlock + iopoll coordination.
No atribuye libc interna (offsets/nombres); PARTIAL/NOT_DETERMINED si falta evidencia."""
from __future__ import annotations

def summary_stdio_read(fd_ptr, buf_base, req=0x2000):
    return {"call":"read","fd":fd_ptr,"buf":buf_base,"req":req,
            "ret":{"pos":">0","eof":"0","err":"-1 (errno 4=EINTR retry, else error 4dbd)"},
            "evidence":"0x4d82 mov 0x2000, lea -0x2040, call read@4d90, test jns/j*",
            "mem":"stack buf PARTIAL (libc internal no probado)"}

def summary_stdio_write(ptr, nmemb, stream, buf_progress=False):
    return {"call":"fwrite_unlocked","ptr":ptr,"size":1,"nmemb":nmemb,
            "loop":"4f00-4f2e: sub remaining, iopoll/fwait retry, jge/jg",
            "evidence":"0x4f11 fwrite_unlocked@plt, sub/add 4f19/4f00, test js/je",
            "stdio":"buffering/flush FILE* PARTIAL (libc lock/buffer no probado)",
            "ret":"?=elementos (no equivalencia raw)"}

def summary_iopoll(has_fwait=True):
    return {"iopoll":"fwait_for_nonblocking_write" if has_fwait else "none",
            "semantics":"coordinación PARTIAL (args fcntl/errno no probados exhaustivos)"}
