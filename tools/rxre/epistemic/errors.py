"""Errores del framework epistémico (fail-closed)."""
class EpistemicError(Exception):
    pass
class AdmissionError(EpistemicError):
    pass
class SealViolation(EpistemicError):
    pass
class PromotionDenied(EpistemicError):
    pass
