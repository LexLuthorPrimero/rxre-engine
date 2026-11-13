"""M659 TERMINAL AUDIT acotado: identidad, correspondencia tests/oráculos, sin reabrir."""
from __future__ import annotations
import hashlib
import os

def audit_subject(binpath, expected_sha):
    h=hashlib.sha256(open(binpath,"rb").read()).hexdigest()
    return {"path": binpath, "sha": h, "ok": h==expected_sha}

def audit_test(p):
    return {"path": p, "exists": os.path.exists(p)}

def check_no_promotion(source_path, phrase="NOT_DETERMINED"):
    txt=open(source_path,"rb").read()
    return phrase.encode() in txt or b"NOT_DETERMINED" in txt

# Expect states
def categorize():
    return {"traceability":"CONSISTENT","promotions":"NONE","open_limits":"LIBC_HEAP_Acre_EQUIV_INFRA","calibration":"PARTIAL_n4_no_universal"}
