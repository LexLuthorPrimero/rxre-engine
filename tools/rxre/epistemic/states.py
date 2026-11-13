"""Estados epistemológicos canónicos y reglas de separación."""
from __future__ import annotations
from enum import Enum

class EpistemicState(str, Enum):
    PROVEN = "PROVEN"
    PARTIAL = "PARTIAL"
    NOT_DETERMINED = "NOT_DETERMINED"
    BLOCKED = "BLOCKED"
    ABSTAINED = "ABSTAINED"

class AcceptanceDecision(str, Enum):
    ACCEPT_WITH_DOMAIN = "ACCEPT_WITH_DOMAIN"
    ACCEPT_LIMITED = "ACCEPT_LIMITED"
    WITHHOLD = "WITHHOLD"
    DETACH = "DETACH"
    ABSTAIN = "ABSTAIN"
    REJECT = "REJECT"

class SealPhase(str, Enum):
    CREATED = "CREATED"
    PREDICTING = "PREDICTING"
    SEALED = "SEALED"
    EVIDENCE_RELEASED = "EVIDENCE_RELEASED"
    VERIFYING = "VERIFYING"
    REVEALED = "REVEALED"

# Regla de separación: estado epistémico ≠ estado de ejecución ≠ estado experimental.
# Ningún estado se promueve sin evidencia independiente (fail-closed).
SEPARATION_RULE = "Epistemic, execution and experimental states are distinct domains; no promotion without independent evidence."
