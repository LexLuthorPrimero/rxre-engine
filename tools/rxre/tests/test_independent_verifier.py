#!/usr/bin/env python3
"""Test unitarios de IndependentVerifier (offline, sin GPU, sin LLM)."""
import sys, json, os, tempfile, shutil
from pathlib import Path
sys.path.insert(0, '/home/lucas/Escritorio/rxre')

from tools.rxre.verifier import independent_verifier as IV
from tools.rxre.verifier.independent_verifier import (
    build_clean_room, verify_manifest, lock_package, unlock_package,
    check_seal, audit_export, VerificationRequest, CaseSpec, verify,
    EXECUTION_BLOCKED, EPISTEMIC_NOT_DETERMINED)

def t_clean_room_and_lock():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        tgt = td / "obj.spv"; tgt.write_bytes(b"\xde\xad\xbe\xef" * 32)
        pkg = Path(build_clean_room(str(tgt), [], CaseSpec(
            case_id="T1", target="obj.spv", artifact_sha256=IV.sha256_file(tgt),
            objective="nc", dispatch_description={"wg": 2}), str(td / "pkg")))
        m = verify_manifest(pkg); assert m["ok"], m
        lock_package(pkg)
        ok = False
        try:
            with (pkg / "comp.spv").open("ab") as f:
                f.write(b"x")
        except PermissionError:
            ok = True
        assert ok, "write inside locked package must fail"
        unlock_package(pkg)
        print("T1 clean-room+lock: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def t_manifest_tamper():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        tgt = td / "o.spv"; tgt.write_bytes(b"A" * 16)
        pkg = Path(build_clean_room(str(tgt), [], CaseSpec("T2", "o.spv",
            IV.sha256_file(tgt), "nc", {}), str(td / "pkg")))
        fp = pkg / "o.spv"; data = fp.read_bytes(); fp.write_bytes(b"B" + data[1:])
        m = verify_manifest(pkg); assert not m["ok"], "tamper not detected"
        print("T3 manifest tamper detected: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def t_extra_files_rejected():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        tgt = td / "o.spv"; tgt.write_bytes(b"A" * 16)
        pkg = Path(build_clean_room(str(tgt), [], CaseSpec("T4", "o.spv",
            IV.sha256_file(tgt), "nc", {}), str(td / "pkg")))
        (pkg / "SEALED_PREDICTION.json").write_text("{}")
        m = verify_manifest(pkg); assert not m["ok"] and m.get("extra_files")
        print("T4 extra file (injected) rejected: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def t_seal_check():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        p = td / "pred.json"; p.write_text(json.dumps({"a": 1}))
        actual = IV.sha256_file(p)
        s = td / "sealed.json"; s.write_text(json.dumps({"sealed_sha256": actual}))
        r = check_seal(str(p), str(s)); assert r["ok"]
        p.write_text(json.dumps({"a": 2}))
        r = check_seal(str(p), str(s)); assert not r["ok"]
        print("T5 seal integrity both ways: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def t_dryrun_blocked():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        tgt = td / "o.spv"; tgt.write_bytes(b"A" * 16)
        req = VerificationRequest(
            target=str(tgt), evidence_package=None,
            case=CaseSpec("T6", "o.spv", IV.sha256_file(tgt), "nc", {}),
            workdir=str(td))
        res = verify(req, runner=None)
        assert res.execution_status == EXECUTION_BLOCKED and res.epistemic_status == EPISTEMIC_NOT_DETERMINED
        print("T6 dry-run fail-closed: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

def t_audit_export_order():
    td = Path(tempfile.mkdtemp(prefix="vf_test_"))
    try:
        exp = td / "export.json"
        exp.write_text(json.dumps({"messages": [
            {"time": {"created": 1}, "content": [{"type": "tool", "state": {"input": {"command": "spirv-dis /evidence/comp.spv"}}}]},
            {"time": {"created": 2}, "content": [{"type": "tool", "state": {"input": {"command": "echo sha > SEALED_VERIFIER_PREDICTION.json"}}}]},
            {"time": {"created": 3}, "content": [{"type": "tool", "state": {"input": {"command": "cat /evidence/gpu_output.txt"}}}]},
        ]}))
        a = audit_export(str(exp), ["RXRE_PLAN_MAESTRO"], r"SEALED_VERIFIER_PREDICTION\.json", r"gpu_output\.txt")
        assert a["seal_before_reveal"] and a["forbidden_clean"]
        print("T7 audit seal-before-reveal + forbidden: PASS")
    finally:
        shutil.rmtree(td, ignore_errors=True)

if __name__ == "__main__":
    t_clean_room_and_lock(); t_manifest_tamper(); t_extra_files_rejected()
    t_seal_check(); t_dryrun_blocked(); t_audit_export_order()
    print("ALL UNIT TESTS PASS")
