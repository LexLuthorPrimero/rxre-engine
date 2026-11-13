"""M653 EXIT SUMMARY: composición M650-M652 sin duplicar evidencias.
Local: termination cond, errors, priority, cleanup, exit. libc interno NOT_DETERMINED."""
from __future__ import annotations
from tools.rxre.analysis.fail_output import summary_fwrite_fail, summary_flush_fail
from tools.rxre.analysis.close_check import summary_close
from tools.rxre.analysis.result_code import derive

def summary_exit(write_ret_err, flush_ret, close_ret, tee_ret):
    fw = summary_fwrite_fail(-1 if write_ret_err else 0, 5 if write_ret_err else 0)
    cc = summary_close(flush_ret, close_ret)
    rc = derive(tee_ret, close_ret)
    # prioridad: write fail -> close fail -> exit (demostrado en CFG, no asumido fuera)
    priority = "write fail" if write_ret_err else ("close fail" if close_ret != 0 else "resultado tee_files")
    return {"termination": rc["path"], "errors": [fw["route"], cc["close_fail"]],
            "priority": priority, "cleanup": "close@0x4e0b -> fail_output@514d si !=0",
            "exit": rc["exit"], "libc": "FILE*/errno/flush NOT_DETERMINED"}

def rule_exit(tee_ret, close_ret):
    return derive(tee_ret, close_ret)["exit"]
