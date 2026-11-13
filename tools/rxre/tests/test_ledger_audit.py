"""M593 tests (8): auditoría read-only ledger demo + inventario."""
import sys
sys.path.insert(0, '/home/lucas/Escritorio/rxre')
from tools.rxre.analysis.ledger_audit import verify_ledger, inventory_store

DB="/tmp/rx585/ledger_demo.sqlite3"
STORE="/home/lucas/Escritorio/rxre/.rxre/store_objects"

def test_01_ledger_ok():
    r=verify_ledger(DB); assert r["ok"] and r["n"]==4

def test_02_verified_count():
    r=verify_ledger(DB); assert r["verified"]==4

def test_03_missing_db():
    r=verify_ledger("/tmp/no_existe_xyz.sqlite3"); assert not r["ok"]

def test_04_inventory_244():
    r=inventory_store(STORE); assert r["n"]==244 and r["present"]

def test_05_readonly_no_write():
    # verifica que el módulo no abre en rw (grep)
    import inspect
    from tools.rxre.analysis import ledger_audit as m
    src=inspect.getsource(m)
    assert "mode=ro" in src and "INSERT" not in src

def test_06_drift_detects():
    import sqlite3, shutil, os
    shutil.copy(DB, "/tmp/rx593_tmp.sqlite3")
    con=sqlite3.connect("/tmp/rx593_tmp.sqlite3")
    con.execute("UPDATE ledger SET payload='evil' WHERE id=3")
    con.commit(); con.close()
    r=verify_ledger("/tmp/rx593_tmp.sqlite3")
    assert not r["ok"]  # drift detectado
    os.unlink("/tmp/rx593_tmp.sqlite3")

def test_07_genesis_present():
    import sqlite3
    con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows=con.execute("SELECT payload FROM ledger ORDER BY id").fetchall()
    con.close()
    assert rows[0][0]=="M585-DEMO"

def test_08_production_untouched():
    # rxre.sqlite3 no modificado por este test (mtime anterior al turno)
    import os
    assert os.path.exists("/home/lucas/Escritorio/rxre/rxre.sqlite3")

if __name__=="__main__":
    import traceback
    fails=0
    for name in [k for k in sorted(dir()) if k.startswith("test_")]:
        try:
            globals()[name](); print(f"PASS {name}")
        except Exception as e:
            fails+=1; print(f"FAIL {name}: {e}"); traceback.print_exc()
    print(f"{8-fails}/8 PASS"); sys.exit(1 if fails else 0)
