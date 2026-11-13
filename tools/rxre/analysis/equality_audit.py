"""M658 EQUALITY AUDIT acotado: dominios, falsos +/- y no-equivalencia."""
from __future__ import annotations

def eq_bytes(a: bytes, b: bytes):
    return {"equal": a==b, "domain":"bytes exact"}

def eq_struct(a: dict, b: dict):
    # igualdad estructural: mismos campos clave en ambos (no ignora campos)
    ka, kb = set(a), set(b)
    return {"equal": a==b, "fields": sorted(ka & kb), "missing": sorted(ka ^ kb)}

def eq_normalized(a, b, normalize):
    na, nb = normalize(a), normalize(b)
    return {"equal": na==nb, "naive": a==b, "norm": (na, nb)}

def eq_state(a: str, b: str):
    return {"equal": a==b, "implies_evidence_equal": False, "domain":"epistemic state"}

def eq_hash(sha_a: str, sha_b: str):
    return {"equal": sha_a==sha_b, "semantic": False, "domain":"hash artefacto"}
