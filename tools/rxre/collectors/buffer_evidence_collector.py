"""RXRE-MISSION-389 — Recolector automático genérico de evidencia de buffers.

Consume artefactos existentes (resultados de análisis, referencias fuente,
símbolos, etc.) y produce un "bundle" estructurado consumible por el extractor
M388 y el contrato M386. No decide si una propiedad está demostrada: sólo
recopila hechos verificables con procedencia. No contiene heurísticas
específicas de C/libtiff.
"""
from __future__ import annotations
import sys, hashlib, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

# Property hints supported (map to M386 properties)
PROPERTY_HINTS = {
    "BUFFER_IDENTITY", "BUFFER_ORIGIN", "BUFFER_BASE", "BUFFER_CAPACITY",
    "BUFFER_INITIALIZED_RANGE", "BUFFER_ACCESSIBLE_RANGE", "BUFFER_OFFSET",
    "BUFFER_ACCESS_LENGTH", "BUFFER_ALIAS_SET", "BUFFER_OWNERSHIP",
    "BUFFER_LIFETIME",
}

REQUIRED_OBS_FIELDS = ("obs_id", "source_artifact", "kind", "property_hint")


def _valid_obs(obs):
    if not isinstance(obs, dict):
        return False, "observation must be dict"
    for f in REQUIRED_OBS_FIELDS:
        if f not in obs or not obs.get(f):
            return False, f"missing field {f}"
    if obs["property_hint"] not in PROPERTY_HINTS and obs["property_hint"] != "NONE":
        return False, f"unknown property_hint {obs['property_hint']}"
    return True, None


def _obs_to_evidence_flag(obs_list):
    """An observation with a property_hint counts as evidence for that property."""
    return len(obs_list) > 0


def _detect_contradictions(obs_by_prop):
    contras = []
    for prop, obs in obs_by_prop.items():
        # group by quantity to avoid false contradictions across different kinds
        by_qty = {}
        for o in obs:
            q = o.get("quantity", "default")
            by_qty.setdefault(q, []).append(o)
        for q, grp in by_qty.items():
            values = set()
            for o in grp:
                v = o.get("value")
                if v is not None:
                    values.add(repr(v))
            if len(values) > 1:
                contras.append({
                    "property": prop,
                    "quantity": q,
                    "sources": [o.get("source_artifact") for o in grp],
                    "values": sorted(values),
                    "note": "contradictory values within same quantity; not resolved automatically",
                })
    return contras


def collect(observations, target_buffer_id, source_refs=None, method="generic_collector", contradictions=None, object_class="UNKNOWN", parent_object_id=None):
    """Agrega observaciones en un bundle M388.

    observations: list of dicts (each validated).
    target_buffer_id: str
    source_refs: list of {file,line,function} (provenance base)
    Returns (bundle, errors, stats).
    """
    errors = []
    # validate observations
    valid_obs = []
    for i, o in enumerate(observations or []):
        ok, err = _valid_obs(o)
        if not ok:
            errors.append(f"obs[{i}]: {err}")
            continue
        valid_obs.append(o)

    source_refs = source_refs or []
    # group by property hint
    by_prop = {p: [] for p in PROPERTY_HINTS}
    for o in valid_obs:
        ph = o["property_hint"]
        if ph in by_prop:
            by_prop[ph].append(o)

    contras = _detect_contradictions(by_prop)
    if contradictions:
        for c in contradictions:
            if c not in contras:
                contras.append(c)

    # Build bundle. Evidence flags derived from presence of observations.
    def refs_for(prop):
        out = []
        for o in by_prop.get(prop, []):
            out.append({"file": o.get("source_artifact", "?"),
                        "line": o.get("location", {}).get("line"),
                        "function": o.get("location", {}).get("function")})
        # add base source_refs if present and no specific
        if not out and source_refs:
            out = list(source_refs)
        return out

    def kind_from_obs(prop, default):
        # if multiple observations, prefer... keep default unless single consistent value
        obs = by_prop.get(prop, [])
        if not obs:
            return default
        kinds = {o.get("value_kind") for o in obs if o.get("value_kind")}
        if len(kinds) == 1:
            return kinds.pop()
        return default

    bundle = {
        "buffer_id": target_buffer_id,
        "object_class": object_class if object_class in ("HEAP","STACK","GLOBAL","DERIVED","UNKNOWN") else "UNKNOWN",
        "parent_object_id": parent_object_id,
        "source_refs": source_refs,
        "method": method,
        "conditions": "collected from provided artifacts; no execution",
        "uncertainty": "as collected; demonstration decided by M388/contract",
        "origin": {
            "kind": kind_from_obs("BUFFER_ORIGIN", "UNKNOWN"),
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_ORIGIN"]),
            "refs": refs_for("BUFFER_ORIGIN"),
        },
        "identity": {"evidence": _obs_to_evidence_flag(by_prop["BUFFER_IDENTITY"])},
        "base": {"evidence": _obs_to_evidence_flag(by_prop["BUFFER_BASE"]),
                 "value": None},
        "capacity": {"evidence": _obs_to_evidence_flag(by_prop["BUFFER_CAPACITY"]),
                      "value": None},
        "initialized_range": {"evidence": _obs_to_evidence_flag(by_prop["BUFFER_INITIALIZED_RANGE"])},
        "accessible_range": {"evidence": _obs_to_evidence_flag(by_prop["BUFFER_ACCESSIBLE_RANGE"])},
        "offset": {
            "kind": kind_from_obs("BUFFER_OFFSET", "UNKNOWN"),
            "value": None,
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_OFFSET"]),
            "refs": refs_for("BUFFER_OFFSET"),
        },
        "access_length": {
            "kind": kind_from_obs("BUFFER_ACCESS_LENGTH", "UNKNOWN"),
            "value": None,
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_ACCESS_LENGTH"]),
            "refs": refs_for("BUFFER_ACCESS_LENGTH"),
        },
        "alias": {
            "kind": kind_from_obs("BUFFER_ALIAS_SET", "UNKNOWN"),
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_ALIAS_SET"]),
            "refs": refs_for("BUFFER_ALIAS_SET"),
        },
        "ownership": {
            "kind": kind_from_obs("BUFFER_OWNERSHIP", "UNKNOWN"),
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_OWNERSHIP"]),
            "refs": refs_for("BUFFER_OWNERSHIP"),
        },
        "lifetime": {
            "kind": kind_from_obs("BUFFER_LIFETIME", "UNKNOWN"),
            "evidence": _obs_to_evidence_flag(by_prop["BUFFER_LIFETIME"]),
            "refs": refs_for("BUFFER_LIFETIME"),
        },
        "affirmations": [],
        "contradictions": contras,
        "object_class_evidence": {"state": "NOT_DETERMINED" if object_class == "UNKNOWN" else "PARTIAL",
                                 "evidence_origin": "", "method": method},
        "_observations": valid_obs,
        "_stats": {
            "n_observations": len(valid_obs),
            "n_rejected": len(observations or []) - len(valid_obs),
            "n_contradictions": len(contras),
            "properties_with_evidence": [p for p in PROPERTY_HINTS if by_prop[p]],
        },
    }

    # propagate value if single consistent value present in observations
    for prop in PROPERTY_HINTS:
        vals = {o.get("value") for o in by_prop[prop] if o.get("value") is not None}
        if len(vals) == 1:
            v = vals.pop()
            # map to bundle field
            field = prop.replace("BUFFER_", "").lower()
            # handle special names
            pass
    # set offset/access_length value if a single quantity has a single value
    for prop, bkey in (("BUFFER_OFFSET", "offset"), ("BUFFER_ACCESS_LENGTH", "access_length")):
        obs = by_prop[prop]
        by_qty = {}
        for o in obs:
            by_qty.setdefault(o.get("quantity", "default"), []).append(o)
        # prefer a quantity with proven observations and single value
        chosen_val = None
        chosen_qty = None
        for q, grp in by_qty.items():
            if not any(o.get("proven") for o in grp):
                continue
            vals = {o.get("value") for o in grp if o.get("value") is not None}
            if len(vals) == 1:
                chosen_val = vals.pop()
                chosen_qty = q
                break
        if chosen_val is None:
            for q, grp in by_qty.items():
                vals = {o.get("value") for o in grp if o.get("value") is not None}
                if len(vals) == 1:
                    chosen_val = vals.pop()
                    chosen_qty = q
                    break
        if chosen_val is not None and bundle[bkey].get("evidence"):
            bundle[bkey]["value"] = chosen_val
            bundle[bkey]["value_quantity"] = chosen_qty
        # proven flag: True if any obs in any quantity is proven
        if by_prop[prop] and any(o.get("proven") for o in by_prop[prop]):
            bundle[bkey]["proven"] = True

    # alias proven flag
    if by_prop["BUFFER_ALIAS_SET"] and any(o.get("proven") for o in by_prop["BUFFER_ALIAS_SET"]):
        bundle["alias"]["proven"] = True
    # origin proven flag
    if by_prop["BUFFER_ORIGIN"] and any(o.get("proven") for o in by_prop["BUFFER_ORIGIN"]):
        bundle["origin"]["proven"] = True

    return bundle, errors


def collect_many(targets, observations_by_target, **kw):
    out = []
    for t in targets:
        obs = observations_by_target.get(t, [])
        bundle, errs = collect(obs, t, **kw)
        out.append({"target": t, "bundle": bundle, "errors": errs})
    return out


__all__ = ["collect", "collect_many", "PROPERTY_HINTS", "REQUIRED_OBS_FIELDS"]
