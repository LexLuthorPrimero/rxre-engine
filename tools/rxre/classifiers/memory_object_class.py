"""RXRE-MISSION-408 — Clasificación genérica de clases de objetos de memoria.

Clasifica un objeto de memoria (HEAP/STACK/GLOBAL/DERIVED/UNKNOWN) a partir de
evidencia estructural (registro base, origen, etc.). La clasificación es una
inferencia semántica (PARTIAL), nunca PROVEN por sí sola. No contiene
heurísticas específicas de libtiff.
"""
from __future__ import annotations

STACK_REGS = {"rbp", "rsp", "ebp", "esp"}
PARAM_REGS = {"rdi", "rsi", "rdx", "rcx", "r8", "r9", "edi", "esi"}
DERIVED_INDICATORS = ("derived", "lea", "add", "sub")


def classify_from_base_register(base_reg, evidence=False):
    """Classify based on base register role. Returns (class, state, method)."""
    if not base_reg:
        return "UNKNOWN", "NOT_DETERMINED", "no base register"
    br = base_reg.lower()
    if br in STACK_REGS:
        return "STACK", "PARTIAL" if evidence else "NOT_DETERMINED", "register_role:stack"
    if br in PARAM_REGS:
        return "HEAP", "PARTIAL" if evidence else "NOT_DETERMINED", "register_role:param (heap candidate)"
    if br == "rip" or br == "":
        return "GLOBAL", "PARTIAL" if evidence else "NOT_DETERMINED", "register_role:rip/absolute"
    return "UNKNOWN", "NOT_DETERMINED", "register_role:unknown"


def classify_from_origin(origin_kind):
    """Classify based on origin kind."""
    ok = (origin_kind or "").upper()
    if ok in ("ALLOC", "MALLOC", "NEW"):
        return "HEAP"
    if ok in ("STACK", "FRAME", "LOCAL"):
        return "STACK"
    if ok in ("GLOBAL", "STATIC", "SYMBOL"):
        return "GLOBAL"
    if ok in ("DERIVED", "OFFSET", "SUBREGION"):
        return "DERIVED"
    return "UNKNOWN"


def combine_classifications(*classes):
    """Combine multiple classification suggestions. Prefer more specific over UNKNOWN."""
    priority = {"HEAP": 1, "STACK": 2, "GLOBAL": 3, "DERIVED": 4, "UNKNOWN": 5}
    # prefer non-UNKNOWN if any
    non_unknown = [c for c in classes if c and c != "UNKNOWN"]
    if not non_unknown:
        return "UNKNOWN"
    # if all agree, return that; else if conflict, UNKNOWN
    if len(set(non_unknown)) == 1:
        return non_unknown[0]
    return "UNKNOWN"


__all__ = ["classify_from_base_register", "classify_from_origin", "combine_classifications",
           "STACK_REGS", "PARAM_REGS"]
