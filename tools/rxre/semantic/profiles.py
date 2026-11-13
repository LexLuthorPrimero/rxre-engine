#!/usr/bin/env python3
"""Experimental profiles — per-binary-hash, provenance-bound, fail-closed.

A profile applies ONLY when the analyzed binary's SHA-256 equals the sealed
`binary_sha256` inside the profile JSON. Historical observations tied to the
author's ls/grep hosts NEVER leak into an unrelated binary: hash mismatch or
missing profile => CONDITION_UNKNOWN for every callsite.

Profiles carry: reachability observations (M262/M263 GDB), experiment metadata
(causal), observability-blocked callsites (M268) and the experiment ids that
confer a strong causal reading. They are archival evidence, not rules.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

_PROFILE_DIR = Path(__file__).resolve().parent / "experimental_profiles"
_cache: dict | None = None

def _hash_of(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None

def load_profiles() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        for p in sorted(_PROFILE_DIR.glob("*.json")):
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            sha = str(d.get("binary_sha256") or "").lower()
            if len(sha) == 64:
                _cache[sha] = d
    return _cache

def load_profile_for(binary_path: str):
    """(profile, binary_sha256|None) — profile is None unless the hash matches a sealed profile."""
    bsha = _hash_of(binary_path) if binary_path else None
    if not bsha:
        return None, None
    return load_profiles().get(bsha.lower()), bsha.lower()

def lookup_reachability(profile, cs_hex: str, target_symbol):
    key = f"{cs_hex}|{target_symbol}" if target_symbol else f"{cs_hex}|"
    if profile:
        v = profile.get("reachability", {}).get(key)
        if isinstance(v, dict):
            return v
    return {"r": "CONDITION_UNKNOWN", "e": None}

_DEFAULT_CAUSAL = dict(input_conditions=[], branch_predicates=[], state_dependencies=[],
                       memory_dependencies=[],
                       causal_chain=["sin experimento discriminante en el dominio probado (o sin perfil experimental aplicable)"])

def causal_entry(profile, experiment_id):
    if not profile:
        d = dict(_DEFAULT_CAUSAL)
        d["causal_chain"] = ["sin perfil experimental aplicable a este binario — análisis genérico, sin conocimiento histórico"]
        return d
    if not experiment_id:
        return dict(_DEFAULT_CAUSAL)
    d = profile.get("causal", {}).get(experiment_id)
    return d if isinstance(d, dict) else dict(_DEFAULT_CAUSAL)
