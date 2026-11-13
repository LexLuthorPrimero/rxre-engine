#!/usr/bin/env python3
"""VALIDACIÓN DE INTEGRIDAD DE EVIDENCIA RXRE.
Verifica que evidencia E2E/E2 coincide con artefacto real y esquema válido.
No modifica evidencia canónica; solo lee.
"""
import hashlib, json, sys, re
from pathlib import Path

VALID_EPISTEMIC = {"PROVEN", "PARTIAL", "NOT_DETERMINED", "PROVEN_ABSENT", "DEFERRED", "INVALIDATED", "OBSERVED", "VALID"}
REQUIRED_E2E = {"e2e_id", "artefacto_path", "artefacto_size_bytes", "artefacto_hash_sha256", "epistemic", "procedencia"}
REQUIRED_E2E2 = {"e2e_id", "parent_e2e", "tipo", "artefacto", "hash_sha256", "artefacto_size_bytes", "epistemic", "procedencia"}

def accept_evidence(ev_path: str, art_path: str = None) -> dict:
    """GATE DE EVIDENCIA — rechaza antes de aceptar; no destruye evidencia previa."""
    res = validate_evidence_path(ev_path, art_path)
    if res["ok"]:
        return {"status": "accepted", "evidence_path": ev_path, "checks": res["checks"], "errors": []}
    else:
        return {"status": "rejected", "evidence_path": ev_path, "checks": res["checks"], "errors": res["errors"], "note": "No se persistió; evidencia previa preservada"}


_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

def validate_evidence_path(ev_path: str, art_path: str = None) -> dict:
    """Gate de evidencia — unas condiciones OBJETO verificables; ausencia ≠ validez.

    Rechaza cualquier evidencia donde la presencia de claves no garantiza identidad:
    - artefacto_path/artefacto vacío o faltante
    - artefacto inexistente
    - artefacto_hash_sha256 / hash_sha256 vacío o con formato distinto de 64-hex
    - artefacto_size_bytes/bytes ausente, <=0 o no coincidente
    - epistemética no VALID_EPISTEMIC
    - procedencia o e2e_id vacíos/espazados
    - (si art_path de solicitado se suministra) correspondencia artefacto solicitado ↔ evidencia
    """
    result = {"ok": False, "path": ev_path, "checks": {}, "errors": []}
    try:
        ev_path_obj = Path(ev_path)
        if not ev_path_obj.exists():
            result["errors"].append("evidence_path_missing")
            return result
        meta = json.loads(ev_path_obj.read_text())
        if not isinstance(meta, dict):
            result["errors"].append("evidence_not_object")
            return result
        result["checks"]["json_valid"] = True

        # Schema check based on known keys (must carry identifiers, not just keys)
        if "parent_e2e" in meta:
            required = REQUIRED_E2E2
        else:
            required = REQUIRED_E2E
        missing = sorted(required - meta.keys())
        result["checks"]["required_keys"] = len(missing) == 0
        if missing:
            result["errors"].append(f"missing_keys: {missing}")

        e2e_id = meta.get("e2e_id") or ""
        if not isinstance(e2e_id, str) or not e2e_id.strip().startswith("e2e_"):
            result["errors"].append(f"invalid_e2e_id: {e2e_id!r}")

        procedencia = meta.get("procedencia")
        if not isinstance(procedencia, str) or not procedencia.strip():
            result["errors"].append("missing_procedencia")

        # Epistemic validity
        ep = meta.get("epistemic")
        result["checks"]["epistemic_valid"] = ep in VALID_EPISTEMIC
        if ep not in VALID_EPISTEMIC:
            result["errors"].append(f"invalid_epistemic: {ep}")

        # Artefacto declarado en evidencia: obligatorio no vacío y resoluble
        declared_artifact = (meta.get("artefacto_path") or meta.get("artefacto") or "") if isinstance(meta, dict) else ""
        if not isinstance(declared_artifact, str) or not declared_artifact.strip():
            result["errors"].append("empty_artifact_path")
            declared_artifact = None

        # Size binding
        expected_size = meta.get("artefacto_size_bytes")
        if expected_size is None:
            result["errors"].append("size_missing")
        elif not isinstance(expected_size, int) or expected_size <= 0:
            result["errors"].append(f"size_not_positive: {expected_size!r}")

        # Hash binding — strict 64-hex, vacío no equivale a "no comprobado"
        expected_hash = (meta.get("artefacto_hash_sha256") or meta.get("hash_sha256") or "").strip().lower()
        if not expected_hash:
            result["errors"].append("hash_missing")
        elif not _HASH_RE.match(expected_hash):
            result["errors"].append(f"hash_format_invalid: {expected_hash[:16]}…")

        # Correspondencia solicitado ↔ evidencia (si pasa art_path)
        if art_path is not None:
            try:
                req_abs = str(Path(art_path).resolve())
                tgt = Path(declared_artifact) if declared_artifact else None
                dec_abs = str(tgt.resolve()) if tgt else None
                both_exist = bool(tgt and tgt.exists() and Path(art_path).exists())
                same = (tgt.resolve() == Path(art_path).resolve()) if both_exist else (dec_abs == req_abs if (dec_abs and req_abs) else None)
                if same is True:
                    result["checks"]["artifact_binding"] = True
                elif same is False:
                    result["errors"].append("evidence_target_mismatch")
                    result["checks"]["artifact_binding"] = False
                else:
                    result["errors"].append("evidence_target_unverifiable")
            except Exception:
                result["errors"].append("evidence_target_mismatch")
                result["checks"]["artifact_binding"] = False

        # Artifact existence + real size + real hash
        if art_path is None:
            art_path = declared_artifact
        if art_path:
            art = Path(art_path)
            if not art.exists():
                result["errors"].append(f"artifact_missing: {art_path}")
            else:
                result["checks"]["artifact_exists"] = True
                art_size = art.stat().st_size
                if isinstance(expected_size, int) and expected_size > 0:
                    result["checks"]["size_matches"] = (expected_size == art_size)
                    if expected_size != art_size:
                        result["errors"].append(f"size_mismatch: expected={expected_size}, actual={art_size}")
                if expected_hash and _HASH_RE.match(expected_hash):
                    h = hashlib.sha256(art.read_bytes()).hexdigest()
                    result["checks"]["hash_matches"] = h == expected_hash
                    if h != expected_hash:
                        result["errors"].append(f"hash_mismatch: expected={expected_hash[:16]}, actual={h[:16]}")
        else:
            result["checks"]["artifact_path_known"] = False
            result["errors"].append("artifact_path_unknown")

        result["ok"] = len(result["errors"]) == 0
    except Exception as exc:
        result["errors"].append(f"exception: {type(exc).__name__}: {exc}")
    return result
