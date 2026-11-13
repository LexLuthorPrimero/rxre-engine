"""M442 — Canonical dispatcher (M435-A). Additive, deterministic, fail-closed.
Rutea formatos a adapters existentes. No modifica schema/classifier/extractor/adapters.
"""
from __future__ import annotations
from .adapters import cert_adapter, trace_adapter, cfg_adapter, disasm_adapter, typed_event_adapter
from .schema import validate_entity

_FORMATS = {"CERT_JSON", "TRACE_JSON", "CFG_JSON", "DISASM_TXT", "TYPED_EVENT_JSON"}

def dispatch(artifact_path: str, fmt: str, **kwargs):
    """Rutea artefacto a su adapter. Fail-closed. Retorna (entities, adapter_msg, fmt)."""
    if fmt not in _FORMATS:
        raise ValueError(f" formato desconocido fail-closed: {fmt}")
    if fmt == "CERT_JSON":
        ents, msg = cert_adapter(artifact_path, **kwargs)
    elif fmt == "TRACE_JSON":
        ents, msg = trace_adapter(artifact_path, **kwargs)
    elif fmt == "CFG_JSON":
        ents, msg = cfg_adapter(artifact_path, **kwargs)
    elif fmt == "DISASM_TXT":
        ents, msg = disasm_adapter(artifact_path, **kwargs)
    else:
        ents, msg = typed_event_adapter(artifact_path, **kwargs)
    return ents, msg, fmt

def dispatch_and_validate(artifact_path: str, fmt: str, **kwargs):
    ents, msg, fmt = dispatch(artifact_path, fmt, **kwargs)
    valid = 0
    for e in ents:
        ok, _ = validate_entity(e)
        if ok:
            valid += 1
    # promoción rechazada por diseño: dispatcher nunca eleva PARTIAL/NOT_DETERMINED
    return {"entities": ents, "adapter_msg": msg, "format": fmt, "total": len(ents), "valid": valid}
