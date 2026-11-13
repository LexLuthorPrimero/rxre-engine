"""M645 RW SUMMARY acotado: read/write con evidencia cat local.
Cada summary: precondiciones, retorno, efectos memoria, error conditions.
Sin inventar contratos externos; PARTIAL/UNKNOWN si depende runtime."""
from __future__ import annotations

def summary_read(pre, args, ret_positive=None, eof=None, error=None):
    # args: (fd, buf_base, size)
    return {"check":"__read_chk","precond":pre,"args":args,
            "ret":{"pos":ret_positive,"eof":eof,"err":error},
            "mem":"heap write buf[0..ret-1] si ret>0 (PARTIAL: alias heap/libc runtime)",
            "evidence":"main 0x14af js err, je EOF (M644)"}

def summary_full_write(buf, length, partial_loop=True):
    return {"check":"full_write","buf":buf,"len":length,
            "loop":"while remaining>0: call write(1,buf,remaining); EINTR retry",
            "evidence":"0x3200-0x324e (sub/add r12/r13, jg 31f0)"}

def summary_copy_range(src, dst, len):
    return {"check":"copy_file_range","args":(src,dst,len),
            "condition":"solo si condiciones locales (no probado entero)",
            "status":"PARTIAL (ruta alternativa sin exhaustividad)"}
