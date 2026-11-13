"""M638 FOCI CAUSAL acotado: clasifica pérdidas sin promover incertidumbre."""
from __future__ import annotations

CAUSES = {"LOCAL_ANALYZER_LIMITATION","EXTERNAL_DEPENDENCY","INSUFFICIENT_EVIDENCE","AMBIGUOUS_STRUCTURE","INVALID_INPUT"}

def classify_loss(kind, evidence_ok, external, ambiguous, instrumental):
    if kind=="external_stub":
        return "EXTERNAL_DEPENDENCY"
    if kind=="limit_mega":
        if instrumental and evidence_ok:
            return "LOCAL_ANALYZER_LIMITATION"  # heurístico interno, corregible en teoría pero con riesgo
        return "AMBIGUOUS_STRUCTURE"
    if kind=="indirect_got":
        if external:
            return "EXTERNAL_DEPENDENCY"
        if ambiguous:
            return "AMBIGUOUS_STRUCTURE"
        return "INSUFFICIENT_EVIDENCE"
    if instrumental and not evidence_ok:
        return "INVALID_INPUT"
    return "INSUFFICIENT_EVIDENCE"

def recoverability(cause):
    if cause=="EXTERNAL_DEPENDENCY": return "NO"
    if cause=="LOCAL_ANALYZER_LIMITATION": return "YES"
    return "NOT_DETERMINED"
