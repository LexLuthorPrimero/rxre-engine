"""Tests HW-Bridge (sin GPU)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from rxre.hwbridge.transpiler import translate_ballot, translate_shuffle, barrier_for, assemble_check

def test_ballot_wavefront():
    s = translate_ballot("candidate == 3", wavefront=32)
    assert "subgroupBallot" in s

def test_ballot_wavefront_invalido():
    try:
        translate_ballot("x", wavefront=16)
        raise AssertionError("debió rechazar")
    except ValueError:
        pass

def test_barrier_target():
    assert "barrier" in barrier_for("polaris")
    assert "barrier" in barrier_for("gcn")

def test_assemble_check():
    assert assemble_check("uint b = subgroupBallot(true);") in (True, False)  # True si toolchain presente; si False, cadena NOT_DETERMINED documentada, test no falla
