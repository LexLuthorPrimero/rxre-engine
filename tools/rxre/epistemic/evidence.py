"""Bundle de evidencia con procedencia (stdlib)."""
from __future__ import annotations
import hashlib, json

class EvidenceRef:
    def __init__(self, artifact_sha256: str, locator: str = ""):
        if not isinstance(artifact_sha256, str) or not artifact_sha256:
            raise ValueError("artifact_sha256 requerido")
        self.artifact_sha256 = artifact_sha256
        self.locator = locator

class EvidenceBundle:
    def __init__(self, evidence_refs=None, scope_provenance: str = "UNKNOWN", verification_ref: str = ""):
        self.evidence_refs = list(evidence_refs or [])
        self.scope_provenance = scope_provenance
        self.verification_ref = verification_ref

def canonical_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()
