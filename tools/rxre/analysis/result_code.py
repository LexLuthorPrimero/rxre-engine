"""M652 RESULT CODE acotado: main ret = (tee_files_ret ^1), con close fail -> 1.
No inferir FILE*/errno internos."""
def derive(tee_ret, close_ret):
    # main 0x126c ebx=tee_ret; 0x126e close; test close je? jne error=1 (14c5)
    if close_ret != 0:
        return {"exit": 1, "path": "close fail 14c5", "tee_ret": tee_ret}
    return {"exit": (tee_ret ^ 1) & 0xff, "path": "xor1 0x127b movzbl", "tee_ret": tee_ret}
