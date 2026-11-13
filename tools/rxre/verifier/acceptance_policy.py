#!/usr/bin/env python3
"""RXRE — Política de aceptación epistemológica (governance layer).

Centraliza la decisión de promoción de conclusiones de investigación a partir
de un VerificationResult producido por tools/rxre/verifier/.

REGLA CENTRAL: el investigador propone; la verificación contrasta; esta política gobierna.
Ningún componente puede aprobarse a sí mismo. Una coincidencia no se promueve sola.
"""
from __future__ import annotations
import json, os, time, hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ACCEPT_WITH_DOMAIN = "ACCEPT_WITH_DOMAIN"   # PROVEN acotado al dominio
ACCEPT_LIMITED = "ACCEPT_LIMITED"          # PARTIAL con límites
WITHHOLD = "WITHHOLD"                      # NOT_DETERMINED
DETACH = "DETACH"                          # BLOCKED
ABSTAIN = "ABSTAIN"                         # ABSTAINED
REJECT = "REJECT"                          # integridad/identidad/aspecto desconocido

_MAP = {
    "PROVEN": ACCEPT_WITH_DOMAIN,
    "PARTIAL": ACCEPT_LIMITED,
    "NOT_DETERMINED": WITHHOLD,
    "BLOCKED": DETACH,
    "ABSTAINED": ABSTAIN,
}

class PromotionDenied(Exception):
    pass

@dataclass
class PromotionDecision:
    investigation_id: str
    artifact_sha256: str
    target_file: str
    domain: str
    epistemic_status: str
    decision: str
    accepted: bool
    detail: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)

def _require_str(d, k):
    v = d.get(k)
    return v if isinstance(v, str) and v else None

def _norm_vr(verification_result):
    """VerificationResult dataclass o dict -> dict normalizado."""
    if verification_result is None:
        return None
    to = getattr(verification_result, "__dict__", None)
    d = to if isinstance(to, dict) else None
    if d is None:
        d = dict(verification_result) if hasattr(verification_result, "keys") else None
    if d is None:
        return None
    return d

def decide(verification_result, *, investigation_id: str, artifact_sha256: str,
           target_file: str, domain: str) -> Dict[str, Any]:
    """Decisión pura (sin efectos). Fail-closed: cualquier anomalía -> REJECT."""
    vr = _norm_vr(verification_result)
    if vr is None:
        return {"decision": REJECT, "accepted": False, "reason": "verification_result ausente o malformado"}
    if not domain or not isinstance(domain, str):
        return {"decision": REJECT, "accepted": False, "reason": "dominio experimental ausente o vacío"}
    es = _require_str(vr, "execution_status")
    ep = _require_str(vr, "epistemic_status")
    if es != "OK":
        d = DETACH if es == "BLOCKED" else REJECT
        return {"decision": d, "accepted": False,
                "reason": f"ejecución no OK ({es}); detención de promoción"}
    if ep not in _MAP:
        return {"decision": REJECT, "accepted": False, "reason": f"estado epistemológico desconocido: {ep}"}
    integ = (vr.get("integrity") or {})
    post = (integ.get("post_run") or {})
    if not post.get("ok"):
        return {"decision": REJECT, "accepted": False, "reason": "integridad del paquete comprometida post-run"}
    audit = vr.get("session_audit") or {}
    if not audit.get("seal_before_reveal"):
        return {"decision": REJECT, "accepted": False, "reason": "la predicción no se selló antes de revelar resultados"}
    if not audit.get("forbidden_clean"):
        return {"decision": REJECT, "accepted": False, "reason": "referencias prohibidas detectadas en el verificador"}
    # vinculación investigación <-> verificación por hash de artefacto
    hashes = ((post.get("hashes") or {}))
    bound = hashes.get(target_file) if target_file else None
    if bound is None or bound != artifact_sha256:
        return {"decision": REJECT, "accepted": False,
                "reason": "el dictamen no corresponde a este artefacto/investigación"}
    verdict = vr.get("verdict") or {}
    limits = list(verdict.get("limitations") or []) + list(vr.get("limitations") or [])
    # regla: un PARTIAL sin limitaciones no puede aceptar; downgrade a WITHHOLD
    if ep == "PARTIAL" and not limits:
        return {"decision": WITHHOLD, "accepted": False,
                "reason": "PARTIAL sin limitaciones persistidas; no promovible",
                "epistemic_status": ep}
    dec = _MAP[ep]
    accepted = dec in (ACCEPT_WITH_DOMAIN, ACCEPT_LIMITED)
    reason = {"PROVEN": "aceptado en el dominio demostrado",
              "PARTIAL": "aceptado con alcance y limitaciones; no escalar a PROVEN",
              "NOT_DETERMINED": "evidencia insuficiente; no promover",
              "BLOCKED": "bloqueo registrado; promoción detenida",
              "ABSTAINED": "el verificador se abstuvo; sin conclusión"}[ep]
    return {"decision": dec, "accepted": accepted, "reason": reason,
            "epistemic_status": ep, "limitations": limits, "domain": domain}

def guard_promotion(*, investigation_id: str, artifact_sha256: str, target_file: str,
                    domain: str, verification_result,
                    persist_to: Optional[str] = None,
                    investigation_artifact: Optional[str] = None) -> PromotionDecision:
    """Gate de promoción fail-closed. Opcionalmente persiste el dictamen.

    - Rechaza: resultado ausente/malformado, estado desconocido, integrity comprometida,
      seal no previo, refs prohibidas, vinculación de artefacto fallida.
    - Vincula persistentemente la decisión a la investigación (investigation_id + hash).
    """
    if investigation_artifact and sha256_like(investigation_artifact) != artifact_sha256:
        dec = PromotionDecision(investigation_id, artifact_sha256, target_file, domain,
                                "BLOCKED", REJECT, False,
                                detail={"reason": "artefacto de investigación no coincide con hash sellado"})
        _persist(persist_to, dec)
        return dec
    d = decide(verification_result, investigation_id=investigation_id,
               artifact_sha256=artifact_sha256, target_file=target_file, domain=domain)
    dec = PromotionDecision(investigation_id=investigation_id, artifact_sha256=artifact_sha256,
                            target_file=target_file, domain=domain,
                            epistemic_status=d.get("epistemic_status", "BLOCKED"),
                            decision=d["decision"], accepted=d.get("accepted", False),
                            detail=d, limitations=d.get("limitations", []))
    _persist(persist_to, dec)
    return dec

def sha256_like(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()

def _persist(persist_to: Optional[str], dec: PromotionDecision):
    if not persist_to:
        return
    os.makedirs(os.path.dirname(persist_to) or ".", exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "investigation_id": dec.investigation_id,
           "artifact_sha256": dec.artifact_sha256, "target_file": dec.target_file,
           "domain": dec.domain, "epistemic_status": dec.epistemic_status,
           "decision": dec.decision, "accepted": dec.accepted,
           "limitations": dec.limitations, "detail": dec.detail}
    with open(persist_to, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def require_promotion(**kwargs) -> PromotionDecision:
    """Igual que guard_promotion pero lanza PromotionDenied si no se acepta."""
    dec = guard_promotion(**kwargs)
    if not dec.accepted:
        raise PromotionDenied(f"promotion denied: {dec.decision} - {dec.detail.get('reason')}")
    return dec
