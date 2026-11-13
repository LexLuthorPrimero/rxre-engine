"""M631 tests (8): PLT/GOT + call_summary + M630."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.plt_got_effects import resolve_plt_got, summary_for_symbol
from tools.rxre.analysis.mem_pred import loc

def test_01_deregister_local():
    r=resolve_plt_got("deregister_tm_clones")
    assert r["is_local_body"] and r["local_entry"]==14656

def test_02_cxa_external():
    r=resolve_plt_got("__cxa_finalize")
    assert not r["is_local_body"] or "imp." in str(r)

def test_03_got_reloc_present():
    r=resolve_plt_got("__cxa_finalize")
    assert any("GLOB_DAT" in x or "JUMP_SLO" in x for x in r["got_relocs"])

def test_04_summary_local_conocido():
    ev={"0":[("load",loc(0x24f78,8),"NE",0)]}
    s=summary_for_symbol("deregister_tm_clones", local_events=ev)
    assert not s["unknown"] and (0x24f78,8) in s["reads"]

def test_05_summary_externa_unknown():
    s=summary_for_symbol("__cxa_finalize")
    assert s["unknown"]

def test_06_hash_ligado():
    r1=resolve_plt_got("deregister_tm_clones")
    assert len(r1["subj_hash"])==64

def test_07_integracion_call_summary():
    from tools.rxre.analysis.call_summary import apply_summary
    ev={"0":[("load",loc(0x24f78,8),"NE",0)]}
    s=summary_for_symbol("deregister_tm_clones", local_events=ev)
    # escribe nada disjunta de FLAG => preserva
    assert apply_summary({(loc(0x25260,1),"EQ",0)}, s)=={(loc(0x25260,1),"EQ",0)}

def test_08_no_optimista_ambiguo():
    s=summary_for_symbol("__cxa_finalize")
    from tools.rxre.analysis.call_summary import apply_summary
    assert apply_summary({(loc(0x25260,1),"EQ",0)}, s)==set()

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
