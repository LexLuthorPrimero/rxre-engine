"""M630 test_call_summary (10): casos discriminantes."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.mem_pred import loc
from tools.rxre.analysis.call_summary import summarize, apply_summary, summarize_fixedpoint

FLAG=loc(0x25260,1); FNPTR=loc(0x24fe8,8); OTHER=loc(0x30000,1)

def test_01_callee_sin_efectos():
    s=summarize("callee", {"0":[("load",FLAG,"EQ",0)]}, "h1")
    assert not s["unknown"] and s["writes"]==set()
    assert apply_summary({(FLAG,"EQ",0)}, s)=={(FLAG,"EQ",0)}

def test_02_escribe_exacta():
    s=summarize("callee", {"0":[("store",FLAG,1)]}, "h1")
    assert apply_summary({(FLAG,"EQ",0)}, s)==set()

def test_03_escribe_disjunta():
    s=summarize("callee", {"0":[("store",OTHER,1)]}, "h1")
    assert apply_summary({(FLAG,"EQ",0)}, s)=={(FLAG,"EQ",0)}

def test_04_alias_posible_no_resuelto():
    # escritura anchura distinta solapada -> invalida (conservador)
    s=summarize("callee", {"0":[("store",loc(0x25260,8),1)]}, "h1")
    assert apply_summary({(FLAG,"EQ",0)}, s)==set()

def test_05_llamada_indirecta():
    s=summarize("indirect", None, "h1")
    assert s["unknown"] and apply_summary({(FLAG,"EQ",0)}, s)==set()

def test_06_externa_sin_cuerpo():
    s=summarize("ext", None, "h1")
    assert s["unknown"]

def test_07_escritura_condicional():
    # escribe en rama 1 solo: summary writes incluye loc -> conservador invalida en join
    s=summarize("callee", {"0":[("store",FLAG,1)],"1":[]}, "h1")
    assert FLAG in s["writes"]
    assert apply_summary({(FLAG,"EQ",0)}, s)==set()

def test_08_cadena_dos_llamadas():
    summaries=summarize_fixedpoint({"A":["B"],"B":[]}, {"A":{"0":[("call","B")]},"B":{"0":[("store",OTHER,1)]}}, "h1")
    # A llama a B (que escribe disjunta) -> A unknown por call anidada (conservador)
    assert summaries["A"]["unknown"] is True

def test_09_ciclo_recursion():
    summaries=summarize_fixedpoint({"A":["A"]}, {"A":{"0":[("call","A")]}}, "h1")
    assert summaries["A"]["unknown"] is True  # terminación sin autojustificación

def test_10_hash_invalidado():
    s1=summarize("callee", {"0":[("store",OTHER,1)]}, "h1")
    s2=summarize("callee", {"0":[("store",OTHER,1)]}, "h2")
    # summary ligado a hash: si cambia, caller debe tratar como unknown
    # (simulado por caller: if subj_hash mismatch -> unknown)
    assert s1["subj_hash"]!=s2["subj_hash"] and "h1" in s1["provenance"]

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS"); sys.exit(1 if fails else 0)
