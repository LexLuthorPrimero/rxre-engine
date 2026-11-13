"""Additive E2E pipeline for TYPED_EVENT_JSON (M433/M434 integration verification).
Reuses adapters.typed_event_adapter + schema validation. Does not modify
adapters.py logic (beyond additive adapter), schema.py, classifier.py, extractor.py.
Preserves epistemic separation; no promotions.
"""
from __future__ import annotations
import json, pathlib
from .adapters import typed_event_adapter
from .schema import validate_entity

def run_typed_event_e2e(typed_event_path, source_id=None, source_cert_hash=None):
    entities, adapter_msg = typed_event_adapter(typed_event_path, source_id=source_id, source_cert_hash=source_cert_hash)
    valid_n = 0; errors = []; rel_n = 0
    direct = inferred = 0; promotions = 0
    for e in entities:
        ok, msg = validate_entity(e)
        if ok: valid_n += 1
        else: errors.append((e.get("entity_id"), msg))
        rel_n += len(e.get("relations", []))
        obs = e.get("observation_type"); ep = e.get("epistemic_state")
        if obs == "DYNAMIC_OBSERVATION": direct += 1
        elif obs == "SEMANTIC_INFERENCE": inferred += 1
        # promotion check: candidates/inference must not become PROVEN
        is_candidate = "candidate" in (e.get("entity_id") or "") or str(e.get("extra",{}).get("m432_event_type","")).endswith("_CANDIDATE")
        if is_candidate and (ep == "PROVEN" or obs == "DETERMINISTIC"):
            promotions += 1
        for r in e.get("relations", []) or []:
            if r.get("epistemic") == "PROVEN" and obs == "SEMANTIC_INFERENCE":
                promotions += 1
    return {
        "adapter_msg": adapter_msg,
        "entities": entities,
        "counts": {"total": len(entities), "valid": valid_n, "errors": len(errors), "relations": rel_n,
                   "direct_observation": direct, "inference_candidate": inferred, "promotions": promotions},
        "validation_errors": errors,
        "epistemic_preservation": "PASS" if promotions == 0 else "FAIL",
    }
