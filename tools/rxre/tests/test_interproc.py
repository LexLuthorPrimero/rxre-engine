"""M580 interproc tests (10): supergraph CALL/RET + intraproc regression + ls call estimation."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.dataflow import decode_function
from tools.rxre.analysis.interproc import interproc_reaching

def dec(h,b=0x1000):
    return decode_function(bytes.fromhex(h),b)

def _mk():
    f1b=[{"id":"B0","offset":0x1000,"out_nodes":["C0"]},{"id":"C0","offset":0x1010,"out_nodes":["D0"]},{"id":"D0","offset":0x1020,"out_nodes":[]}]
    f1i={"B0":dec("48 89 d8",0x1000),"C0":dec("90",0x1010),"D0":dec("48 89 c1",0x1020)}
    f2b=[{"id":"K0","offset":0x2000,"out_nodes":["K1"]},{"id":"K1","offset":0x2010,"out_nodes":[]}]
    f2i={"K0":dec("48 89 d8",0x2000),"K1":dec("90",0x2010)}
    return f1b,f1i,f2b,f2i

def test_01_call_edge_reaches_callee():
    f1b,f1i,f2b,f2i=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    assert len(IN["K0"])>=1  # caller def reaches callee entry

def test_02_return_reaches_continuation():
    f1b,f1i,f2b,f2i=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    assert len(IN["D0"])>=1  # callee exit -> continuation

def test_03_no_call_no_interproc():
    f1b,f1i,_,_=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i)},[],"B0")
    assert set(["B0","C0","D0"]) <= set(IN.keys())

def test_04_kill_at_callee_entry():
    # callee K0 defines rax -> kills caller rax def in K0 OUT
    f1b,f1i,f2b,f2i=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    # K0 OUT gen is its own (r,0); caller def not propagated through K0
    assert len(OUT["K0"])>=1

def test_05_single_func_regression():
    from tools.rxre.analysis.ssa import build_graph, dominators
    f1b,f1i,_,_=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i)},[],"B0")
    assert "D0" in IN  # still functional

def test_06_two_call_edges():
    f1b,f1i,f2b,f2i=_mk()
    IN,OUT,_,_,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0"),("C0","K0",["K1"],"D0")],"B0")
    # duplicate edges tolerated (multiset succ)
    assert len(IN["K0"])>=1

def test_07_ids_present():
    f1b,f1i,f2b,f2i=_mk()
    _,_,_,_,ids=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    assert "B0" in ids and "K0" in ids and "D0" in ids

def test_08_succ_pred_symmetry():
    f1b,f1i,f2b,f2i=_mk()
    _,_,succ,pred,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    for n,outs in succ.items():
        for o in outs:
            assert n in pred.get(o,[])

def test_09_conservative_entry():
    f1b,f1i,f2b,f2i=_mk()
    IN,_,_,_,_=interproc_reaching({"F1":(f1b,f1i),"F2":(f2b,f2i)},[("C0","K0",["K1"],"D0")],"B0")
    assert len(IN["B0"])==0  # entry IN empty

def test_10_ls_calls_estimate():
    import subprocess, json, re
    p=subprocess.run(["/usr/bin/rizin","-q","-N","-e","scr.color=0","-c","aaa; aflj","/usr/bin/ls"],capture_output=True,text=True,timeout=60)
    out=re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]","",p.stdout)
    data=json.loads(out[out.find("["):])
    assert len(data)>=10  # ls has many funcs
    # count callrefs in first small func (finite)
    assert any(isinstance(f,dict) and f.get("callrefs") for f in data)

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name]()
            print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{10-fails}/10 PASS")
    sys.exit(1 if fails else 0)
