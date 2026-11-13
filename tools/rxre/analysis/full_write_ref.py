"""M646 ref mínimo independiente (desde objdump 0x3200-0x324e):
state=offset(escritos), remaining, ptr avanza. Sin copiar rw_summary."""
# transiciones verificadas objdump:
#  - ret>0 < rem: offset+=ret, rem-=ret, loop
#  - ret==rem: offset=len, rem=0, exit(total)
#  - EINTR (4): mismo estado, retry
#  - error !=EINTR: exit parcial (total escritos)
#  - ret==0: exit parcial con errno 28
def step(offset, remaining, ret, errno=0):
    if ret < 0:
        if errno == 4: return {"offset": offset, "remaining": remaining, "action": "retry", "total": None}
        return {"offset": offset, "remaining": remaining, "action": "exit_partial", "total": offset}
    if ret == 0:
        return {"offset": offset, "remaining": remaining, "action": "exit_errno28", "total": offset}
    if ret < remaining:
        return {"offset": offset+ret, "remaining": remaining-ret, "action": "loop", "total": None}
    return {"offset": offset+ret, "remaining": 0, "action": "exit_total", "total": offset+ret}
