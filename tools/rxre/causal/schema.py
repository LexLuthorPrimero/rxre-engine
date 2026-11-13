"""M426 — Canonical evidence schema for RXRE.

Separates epistemic_state from execution_status.
Preserves full provenance: source_id, source_format, source_hash, source_locator,
adapter_version, normalization_version.
"""
from __future__ import annotations
import json, hashlib, pathlib

SCHEMA_VERSION = "1.0.0"
ADAPTER_VERSION = "1.0.0"

ENTITY_TYPES = {"FUNCTION", "BLOCK", "INSTRUCTION", "VARIABLE", "RESULT", "EFFECT", "TRANSFORM", "STATE"}
OBSERVATION_TYPES = {"STRUCTURAL_FACT", "DYNAMIC_OBSERVATION", "SEMANTIC_INFERENCE", "CAUSAL_ATTRIBUTION", "NOT_OBSERVED"}
EPISTEMIC_STATES = {"PROVEN", "PARTIAL", "INSUFFICIENT", "NOT_DETERMINED", "NOT_APPLICABLE"}
EXECUTION_STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED"}


def make_entity(entity_id, entity_type, source_id, source_format, source_hash,
                source_locator, observation_type, epistemic_state, execution_status,
                evidence_refs=None, premises=None, relations=None, extra=None):
    """Create a canonical entity with full provenance."""
    e = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "source_id": source_id,
        "source_format": source_format,
        "source_hash": source_hash,
        "source_locator": source_locator,
        "adapter_version": ADAPTER_VERSION,
        "normalization_version": SCHEMA_VERSION,
        "observation_type": observation_type,
        "epistemic_state": epistemic_state,
        "execution_status": execution_status,
        "evidence_refs": evidence_refs or [],
        "premises": premises or [],
        "relations": relations or [],
    }
    if extra:
        e.update(extra)
    return e


def validate_entity(e):
    """Validate that an entity has all required fields."""
    required = ["entity_id", "entity_type", "source_id", "source_format",
                "source_hash", "source_locator", "adapter_version",
                "normalization_version", "observation_type", "epistemic_state",
                "execution_status", "evidence_refs", "premises", "relations"]
    for field in required:
        if field not in e:
            return False, f"missing field: {field}"
    if e["entity_type"] not in ENTITY_TYPES:
        return False, f"invalid entity_type: {e['entity_type']}"
    if e["observation_type"] not in OBSERVATION_TYPES:
        return False, f"invalid observation_type: {e['observation_type']}"
    if e["epistemic_state"] not in EPISTEMIC_STATES:
        return False, f"invalid epistemic_state: {e['epistemic_state']}"
    if e["execution_status"] not in EXECUTION_STATUSES:
        return False, f"invalid execution_status: {e['execution_status']}"
    return True, "ok"


def make_relation(from_id, to_id, relation_type, obs_type, epistemic, evidence_refs=None, premises=None):
    return {
        "from": from_id,
        "to": to_id,
        "type": relation_type,
        "obs_type": obs_type,
        "epistemic": epistemic,
        "evidence_refs": evidence_refs or [],
        "premises": premises or [],
    }
