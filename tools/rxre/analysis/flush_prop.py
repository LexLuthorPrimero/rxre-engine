"""M649 FLUSH PROPAGATION acotado: fwrite->iopoll->decision->flush/close->resultado.
Cada arista con offset/condición; FILE* interna UNKNOWN."""
from __future__ import annotations

def graph_edges():
    return [
        {"from":"fwrite_unlocked@4f11","cond":"rax>=0","to":"iopoll","off":"0x4f16-4f22","proof":"test/js/je + fwait@4f27 jne loop"},
        {"from":"fwrite_unlocked@4f11","cond":"rax<0","to":"error_d41","off":"0x4f1c","proof":"js d41"},
        {"from":"fwrite_unlocked@4f11","cond":"rax==0","to":"iopoll","off":"0x4f22","proof":"je 4f8a"},
        {"from":"iopoll/fwait","cond":"retry","to":"loop_4f00","off":"0x4f2e","proof":"jne 4f00"},
        {"from":"loop_exit","cond":"r13<=0","to":"next_stream","off":"0x4f61-4f6b","proof":"jge loop"},
        {"from":"fflush_unlocked@4dff","cond":"rax!=0","to":"retry/error","off":"0x4e04","proof":"jne","note":"FILE* interno NOT_DETERMINED"},
        {"from":"fclose_pair","cond":"test+fail","to":"fail_output@4f43/514d","off":"0x4e10-4e12","proof":"test/jne"},
    ]

def propagate(ret, errno_v):
    # sin equivalencia global, solo decisiones locales
    if ret is None: return "NOT_DETERMINED"
    if ret<0: return "error_path"
    if ret==0: return "iopoll_continue"
    return "loop_progress"

def failure_chain(error_kind):
    if error_kind=="write": return "fwrite -> js -> d41 error -> fail_output -> non-zero exit"
    if error_kind=="flush": return "fflush_unlocked -> jne -> retry/error (flush FILE* NOT_DETERMINED)"
    return "NOT_DETERMINED"
