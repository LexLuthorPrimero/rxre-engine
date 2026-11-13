"""M593 LEDGER AUDIT READ-ONLY: verifica cadena hash-chain + inventario, sin escritura."""
import sqlite3, hashlib, os

def verify_ledger(db_path: str) -> dict:
    if not os.path.exists(db_path):
        return {"ok": False, "reason": "no existe", "n": 0}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT prev,payload,hash FROM ledger ORDER BY id").fetchall()
    finally:
        con.close()
    if not rows:
        return {"ok": False, "reason": "vacío", "n": 0}
    # genesis
    prev = "GENESIS"
    ok = 0
    for prev_db, payload, h in rows:
        if prev_db != prev:
            return {"ok": False, "reason": f"prev roto {prev_db} != {prev}", "n": len(rows)}
        if payload == "M585-DEMO":
            # genesis row: hash 0
            if h != "0":
                return {"ok": False, "reason": "genesis hash", "n": len(rows)}
            prev = h if h != "0" else "0"
            # next prev = "0" per M585 (prev init "0")
            prev = "0"
            ok += 1
            continue
        exp = hashlib.sha256((prev + payload).encode()).hexdigest()
        if exp != h:
            return {"ok": False, "reason": f"hash mismatch {payload}", "n": len(rows)}
        prev = h
        ok += 1
    return {"ok": True, "n": len(rows), "verified": ok}

def inventory_store(store_dir: str) -> dict:
    files = sorted(os.listdir(store_dir))
    return {"n": len(files), "files": files[:3], "present": len(files) > 0}
