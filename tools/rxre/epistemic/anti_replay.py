"""Anti-replay authorize_and_consume + consumed.jsonl (extracción, stdlib+fcntl)."""
from __future__ import annotations
import fcntl, hashlib, json, os
from pathlib import Path

ConsumedFile = None  # configurable por caller via env EPISTEMIC_LEDGER o defecto
def _ledger_path():
    p = os.environ.get("EPISTEMIC_LEDGER")
    return Path(p) if p else Path("/tmp/epistemic_consumed.jsonl")

def _digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def audit_ledger(path=None):
    p = Path(path) if path else _ledger_path()
    if not p.exists():
        return []
    entries = []
    for line in p.read_text().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    # verificar cadena hash
    prev = ""
    for e in entries:
        payload = json.dumps({"dictamen_id": e.get("dictamen_id"), "verification_ref": e.get("verification_ref"), "consumer": e.get("consumer"), "seq": e.get("seq"), "prev_digest": prev}, sort_keys=True).encode()
        if _digest(payload) != e.get("digest"):
            raise ValueError("cadena hash rota")
        prev = e.get("digest")
    return entries

def authorize_and_consume(verification_ref: str, consumer_id: str, path=None) -> dict:
    if not verification_ref or not consumer_id:
        return {"ok": False, "reason": "referencia/consumidor requeridos"}
    p = Path(path) if path else _ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        content = f.read()
        entries = [json.loads(l) for l in content.splitlines() if l.strip()]
        for e in entries:
            if e.get("verification_ref") == verification_ref and e.get("consumer") == consumer_id:
                fcntl.flock(f, fcntl.LOCK_UN)
                return {"ok": False, "reason": "replay detectado"}
        prev = entries[-1]["digest"] if entries else ""
        seq = len(entries) + 1
        payload = json.dumps({"dictamen_id": f"d-{seq}", "verification_ref": verification_ref, "consumer": consumer_id, "seq": seq, "prev_digest": prev}, sort_keys=True).encode()
        entry = {"dictamen_id": f"d-{seq}", "verification_ref": verification_ref, "consumer": consumer_id, "seq": seq, "prev_digest": prev, "digest": _digest(payload)}
        f.write(json.dumps(entry, sort_keys=True) + "\n"); f.flush(); os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)
        return {"ok": True, "entry": entry}

class AuditEntry:
    def __init__(self, **kw):
        self.__dict__.update(kw)
