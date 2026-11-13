"""M670 tests (8): command summary."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.command_summary import describe_entry, describe_struct, describe_execute, status_summary

def test_01_entry():
    assert describe_entry()["caller"]=="main 0x11e0"

def test_02_callee():
    assert "execute_program 0x80d0" in describe_entry()["callee"]

def test_03_struct():
    assert "0x10" in "".join(list(describe_struct().values())[0])

def test_04_field_partial():
    assert "PARTIAL" in describe_struct()["semantics"] or "PARTIAL" in describe_struct()["fields_partial"]

def test_05_execute_supported():
    assert describe_execute("substitution")["status"]=="SUPPORTED (oráculo OS para substitution visible)"

def test_06_summary_status():
    assert status_summary()["runtime"]=="NOT_DETERMINED"

def test_07_no_dfa():
    assert "PARTIAL" in describe_struct()["semantics"]

def test_08_oracle_links():
    # oráculo externo confirmado en dictamen: match rc0 / nomatch rc0 / noex rc2 (evidencia sistema, no prueba interna)
    assert describe_execute("substitution")["effect"].startswith("sustitución")

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
