"""RXRE-MISSION-388 — Extractor genérico de propiedades buffer-capacity.

Transforma un "bundle de evidencia" estructurado en un registro del contrato
M386. No contiene heurísticas específicas de C/libtiff.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.buffer_capacity_provenance_contract import build_minimal_record, validate_record


def _ref_str(r):
    if isinstance(r, str):
        return r
    if isinstance(r, dict):
        f = r.get("file", "?")
        ln = r.get("line")
        return f"{f}:{ln}" if ln is not None else str(f)
    return str(r)


def _refs(bundle, key):
    sub = (bundle.get(key) or {})
    r = sub.get("refs")
    if r is None:
        r = bundle.get("source_refs") or []
    return r


VALID_ORIGIN = ("ALLOC", "PARAM", "GLOBAL", "DERIVED", "UNKNOWN", "MULTIPLE")
VALID_OFFSET = ("CONSTANT", "VARIABLE", "UNKNOWN")
VALID_LENGTH = ("CONSTANT", "SYMBOLIC", "UNKNOWN")
VALID_ALIAS = ("PROVEN", "CANDIDATE", "AMBIGUOUS", "NONE", "UNKNOWN")
VALID_OWNERSHIP = ("OWNED", "TRANSFERRED", "SHARED", "UNKNOWN")
VALID_LIFETIME = ("DEMONSTRATED", "PARTIAL", "UNKNOWN")


def _state(evidence_bool, proven=False):
    if not evidence_bool:
        return "NOT_DETERMINED"
    return "PROVEN" if proven else "PARTIAL"


def extract(bundle):
    if not isinstance(bundle, dict):
        return None, ["bundle debe ser dict"]
    bid = bundle.get("buffer_id")
    if not bid:
        return None, ["buffer_id requerido"]

    source_refs = bundle.get("source_refs") or []
    method = bundle.get("method", "generic_extractor")
    conditions = bundle.get("conditions", "provided evidence")
    uncertainty = bundle.get("uncertainty", "as provided by bundle")
    origin_kind = (bundle.get("origin") or {}).get("kind", "UNKNOWN")
    if origin_kind not in VALID_ORIGIN:
        origin_kind = "UNKNOWN"

    oc = bundle.get("object_class", "UNKNOWN")
    if oc not in ("HEAP","STACK","GLOBAL","DERIVED","UNKNOWN"):
        oc = "UNKNOWN"
    rec = build_minimal_record(bid, origin_kind=origin_kind, object_class=oc,
                              parent_object_id=bundle.get("parent_object_id"))

    ident_ev = bool(source_refs) or bool((bundle.get("identity") or {}).get("evidence"))
    rec["properties"]["BUFFER_IDENTITY"] = {
        "state": _state(ident_ev, proven=False),
        "value": bid,
        "evidence_origin": ",".join(_ref_str(r) for r in source_refs) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in source_refs if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "identity by source location/name; not semantic memory identity (rule 10)",
    }

    origin_ev = bool((bundle.get("origin") or {}).get("evidence"))
    rec["properties"]["BUFFER_ORIGIN"] = {
        "state": _state(origin_ev, proven=False),
        "value": origin_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "origin")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "origin") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "origin classification from provided evidence; multiple origins possible",
    }

    base = bundle.get("base") or {}
    base_ev = bool(base.get("evidence"))
    rec["properties"]["BUFFER_BASE"] = {
        "state": _state(base_ev, proven=base.get('proven', False)),
        "value": base.get("value"),
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "base")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "base") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "base address requires execution/runtime evidence",
    }

    cap = bundle.get("capacity") or {}
    cap_ev = bool(cap.get("evidence"))
    rec["properties"]["BUFFER_CAPACITY"] = {
        "state": _state(cap_ev, proven=cap.get('proven', False)),
        "value": cap.get("value"),
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "capacity")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "capacity") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "capacity unknown != unlimited (rule 8)",
    }

    init = bundle.get("initialized_range") or {}
    init_ev = bool(init.get("evidence"))
    rec["properties"]["BUFFER_INITIALIZED_RANGE"] = {
        "state": _state(init_ev, proven=init.get('proven', False)),
        "value": init.get("value"),
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "initialized_range")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "initialized_range") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "assignment != initialization (rule 1)",
    }

    acc = bundle.get("accessible_range") or {}
    acc_ev = bool(acc.get("evidence"))
    rec["properties"]["BUFFER_ACCESSIBLE_RANGE"] = {
        "state": _state(acc_ev, proven=acc.get('proven', False)),
        "value": acc.get("value"),
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "accessible_range")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "accessible_range") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "accessible range != initialized range (rule 9)",
    }

    off = bundle.get("offset") or {}
    off_kind = off.get("kind", "UNKNOWN")
    if off_kind not in VALID_OFFSET:
        off_kind = "UNKNOWN"
    off_ev = bool(off.get("evidence"))
    off_value = off.get("value")
    if off_kind == "UNKNOWN" or not off_ev:
        off_value = None
    if off_kind == "CONSTANT" and off_ev and off_value is None:
        off_value = off.get("value", 0)
    rec["properties"]["BUFFER_OFFSET"] = {
        "state": _state(off_ev, proven=off.get('proven', False)),
        "value": off_value,
        "value_kind": off_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "offset")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "offset") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "offset unknown != 0 (rule 5)",
    }

    al = bundle.get("access_length") or {}
    al_kind = al.get("kind", "UNKNOWN")
    if al_kind not in VALID_LENGTH:
        al_kind = "UNKNOWN"
    al_ev = bool(al.get("evidence"))
    rec["properties"]["BUFFER_ACCESS_LENGTH"] = {
        "state": _state(al_ev, proven=al.get('proven', False)),
        "value": al.get("value") if al_ev else None,
        "value_kind": al_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "access_length")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "access_length") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "requested length != effective write (rule 7)",
    }

    alias = bundle.get("alias") or {}
    alias_kind = alias.get("kind", "UNKNOWN")
    if alias_kind not in VALID_ALIAS:
        alias_kind = "UNKNOWN"
    alias_ev = bool(alias.get("evidence"))
    alias_state = _state(alias_ev, proven=alias.get('proven', False))
    if alias_state == "PROVEN" and alias_kind in ("CANDIDATE", "AMBIGUOUS", "UNKNOWN"):
        alias_state = "PARTIAL"
    rec["properties"]["BUFFER_ALIAS_SET"] = {
        "state": alias_state,
        "value": alias_kind,
        "value_kind": alias_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "alias")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "alias") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "candidate alias != proven alias (rule 4)",
    }

    own = bundle.get("ownership") or {}
    own_kind = own.get("kind", "UNKNOWN")
    if own_kind not in VALID_OWNERSHIP:
        own_kind = "UNKNOWN"
    own_ev = bool(own.get("evidence"))
    rec["properties"]["BUFFER_OWNERSHIP"] = {
        "state": _state(own_ev, proven=own.get('proven', False)),
        "value": own_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "ownership")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "ownership") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "pointer param != ownership (rule 3)",
    }

    life = bundle.get("lifetime") or {}
    life_kind = life.get("kind", "UNKNOWN")
    if life_kind not in VALID_LIFETIME:
        life_kind = "UNKNOWN"
    life_ev = bool(life.get("evidence"))
    rec["properties"]["BUFFER_LIFETIME"] = {
        "state": _state(life_ev, proven=life.get('proven', False)),
        "value": life_kind,
        "evidence_origin": ",".join(_ref_str(r) for r in _refs(bundle, "lifetime")) or "none",
        "code_location": "; ".join(f"{r.get('file')}:{r.get('line')}" for r in _refs(bundle, "lifetime") if isinstance(r, dict)) or "unknown",
        "method": method, "conditions": conditions,
        "uncertainty": "no observed free != unlimited lifetime (rule 6)",
    }

    rec["origin_kind"] = origin_kind
    rec["affirmations"] = list(bundle.get("affirmations") or [])
    for a in rec["affirmations"]:
        if "class" not in a:
            a["class"] = "STRUCTURAL_FACT"
        if "state" not in a:
            a["state"] = "PARTIAL"
    rec["contradictions"] = list(bundle.get("contradictions") or [])

    # object_class evidence (M408): default UNKNOWN unless evidence provided
    oc_ev = bundle.get("object_class_evidence") or {}
    rec["object_class"] = oc
    rec["parent_object_id"] = bundle.get("parent_object_id")
    rec["object_class_evidence"] = {
        "state": oc_ev.get("state", "NOT_DETERMINED" if oc == "UNKNOWN" else "PARTIAL"),
        "evidence_origin": oc_ev.get("evidence_origin", ""),
        "code_location": oc_ev.get("code_location", ""),
        "method": oc_ev.get("method", bundle.get("method", "generic_extractor")),
        "conditions": oc_ev.get("conditions", bundle.get("conditions", "provided evidence")),
        "uncertainty": oc_ev.get("uncertainty", "class from provided evidence; no heuristic promotion"),
    }
    errors = validate_record(rec)
    return rec, errors


def extract_many(bundles):
    out = []
    for b in bundles:
        rec, errs = extract(b)
        out.append({"record": rec, "errors": errs})
    return out


__all__ = ["extract", "extract_many"]
