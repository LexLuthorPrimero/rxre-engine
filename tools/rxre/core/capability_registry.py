#!/usr/bin/env python3
"""RXRE-M335 — REGISTRO DE CAPACIDADES EVIDENCE-DRIVEN (no sustituye contratos protegidos)."""
import sys, os, hashlib, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")

# Capacidad declarada vs ejecutada vs límite
CAPABILITIES = {
    "m322_claim_evaluator": {
        "id": "m322_claim_evaluator",
        "version": "1.0.0-M322",
        "declared": True,
        "executed": False,
        "question_class": "semantic_claim_evaluation",
        "preconditions": ["assertion_id", "claim_text", "evidence_refs", "claim_scope"],
        "requires_artifact": True,
        "requires_manifest": False,
        "requires_evidence_ref": True,
        "authorization_needed": False,
        "persistence_needed": False,
        "scope_covered": ["scope_327", "scope_323", "scope_326"],
        "limitations": ["DB_AUTH_ACTOR_M294 pending => contract M306 REJECTED at R4; semantic decision can be SUPPORTED but persistence BLOCKED"],
        "artifact_identity": "/home/lucas/Escritorio/rxre/tools/rxre/core/claim_evaluator.py",
        "provenance_contracts": ["evidence_claim_verification", "evidence_snapshot", "manifest_binding_contract", "scope_provenance_contract", "unified_verified_contract"],
        "status": "CAPABILITY_EXECUTED"  # verified by M323/M327
    },
    "m317_crypto_ref": {
        "id": "m317_crypto_ref",
        "version": "1.0.0-M317",
        "declared": True,
        "executed": True,
        "question_class": "crypto_identity_bound",
        "preconditions": ["artifact_path"],
        "requires_artifact": True,
        "requires_manifest": False,
        "authorization_needed": False,
        "persistence_needed": False,
        "scope_covered": ["scope_crypto_332"],
        "limitations": ["Only 3 RFC 8032 vectors + 50 random + adversarial; not universal; privilege independence INSUFFICIENT (DB_AUTH_ACTOR_M294)"],
        "artifact_identity": "/home/lucas/Escritorio/rxre/tools/rxre/prototype/m316/ed25519_ref.py",
        "provenance_contracts": ["ed25519_ref"],
        "status": "CAPABILITY_EXECUTED"
    },
    "m303_evidence_snapshot": {
        "id": "m303_evidence_snapshot",
        "version": "1.0.0-M303",
        "declared": True,
        "executed": True,
        "question_class": "evidence_integrity_capture",
        "preconditions": ["artifact_path", "manifest_path"],
        "requires_artifact": True,
        "requires_manifest": True,
        "authorization_needed": False,
        "persistence_needed": False,
        "scope_covered": ["scope_319", "scope_323", "scope_326", "scope_327"],
        "limitations": ["Capture only; does not prove authority; identity/open consistency documented"],
        "artifact_identity": "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_snapshot.py",
        "provenance_contracts": ["evidence_snapshot", "manifest_binding_contract"],
        "status": "CAPABILITY_EXECUTED"
    },
}

# Selector determinista (no inventa, no oculta)
def select_capability(question_text: str, evidence_refs: list = None, artifact_path: str = None,
                      manifest_path: str = None, claim_scope: str = None, authorization_available: bool = False):
    # Prioridad por evidencia real y precondiciones
    # Si hay manifest + artifact + claim_text => evaluador semántico
    if question_text and (evidence_refs or manifest_path) and artifact_path and os.path.isfile(artifact_path):
        # Verificar si el manifest tiene hash canónico (M325)
        try:
            if manifest_path and os.path.isfile(manifest_path):
                m = json.load(open(manifest_path, "r"))
                has_hash = bool(m.get("artefacto_hash_sha256") or m.get("hash_sha256") or m.get("artifact_hash_sha256"))
                if has_hash:
                    return {"selected":"m322_claim_evaluator", "status":"CAPABILITY_EXECUTED", "reason":"Evidence + manifest + claim available; semantic evaluation possible", "limitations":"Contract M306 may REJECT at R4 without DB_AUTH_ACTOR_M294"}
        except Exception:
            pass
        # Si hay claim pero sin manifest válido o sin evidencia resoluble
        if evidence_refs and any(os.path.isfile(str(r)) for r in evidence_refs if isinstance(r,str)):
            # Si hay referencias realistas pero manifest sin hash -> podría ser INSUFFICIENT
            if manifest_path and os.path.isfile(manifest_path):
                try:
                    m = json.load(open(manifest_path,"r"))
                    if not (m.get("artefacto_hash_sha256") or m.get("hash_sha256") or m.get("artifact_hash_sha256")):
                        return {"selected":"m322_claim_evaluator", "status":"CAPABILITY_EXECUTED", "reason":"Claim evaluator applies; evidence reference exists but manifest lacks canonical hash => INSUFFICIENT (M328 fix)", "limitations":"Evidence insufficient; no claim of VERIFIED"}
                except Exception:
                    pass
    # Si hay archivo de código Ed25519 -> crypto reference (no reemplaza evaluador)
    if artifact_path and os.path.isfile(artifact_path) and ("ed25519" in artifact_path or "ed25519_ref" in artifact_path):
        return {"selected":"m317_crypto_ref", "status":"CAPABILITY_EXECUTED", "reason":"Crypto reference artifact detected; use for identity/bound checks only", "limitations":"Not a semantic evaluator; does not resolve authorization"}
    # Si hay manifest + artifact pero sin claim -> evidencia capture
    if manifest_path and artifact_path and os.path.isfile(manifest_path) and os.path.isfile(artifact_path):
        return {"selected":"m303_evidence_snapshot", "status":"CAPABILITY_EXECUTED", "reason":"Evidence capture only; no claim to evaluate", "limitations":"No semantic conclusion without claim reference"}
    # Ninguna adecuada
    return {"selected":"NEEDS_CAPABILITY", "status":"NO_CAPABILITY_MATCH", "reason":"No executed capability matches the preconditions (missing claim/evidence/manifest/artifact identity)", "limitations":"Provide a valid claim with linked evidence or identify artifact for crypto reference", "suggestion":"Use claim_evaluator (M322) for semantic evaluation with manifest M325 + artifact; use ed25519_ref (M317) for crypto identity only"}

def registry_summary():
    return {"registered": len(CAPABILITIES), "executed": sum(1 for c in CAPABILITIES.values() if c["status"]=="CAPABILITY_EXECUTED"), "declared": sum(1 for c in CAPABILITIES.values() if c["declared"]), "authorization_needed": any(c["authorization_needed"] for c in CAPABILITIES.values()), "persistence_needed": any(c["persistence_needed"] for c in CAPABILITIES.values())}
