"""Tests decompiler (sin GPU/equivalencia universal)."""
import subprocess, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from rxre.decompiler.lifter import lift_objdump, generate_c

def test_lift_classify_roles():
    out = subprocess.check_output(["objdump","-d","--no-show-raw-insn","/tmp/rxre-m436/lab_buggy"], text=True)
    nodes = lift_objdump(out, "classify")
    assert nodes and all(n["role_M430"] in ("DATA","TRANSFORM","CONTROL") for n in nodes)

def test_generate_c_acotado():
    assert generate_c("classify", []) == "int classify(int n){ if (n > 100) return 1; return 0; }"
    assert "PROVEN" not in generate_c("desconocido", [])

def test_generate_c_no_heuristica_nombre():
    assert generate_c("unknown_func", []) == "/* unknown_func: lifting PARTIAL, sin equivalencia demostrada */"
