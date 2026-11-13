"""M426 — Epistemic classifier for RXRE.

Receives ONLY canonical entities (schema.py). Does not know source formats.
Classifies observation_type and epistemic_state based on canonical fields.
"""
from __future__ import annotations
from .schema import make_entity, validate_entity

def classify_entity(entity):
    """Classify a canonical entity's observation_type and epistemic_state.

    Rules (verifiable, not format-dependent):
    - STRUCTURAL_FACT: entity from CFG or disassembly (static analysis)
    - DYNAMIC_OBSERVATION: entity from trace (runtime observation)
    - SEMANTIC_INFERENCE: entity from certificate metrics/results (inference)
    - CAUSAL_ATTRIBUTION: entity with verified causal evidence (operation + operands + result)
    """
    obs = entity.get("observation_type", "")
    # Preserve existing valid classifications
    if obs in ("STRUCTURAL_FACT", "DYNAMIC_OBSERVATION", "SEMANTIC_INFERENCE",
               "CAUSAL_ATTRIBUTION", "NOT_OBSERVED"):
        pass  # already classified
    else:
        obs = "SEMANTIC_INFERENCE"  # default

    # Epistemic state based on evidence, not execution status
    ep = entity.get("epistemic_state", "NOT_DETERMINED")
    exec_status = entity.get("execution_status", "NOT_EXECUTED")

    # Rule: execution_status PASS/FAIL does not change epistemic_state
    # Rule: if evidence_refs empty -> NOT_DETERMINED
    if not entity.get("evidence_refs"):
        ep = "NOT_DETERMINED"
    # Rule: if premises empty -> INSUFFICIENT (for inference types)
    if obs in ("SEMANTIC_INFERENCE", "CAUSAL_ATTRIBUTION") and not entity.get("premises"):
        ep = "INSUFFICIENT"

    return obs, ep


def classify_relation(relation, source_entities):
    """Classify a relation's epistemic state based on its evidence.

    Rules:
    - If both endpoints have DYNAMIC_OBSERVATION evidence -> DYNAMIC_OBSERVATION
    - If one endpoint is STRUCTURAL_FACT -> STRUCTURAL_FACT
    - If evidence is causal (operation + operands + result) -> CAUSAL_ATTRIBUTION
    - If only inference -> SEMANTIC_INFERENCE
    - If no evidence -> NOT_DETERMINED
    """
    obs = relation.get("obs_type", "SEMANTIC_INFERENCE")
    ep = relation.get("epistemic", "NOT_DETERMINED")
    # Preserve NOT_DETERMINED / NOT_OBSERVED
    if obs == "NOT_OBSERVED" or ep == "NOT_DETERMINED":
        return obs if obs != "NOT_OBSERVED" else "NOT_DETERMINED", "NOT_DETERMINED"
    # Preserve NOT_APPLICABLE
    if ep == "NOT_APPLICABLE":
        return obs, "NOT_APPLICABLE"
    # If evidence missing, NOT_DETERMINED
    if not relation.get("evidence_refs") and not relation.get("evidence"):
        return obs, "NOT_DETERMINED"
    return obs, ep


def classify_graph(entities, relations):
    """Classify all entities and relations in a canonical graph.

    Returns classified entities and relations without modifying originals.
    """
    classified_entities = []
    for e in entities:
        obs, ep = classify_entity(e)
        new_e = dict(e)
        new_e["observation_type"] = obs
        new_e["epistemic_state"] = ep
        classified_entities.append(new_e)

    classified_relations = []
    for r in relations:
        obs, ep = classify_relation(r, classified_entities)
        new_r = dict(r)
        new_r["obs_type"] = obs
        new_r["epistemic"] = ep
        classified_relations.append(new_r)

    return classified_entities, classified_relations
