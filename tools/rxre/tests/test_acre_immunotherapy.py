"""Tests ACRE Immunotherapy (sin binario cerrado real, solo sintético)."""
import hashlib, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from rxre.acre.immunotherapy import apply_patch, apply_rollback, repair_rate, guard_patch

def test_patch_minimo_y_rollback():
    b = b"\x00\x5a\x00"
    p, u = apply_patch(b, 1, 0x64)
    assert p == b"\x00\x64\x00"
    assert u.file_offset == "0x1" and u.bytes_before == "5a" and u.bytes_after == "64"
    assert apply_rollback(b, p) == b
    assert hashlib.sha256(p).hexdigest() == u.patched_hash

def test_repair_rate_sellado():
    cases = [{"diverges": True, "fixed": True}, {"diverges": True, "fixed": False}, {"diverges": False, "fixed": True}]
    assert repair_rate(cases) == 0.5

def test_guard_fail_closed():
    from rxre.acre.immunotherapy import PatchUnit
    u = PatchUnit("a"*64, "b"*64, "0x1", "0x400001", "5a", "64", "cmp")
    assert guard_patch(u, "a"*64) is True
    assert guard_patch(u, "c"*64) is False
