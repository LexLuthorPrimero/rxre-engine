#!/usr/bin/env python3
"""RXRE — Registro y autoridad central de dictámenes (endurecido, fase VERIFIER-004).

Backend aislado: `RXRE_DICTAMEN_DIR` (default /tmp/rxre_authority/).
Garantías técnicas reales (y sus límites) están documentadas en
/tmp/rxre_verifier_004/TRUST_BOUNDARY.md. Este módulo NO declara autenticidad
ante procesos con mismo UID; detecta manipulación por comparación de hashes sellados.

- Escritura atómica (tmp+rename, fsync archivo y directorio)
- O_NOFOLLOW en lecturas: rechaza symlinks
- Chequeo propietario/no-hardlink/regular-file en cada lectura
- Validación estricta de esquema y tipos (allowlist)
- Registry state con digest monótono: detecta truncado/eliminación/rollback
- fcntl flock en registro y en authorize (misma MÁCINA)
- Re-derivación de decisión antes de otorgar autorización
"""
from __future__ import annotations
import hashlib, json, os, re, stat, fcntl
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import acceptance_policy as ap

DICTAMEN_DIR = os.environ.get("RXRE_DICTAMEN_DIR", "/tmp/rxre_authority")
REGISTRY = "dictamenes.jsonl"
STATE_FILE = "registry_state.json"
LOCK_FILE = ".lock"
DICT_DIR = "dictamenes"
MAX_FILE_BYTES = 65536
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,127}$")

class AuthorityError(Exception):
    pass

# ---------------------------------------------------------------------------
# filesystem fundamentals
# ---------------------------------------------------------------------------
def _uid() -> int:
    return os.getuid()

def _dir() -> Path:
    d = Path(os.environ.get("RXRE_DICTAMEN_DIR", DICTAMEN_DIR))
    try:
        if not d.exists():
            d.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(d, 0o700)
        (d / DICT_DIR).mkdir(mode=0o700, exist_ok=True)
        os.chmod(d / DICT_DIR, 0o700)
    except PermissionError:
        raise AuthorityError(f"no se puede asegurar privacidad del directorio autoridad: {d}")
    return d

def _fsync_dir(d: Path):
    fd = os.open(str(d), os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def _safe_read(p: Path, allow_empty: bool = False) -> Tuple[bytes, os.stat_result]:
    if p.is_symlink():
        raise AuthorityError(f"symlink rechazado: {p}")
    if not p.is_file():
        raise AuthorityError(f"no es archivo regular: {p}")
    st = p.stat()
    if st.st_uid != _uid():
        raise AuthorityError(f"propietario distinto ({st.st_uid}): {p}")
    if st.st_nlink != 1:
        raise AuthorityError(f"hardlink rechazado (nlink={st.st_nlink}): {p}")
    if st.st_size > MAX_FILE_BYTES:
        raise AuthorityError(f"tamaño inválido ({st.st_size}): {p}")
    if st.st_size == 0 and not allow_empty:
        raise AuthorityError(f"tamaño inválido (empty): {p}")
    fd = os.open(str(p), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        data = os.read(fd, MAX_FILE_BYTES + 1)
    finally:
        os.close(fd)
    return data, st

def _safe_write(p: Path, content: bytes) -> None:
    p = Path(p)
    if p.exists() and p.is_symlink():
        raise AuthorityError(f"symlink de escritura rechazado: {p}")
    tmp = p.with_suffix(p.suffix + f".tmp.{os.getpid()}.{os.urandom(4).hex()}")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, content)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(str(tmp), str(p))
    _fsync_dir(p.parent)

def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _sha256_obj(o: Any) -> str:
    return _sha256_bytes(json.dumps(o, sort_keys=True, default=str).encode())

# ---------------------------------------------------------------------------
# strict validation (allowlist + types)
# ---------------------------------------------------------------------------
_DICTAMEN_REQUIRED = {
    "dictamen_id": str, "investigation_id": str, "artifact_sha256": str,
    "target_file": str, "domain": str, "epistemic_status": str,
    "decision": str, "policy": str, "timestamp": str,
    "verification_result_hash": str, "accepted": bool,
}
_DICTAMEN_OPTIONAL = {"limitations": list, "evidence_refs": list,
                      "decision_detail": str, "seq": int}

def _strict_obj(d: Any, req: Dict[str, type], opt: Dict[str, type], ctx: str) -> Dict[str, Any]:
    if not isinstance(d, dict):
        raise AuthorityError(f"{ctx}: objeto no es dict")
    for k, t in req.items():
        if k not in d:
            raise AuthorityError(f"{ctx}: falta campo requerido '{k}'")
        if not isinstance(d[k], t):
            raise AuthorityError(f"{ctx}: tipo inválido en '{k}' ({type(d[k]).__name__})")
        if isinstance(d[k], str) and _ID_RE and k in ("investigation_id", "target_file", "dictamen_id"):
            if not _ID_RE.match(d[k]):
                raise AuthorityError(f"{ctx}: campo ilegible en '{k}'")
    for k, v in d.items():
        if k in req or k in opt:
            if k in opt and not isinstance(v, opt[k]):
                raise AuthorityError(f"{ctx}: tipo inválido en opcional '{k}'")
        else:
            raise AuthorityError(f"{ctx}: campo inesperado '{k}'")
    if not re.fullmatch(r"[0-9a-f]{64}", d["artifact_sha256"]):
        raise AuthorityError(f"{ctx}: artifact_sha256 inválido")
    if not re.fullmatch(r"[0-9a-f]{64}", d["verification_result_hash"]):
        raise AuthorityError(f"{ctx}: verification_result_hash inválido")
    return d

_VR_REQUIRED = {"execution_status": str, "epistemic_status": str}
_VR_OPTIONAL = {"integrity": dict, "session_audit": dict, "verdict": dict,
                "limitations": list, "driver": dict, "artifacts": dict,
                "metrics": dict, "verdict_hash": str}
# claves conocidas del Verdict/extensiones verificadas en read-back
_VR_KNOWN = set(_VR_REQUIRED) | set(_VR_OPTIONAL) | {"audit_log", "investigation_id", "domain",
                                                     "artifact_sha256", "target_file",
                                                     "register_dictamen", "seal", "timestamp"}

def _validate_vr(d: Any, ctx: str) -> Dict[str, Any]:
    if not isinstance(d, dict):
        raise AuthorityError(f"{ctx}:VR no es dict")
    for k in d:
        if k not in _VR_KNOWN:
            raise AuthorityError(f"{ctx}: campo inesperado en VR '{k}'")
    es = d.get("execution_status"); ep = d.get("epistemic_status")
    if not isinstance(es, str) or es not in ("OK", "BLOCKED", "RUNNING"):
        raise AuthorityError(f"{ctx}: execution_status desconocido: {es}")
    if not isinstance(ep, str) or ep not in ("PROVEN", "PARTIAL", "NOT_DETERMINED", "BLOCKED", "ABSTAINED"):
        raise AuthorityError(f"{ctx}: epistemic_status desconocido: {ep}")
    integ = d.get("integrity")
    audit = d.get("session_audit")
    if not isinstance(integ, dict) or not isinstance(audit, dict):
        raise AuthorityError(f"{ctx}: integrity/session_audit ausentes")
    return d

# ---------------------------------------------------------------------------
# state management (rollback/truncation detection)
# ---------------------------------------------------------------------------
def _read_state(d: Path, migrate: bool = False) -> Dict[str, Any]:
    st = d / STATE_FILE
    if not st.exists():
        raw = _read_registry_raw(d)
        lines = [l for l in raw.splitlines() if l.strip()]
        return {"count": len(lines), "digest": _jsonl_digest(raw), "seq": len(lines), "legacy": True}
    try:
        data, _ = _safe_read(st, allow_empty=True)
        s = json.loads(data.decode())
        if not isinstance(s, dict):
            return {"count": -1, "digest": "CORRUPT", "seq": -1}
        return s
    except Exception:
        return {"count": -1, "digest": "CORRUPT", "seq": -1}

def _jsonl_digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def _read_registry_raw(d: Path) -> bytes:
    reg = d / REGISTRY
    if not reg.exists():
        return b""
    data, _ = _safe_read(reg, allow_empty=True)
    return data

def _write_state(d: Path, count: int, digest: str, seq: int):
    st = {"count": count, "digest": digest, "seq": seq}
    _safe_write(d / STATE_FILE, json.dumps(st, sort_keys=True).encode())

# ---------------------------------------------------------------------------
# locking
# ---------------------------------------------------------------------------
import contextlib

@contextlib.contextmanager
def _with_lock(d: Path):
    lock = d / LOCK_FILE
    fd = os.open(str(lock), os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)

# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def register_dictamen(verification_result: Dict[str, Any], *,
                      investigation_id: str, artifact_sha256: str,
                      target_file: str, domain: str) -> Dict[str, Any]:
    """Persiste dictamen con vinculación + validación estricta + estado monótono."""
    if not isinstance(verification_result, dict):
        raise AuthorityError("VR no es dict")
    vr = _validate_vr(verification_result, "register")
    for name in ("investigation_id", "target_file", "domain"):
        v = locals()[name]
        if not isinstance(v, str) or not v:
            raise AuthorityError(f"{name} requerido")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise AuthorityError("artifact_sha256 inválido")
    if not _ID_RE.match(investigation_id):
        raise AuthorityError("investigation_id inválido")
    if not _ID_RE.match(target_file):
        raise AuthorityError("target_file inválido")

    d = _dir()
    with _with_lock(d):
        rec_path = d / DICT_DIR / f"dic_{investigation_id}_{artifact_sha256[:12]}.json"
        vr_path = d / DICT_DIR / f"dic_{investigation_id}_{artifact_sha256[:12]}.vr.json"

        raw_new = _sha256_bytes(json.dumps(vr, sort_keys=True, default=str).encode())
        vr_bytes = json.dumps({"__sha256": raw_new, "result": vr},
                              ensure_ascii=False, sort_keys=True).encode()
        rec = {
            "dictamen_id": f"dic_{investigation_id}_{artifact_sha256[:12]}",
            "investigation_id": investigation_id,
            "artifact_sha256": artifact_sha256,
            "target_file": target_file,
            "domain": domain,
            "epistemic_status": vr.get("epistemic_status", "BLOCKED"),
            "decision": ap.decide(vr, investigation_id=investigation_id,
                                  artifact_sha256=artifact_sha256,
                                  target_file=target_file, domain=domain)["decision"],
            "limitations": list(vr.get("limitations") or []),
            "policy": "acceptance_policy/v1",
            "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "verification_result_hash": raw_new,
            "evidence_refs": (vr.get("verdict") or {}).get("evidence_refs", []),
            "decision_detail": ap.decide(vr, investigation_id=investigation_id,
                                         artifact_sha256=artifact_sha256,
                                         target_file=target_file, domain=domain).get("reason", ""),
            "accepted": bool(ap.decide(vr, investigation_id=investigation_id,
                                       artifact_sha256=artifact_sha256,
                                       target_file=target_file, domain=domain).get("accepted", False)),
        }
        # seq: mono creciente
        st = _read_state(d)
        if st["count"] < 0:
            raise AuthorityError("registry_state corrupto")
        seq = st["seq"] + 1
        rec["seq"] = seq

        if rec_path.exists():
            old = json.loads(_safe_read(rec_path)[0].decode())
            # Sólo idempotencia exacta
            if all(old.get(k) == rec.get(k) for k in
                   ("verification_result_hash", "artifact_sha256", "domain", "decision",
                    "investigation_id", "target_file")):
                return old
            raise AuthorityError("dictamen duplicado con contenido distinto (posible replay)")

        _safe_write(rec_path, json.dumps(rec, ensure_ascii=False, indent=2).encode())
        _safe_write(vr_path, vr_bytes)
        # registry JSONL append atomically
        reg = d / REGISTRY
        prev = _read_registry_raw(d)
        line = json.dumps(rec, ensure_ascii=False, sort_keys=True).encode() + b"\n"
        new = prev + line
        _safe_write(reg, new)
        _write_state(d, st["count"] + 1, _jsonl_digest(new), seq)
        return rec

def attach_verification_result(rec: Dict[str, Any], verification_result: Dict[str, Any]):
    """Redundante en el flujo nuevo (vr se guarda siempre en register_dictamen).
    Se conserva para compatibilidad; no sobrescribe un dictamen existente."""
    d = _dir()
    vr_path = d / DICT_DIR / f"{rec['dictamen_id']}.vr.json"
    if vr_path.exists():
        return {"status": "exists", "vr_path": str(vr_path)}
    vr = _validate_vr(verification_result, "attach")
    raw = _sha256_bytes(json.dumps(vr, sort_keys=True, default=str).encode())
    _safe_write(vr_path, json.dumps({"__sha256": raw, "result": vr},
                                    ensure_ascii=False, sort_keys=True).encode())
    return {"status": "written", "vr_path": str(vr_path)}

def _load(d: Path, dictamen_id: str) -> Optional[Dict[str, Any]]:
    p = d / DICT_DIR / f"{dictamen_id}.json"
    if not p.exists():
        return None
    try:
        data, _ = _safe_read(p)
        rec = json.loads(data.decode())
    except Exception:
        return None
    # verify VR integrity when present
    vr_p = d / DICT_DIR / f"{dictamen_id}.vr.json"
    if not vr_p.exists():
        return None
    try:
        vr_data, _ = _safe_read(vr_p)
        vr_obj = json.loads(vr_data.decode())
        if not isinstance(vr_obj, dict):
            return None
        vr = vr_obj.get("result")
        if not isinstance(vr, dict) or not _validate_vr(vr, "load"):
            pass
        if _sha256_obj(vr) != vr_obj.get("__sha256"):
            return None
        if vr_obj.get("__sha256") != rec.get("verification_result_hash"):
            return None
    except Exception:
        return None
    try:
        _strict_obj(rec, _DICTAMEN_REQUIRED, _DICTAMEN_OPTIONAL, "load")
    except AuthorityError:
        return None
    return rec

def _authorize_locked(d: Path, *, investigation_id: str, artifact_sha256: str,
                   target_file: str = "comp.spv", domain: str = ""):
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        return None
    st = _read_state(d)
    if st["count"] < 0:
        return None
    raw = _read_registry_raw(d)
    digest = _jsonl_digest(raw)
    lines = [l for l in raw.splitlines() if l.strip()]
    if st.get("legacy"):
        # baseline: registry digests match "as-is" (migración de 1 dictamen histórico)
        if digest != st["digest"]:
            return None
    else:
        if st.get("digest") and digest != st["digest"]:
            return None  # rollback/truncación/sustitución detectada
        if st.get("count") >= 0 and len(lines) != st["count"]:
            return None
    for line in lines:
        try:
            cand = json.loads(line)
        except Exception:
            continue
        if not isinstance(cand, dict):
            continue
        if cand.get("investigation_id") != investigation_id:
            continue
        if cand.get("artifact_sha256") != artifact_sha256:
            continue
        if target_file and cand.get("target_file") != target_file:
            continue
        if domain and cand.get("domain") != domain:
            continue
        did = cand.get("dictamen_id")
        if not isinstance(did, str) or not _ID_RE.match(did):
            continue
        rec = _load(d, did)
        if rec is None:
            continue
        # re-derivar decisión con la VR almacenada
        vr_path = d / DICT_DIR / f"{did}.vr.json"
        vr_obj = json.loads(_safe_read(vr_path)[0].decode())
        vr = vr_obj.get("result")
        dec = ap.decide(vr, investigation_id=investigation_id,
                        artifact_sha256=artifact_sha256,
                        target_file=target_file, domain=cand.get("domain", domain))
        if dec.get("decision") != cand.get("decision"):
            return None
        if dec.get("accepted") != cand.get("accepted"):
            return None
        return rec
    return None

def authorize(investigation_id: str, artifact_sha256: str, target_file: str = "comp.spv",
              domain: str = "") -> Optional[Dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        return None
    d = _dir()
    with _with_lock(d):
        return _authorize_locked(d, investigation_id=investigation_id,
                                  artifact_sha256=artifact_sha256,
                                  target_file=target_file, domain=domain)

def require(investigation_id: str, artifact_sha256: str, target_file: str = "comp.spv",
            domain: str = "", reason: str = "promotion") -> Dict[str, Any]:
    rec = authorize(investigation_id, artifact_sha256, target_file, domain)
    if rec is None:
        raise AuthorityError(f"{reason}: sin dictamen válido o íntegro; promoción denegada")
    if not rec.get("accepted"):
        raise AuthorityError(f"{reason}: dictamen no autoriza aceptación ({rec.get('decision')})")
    return rec

def audit_registry() -> Dict[str, Any]:
    d = _dir()
    report = {"state": None, "records": [], "veredicto": "UNKNOWN"}
    try:
        st = _read_state(d)
        raw = _read_registry_raw(d)
        digest = _jsonl_digest(raw)
        lines = [l for l in raw.splitlines() if l.strip()]
        report["state"] = {"count": st.get("count"), "seq": st.get("seq"),
                           "legacy": st.get("legacy", False),
                           "stored_digest": st.get("digest"),
                           "actual_digest": digest,
                           "match": st.get("digest") == digest and st.get("count") == len(lines)}
        for l in lines:
            try:
                cand = json.loads(l)
                rec = _load(d, cand.get("dictamen_id", ""))
                report["records"].append({
                    "investigation_id": cand.get("investigation_id"),
                    "dictamen_id": cand.get("dictamen_id"),
                    "ok": rec is not None,
                    "accepted": cand.get("accepted"),
                })
            except Exception as e:
                report["records"].append({"error": str(e)[:120]})
        report["veredicto"] = "OK" if (report["state"]["match"] and all(r.get("ok") for r in report["records"])) else "COMPROMISED"
    except AuthorityError as e:
        report["veredicto"] = "REJECTED"
        report["error"] = str(e)
    return report

# ===================================================================-------
# Ledger de consumo — anti-replay, una operación una sola vez por defecto
# ===================================================================-------
LEDGER = "consumed.jsonl"
CONSUMERS = {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "GATE"}

def _read_ledger(d: Path) -> List[Dict[str, Any]]:
    p = d / LEDGER
    if not p.exists():
        return []
    data, _ = _safe_read(p, allow_empty=True)
    ents: List[Dict[str, Any]] = []
    prev_sha = ""
    for seq, raw_line in enumerate([l for l in data.splitlines() if l.strip()]):
        line = raw_line.strip()
        try:
            e = json.loads(line)
        except Exception:
            raise AuthorityError("consumed_ledger: entrada no parseable")
        if not isinstance(e, dict):
            raise AuthorityError("consumed_ledger: entrada no es dict")
        if seq > 0 and e.get("prev_hash") != prev_sha:
            raise AuthorityError("consumed_ledger: cadena de hashes rota (posible manipulación)")
        prev_sha = hashlib.sha256(line).hexdigest()
        ents.append(e)
    return ents

def _append_ledger(d: Path, entry: Dict[str, Any]) -> None:
    p = d / LEDGER
    ents = _read_ledger(d)
    prev_sha = hashlib.sha256(json.dumps(ents[-1], sort_keys=True).encode()).hexdigest() if ents else "0" * 64
    final = {"seq": len(ents) + 1, "prev_hash": prev_sha, **entry,
             "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())}
    line = json.dumps(final, sort_keys=True).encode() + b"\n"
    current = _read_registry_raw(d) if False else (p.read_bytes() if p.exists() else b"")
    _safe_write(p, current + line)

def audit_ledger() -> Dict[str, Any]:
    d = _dir()
    try:
        ents = _read_ledger(d)
        return {"veredicto": "OK", "entries": len(ents),
                "seq": [e.get("seq") for e in ents],
                "consumers": sorted({e.get("consumer") for e in ents})}
    except AuthorityError as e:
        return {"veredicto": "COMPROMISED", "error": str(e)}

def _consumption_id(d: Path, operation_id: str, investigation_id: str, consumer: str) -> str:
    base = f"{investigation_id}:{consumer}:{operation_id}"
    ents = _read_ledger(d)
    return f"cns_{hashlib.sha256(base.encode()).hexdigest()[:16]}_{len(ents)+1:06d}"

def authorize_and_consume(*, investigation_id: str, artifact_sha256: str,
                          target_file: str = "comp.spv", domain: str = "",
                          consumer: str, operation_id: str,
                          action: str = "consume",
                          single_use: bool = True,
                          idempotent: bool = True) -> Dict[str, Any]:
    """Contrato transaccional: valida dictamen + consume operación bajo un único flock.

    - Verifica la autoridad y consume en la misma sección crítica (sin TOCTOU).
    - Vincula: investigation_id + artifact_sha256 + domain + consumer + operation_id.
    - single_use=True por defecto; idempotent=True permite retry legítimo sobre MISMO contexto.
    - operation_id es REQUIRED; el llamador es responsable de un identificador estable y significativo.
    - Rechaza contexto alterado para el mismo operation_id.
    - Registra consumo o rechazo; nunca acepta promoción indirecta.
    """
    if consumer not in CONSUMERS:
        raise AuthorityError(f"consumer no reconocido: {consumer}")
    if not isinstance(operation_id, str) or not _ID_RE.match(operation_id):
        raise AuthorityError("operation_id inválido")
    if not _ID_RE.match(investigation_id):
        raise AuthorityError("investigation_id inválido")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
        raise AuthorityError("artifact_sha256 inválido")
    d = _dir()
    with _with_lock(d):
        # 1) re-resolver autoridad tal cual el gate la ve
        rec = _authorize_locked(d, investigation_id=investigation_id,
                                artifact_sha256=artifact_sha256,
                                target_file=target_file, domain=domain)
        context = {"investigation_id": investigation_id,
                   "artifact_sha256": artifact_sha256,
                   "target_file": target_file,
                   "domain": domain,
                   "consumer": consumer,
                   "operation_id": operation_id,
                   "action": action}
        if rec is None:
            _append_ledger(d, {**context, "outcome": "rejected", "reason": "no_valid_dictamen",
                              "accepted": False})
            raise AuthorityError(f"{consumer}/{operation_id}: promoción denegada (sin dictamen válido)")
        ents = _read_ledger(d)
        same_op = [e for e in ents if e.get("operation_id") == operation_id]
        if same_op:
            e0 = same_op[0]
            same_ctx = all(e0.get(k) == context[k] for k in
                           ("investigation_id", "artifact_sha256", "target_file", "domain", "consumer", "action"))
            if same_ctx and e0.get("outcome") == "consumed" and idempotent:
                return {"record": rec, "operation": context,
                        "consumption_id": e0.get("consumption_id"),
                        "idempotent_replay": True,
                        "records_match": e0.get("dictamen_id") == rec.get("dictamen_id")}
            raise AuthorityError(
                f"{consumer}/{operation_id}: operación ya consumida con contexto "
                f"{'idéntico' if same_ctx else 'distinto'}")
        cid = _consumption_id(d, operation_id, investigation_id, consumer)
        entry = {**context,
                 "outcome": "consumed",
                 "accepted": True,
                 "decision": rec.get("decision"),
                 "epistemic_status": rec.get("epistemic_status"),
                 "dictamen_id": rec.get("dictamen_id"),
                 "consumption_id": cid}
        _append_ledger(d, entry)
        return {"record": rec, "operation": context,
                "consumption_id": cid,
                "idempotent_replay": False,
                "records_match": True}

__all__ = list(globals().keys())
