"""M433 — additive ingestion of typed semantic events (M432 contract) into
canonical M426 entities/relations. Does NOT modify adapters/schema/classifier/extractor.
Evidence-justified: no existing adapter ingests typed semantic event format (F1 gap).
Strict epistemic separation: observation != inference; candidates stay SEMANTIC_INFERENCE/PARTIAL;
no promotion. Adjustment 3 preserved.
"""
from __future__ import annotations
import json, hashlib, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))  # repo root/tools parent context
# import from package path used in repo
from tools.rxre.causal.schema import make_entity, make_relation, validate_entity, SCHEMA_VERSION, ADAPTER_VERSION

INGEST_VERSION = "m433-v1"

EVENT_TYPE_TO_ENTITY = {
    "CALL_OBSERVED": "RESULT",
    "MEMORY_OBSERVED": "RESULT",
    "EFFECT_OBSERVED": "EFFECT",
    "TRANSFORM_CANDIDATE": "TRANSFORM",  # candidate entity; epistemic/obs class keep it non-proven
    "OUTPUT_CANDIDATE": "EFFECT",
    "RESULT_OBSERVED": "RESULT",
}

def _src_hash(path):
    try: return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
    except Exception: return "UNAVAILABLE"

def ingest_typed_events(events_payload, source_id="m432_typed_events", source_cert_hash=None):
    """Map M432 typed events to canonical entities/relations. Additive, no promotion."""
    events = events_payload.get("typed_events", events_payload) if isinstance(events_payload, dict) else events_payload
    entities = []; errors = []
    # build id set for relation resolution
    ev_ids = {e.get("event_id") for e in events}
    for ev in events:
        eid = ev.get("event_id")
        etype = ev.get("event_type","UNKNOWN")
        obs = ev.get("observation_class","NOT_OBSERVED")
        ep = ev.get("epistemic_state","NOT_DETERMINED")
        ex = ev.get("execution_status","NOT_EXECUTED")
        src = ev.get("source","")
        sh = _src_hash(src) if src and not src.startswith("derived") else (source_cert_hash or "DERIVED")
        src_format = "TYPED_EVENT_JSON"
        premises = list(ev.get("premises",[]))
        for note in ev.get("nominal_or_interpretive_notes",[]) or []:
            premises.append(f"note: {note}")
        premises.append(f"mechanism={ev.get('mechanism','')}")
        premises.append(f"event_type={etype}")
        if etype in ("TRANSFORM_CANDIDATE","OUTPUT_CANDIDATE"):
            premises.append("CANDIDATE_ONLY: not proven DATAFLOW/TRANSFORM/OUTPUT; no promotion (adj.3)")
        ent_type = EVENT_TYPE_TO_ENTITY.get(etype, "RESULT")
        # map relations
        rels = []
        for r in ev.get("relations",[]) or []:
            # M432 uses from_refs/to_ref/provenance_refs
            from_refs = r.get("from_refs") or ([r.get("from_id")] if r.get("from_id") else [])
            to_ref = r.get("to_ref") or r.get("to_id")
            # create one relation per from_ref (explicit refs); keep target ref as string
            for fr in from_refs:
                rels.append(make_relation(
                    from_id=fr if fr in ev_ids else f"ref:{fr}",
                    to_id=to_ref if (to_ref in ev_ids or str(to_ref).startswith("ref:")) else f"ref:{to_ref}",
                    relation_type=r.get("type","RELATED"),
                    obs_type=r.get("obs_type", obs),
                    epistemic=r.get("epistemic", ep),
                    evidence_refs=[sh] + [x for x in (r.get("provenance_refs") or []) if isinstance(x,str) and len(x)==64],
                    premises=[f"candidate_relation provenance_refs={r.get('provenance_refs',[])}"]
                ))
        extra = {"ingest_version": INGEST_VERSION, "mechanism": ev.get("mechanism"), "m432_event_type": etype}
        ent = make_entity(
            entity_id=eid,
            entity_type=ent_type,
            source_id=source_id,
            source_format=src_format,
            source_hash=sh if sh!="UNAVAILABLE" else (source_cert_hash or "UNAVAILABLE"),
            source_locator=ev.get("source_locator",""),
            observation_type=obs,
            epistemic_state=ep,
            execution_status=ex,
            evidence_refs=list(dict.fromkeys([sh] + (ev.get("evidence_refs") or []) + ([source_cert_hash] if source_cert_hash else []))),
            premises=premises,
            relations=rels,
            extra=extra,
        )
        # override adapter/normalization version fields in effect? make_entity sets them from schema constants; keep as-is (provenance note in extra)
        ok,msg = validate_entity(ent)
        if not ok: errors.append((eid,msg))
        entities.append(ent)
    return {"source_id":source_id,"ingest_version":INGEST_VERSION,"entities":entities,"total":len(entities),"valid":sum(1 for e in entities if validate_entity(e)[0]),"errors":errors}
