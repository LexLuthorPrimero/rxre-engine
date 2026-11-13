"""Framework de gobernanza epistémica (librería independiente, stdlib)."""
from __future__ import annotations
from .states import EpistemicState, AcceptanceDecision, SealPhase
from .promotion import guard_promotion
from .sealing import seal_prediction, validate_seal_before_reveal
from .admission import admit_claim, AdmitResult
from .coordination import prepare, record_effect, confirm, reconcile
from .anti_replay import authorize_and_consume, audit_ledger
from .evidence import EvidenceBundle, EvidenceRef
from .errors import EpistemicError, AdmissionError, SealViolation, PromotionDenied

__all__ = [
    "EpistemicState", "AcceptanceDecision", "SealPhase",
    "guard_promotion", "seal_prediction", "validate_seal_before_reveal",
    "admit_claim", "AdmitResult",
    "prepare", "record_effect", "confirm", "reconcile",
    "authorize_and_consume", "audit_ledger",
    "EvidenceBundle", "EvidenceRef",
    "EpistemicError", "AdmissionError", "SealViolation", "PromotionDenied",
]

__version__ = "0.1.0"
