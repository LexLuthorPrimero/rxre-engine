"""RXRE-MISSION-390 — Descubrimiento automático genérico de fuentes.

Descubre fuentes disponibles a partir de artefactos e interfaces reales ya
existentes, sin crear un inventario paralelo ni heurísticas específicas de
libtiff. Clasifica cada fuente como:
  - discovered: encontrada (referencia disponible)
  - accessible: verificable (existe/hash comprobable)
  - analyzed: ya analizada (resultado persistido disponible)
  - extracted: evidencia extraída (observación generada)
  - inaccessible: no verificable
  - duplicate: duplicado de otra fuente
  - contradictory: contradice otra fuente
  - not_determined: no se puede clasificar

No ejecuta binarios. No crea DB. No decide demostración (eso es M388/contrato).
"""
from __future__ import annotations
import sys, os, hashlib, json
try:
    from rxre.integrations.rz_memory_evidence import run as _rz_run, extract_memory_operands as _rz_extract
except Exception:
    _rz_run = None
    _rz_extract = None
try:
    from rxre.analysis.flow_access import run as _flow_run
except Exception:
    _flow_run = None
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

SOURCE_STATUSES = ("discovered", "accessible", "analyzed", "extracted",
                   "inaccessible", "duplicate", "contradictory", "not_determined")


def _hash_file(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _src_id(src):
    # stable id from available provenance
    key = (src.get("kind"), src.get("artifact"), src.get("location", {}).get("file"),
           src.get("location", {}).get("line"), src.get("location", {}).get("function"),
           src.get("hash"))
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str).encode()).hexdigest()[:16]


def discover(context):
    """context: dict with keys:
      target: str (buffer/target id)
      artifact_paths: list of str (paths to verify)
      source_refs: list of {file,line,function,...}
      symbol_refs: list of {name, address, artifact, ...}
      persisted_refs: list of {path, hash, ...} (already analyzed results)
      prior_sources: list of discovered sources (for dedup/contradiction)
    Returns dict with discovered list + stats + errors.
    """
    errors = []
    extra_obs = []
    target = context.get("target")
    context["_object_class"] = context.get("object_class", "UNKNOWN")
    if not target:
        return {"status": "BLOCKED", "decision": "NOT_DETERMINED",
                "errors": ["target required"], "discovered": [],
                "stats": {}, "provenance": {}}

    discovered = []
    seen_ids = set()
    duplicates = []
    inaccessible = []

    def add(src):
        nonlocal discovered, duplicates, inaccessible
        sid = _src_id(src)
        if sid in seen_ids:
            # find original
            dup = {"source_id": sid, "duplicate_of": sid, "source": src,
                   "status": "duplicate", "note": "duplicate source (same provenance)"}
            duplicates.append(dup)
            return
        seen_ids.add(sid)
        # classify accessibility
        status = "discovered"
        artifact = src.get("artifact")
        kind = src.get("kind")
        # accessibility: source_ref/symbol/persisted are accessible if they carry location/provenance;
        # artifact_path requires file existence.
        if kind == "artifact_path":
            if artifact and os.path.isfile(artifact):
                h = _hash_file(artifact)
                if h is not None:
                    status = "accessible"
                    src = dict(src); src["verified_hash"] = h
                    if src.get("hash") and src["hash"] != h:
                        src["hash_mismatch"] = True
            elif artifact:
                status = "inaccessible"
                inaccessible.append({"source_id": sid, "source": src, "status": "inaccessible",
                                     "note": "artifact not found"})
                src = dict(src); src["status"] = "inaccessible"
                discovered.append(src); return
        else:
            # location-based accessibility
            loc = src.get("location") or {}
            if loc.get("file") or loc.get("function") or src.get("provenance"):
                status = "accessible"
            else:
                status = "inaccessible"
                inaccessible.append({"source_id": sid, "source": src, "status": "inaccessible",
                                     "note": "no verifiable location/provenance"})
                src = dict(src); src["status"] = "inaccessible"
                discovered.append(src); return
        # analyzed? if in persisted_refs
        analyzed = False
        for pr in (context.get("persisted_refs") or []):
            if pr.get("source_id") == sid or pr.get("artifact") == artifact:
                analyzed = True
                break
        if analyzed:
            status = "analyzed"
        src = dict(src)
        src["source_id"] = sid
        src["status"] = status
        discovered.append(src)

    # source_refs
    for r in (context.get("source_refs") or []):
        src = {
            "kind": "source_ref",
            "artifact": r.get("file"),
            "location": {"file": r.get("file"), "line": r.get("line"),
                         "function": r.get("function")},
            "hash": r.get("hash"),
            "provenance": "provided source reference",
            "method": "source_ref_discovery",
        }
        add(src)
        # generic metadata-driven observations (data-driven, no heuristics)
        loc = src["location"]
        if "offset" in r:
            extra_obs.append({
                "obs_id": f"src_off_{_src_id(src)}",
                "source_artifact": r.get("file") or "unknown",
                "kind": "source_ref_offset",
                "property_hint": "BUFFER_OFFSET",
                "value": r.get("offset"),
                "value_kind": r.get("offset_kind", "CONSTANT"),
                "location": loc,
                "method": "source_ref_discovery",
                "proven": bool(r.get("offset_proven", False)),
                "quantity": "source_argument",
            })
        if "alias" in r:
            extra_obs.append({
                "obs_id": f"src_alias_{_src_id(src)}",
                "source_artifact": r.get("file") or "unknown",
                "kind": "source_ref_alias",
                "property_hint": "BUFFER_ALIAS_SET",
                "value": r.get("alias"),
                "value_kind": r.get("alias_kind", "CANDIDATE"),
                "location": loc,
                "method": "source_ref_discovery",
                "proven": bool(r.get("alias_proven", False)),
                "quantity": "source_argument",
            })
        if "access_length" in r:
            extra_obs.append({
                "obs_id": f"src_len_{_src_id(src)}",
                "source_artifact": r.get("file") or "unknown",
                "kind": "source_ref_access_length",
                "property_hint": "BUFFER_ACCESS_LENGTH",
                "value": r.get("access_length"),
                "value_kind": r.get("access_length_kind", "SYMBOLIC"),
                "location": loc,
                "method": "source_ref_discovery",
                "proven": bool(r.get("access_length_proven", False)),
                "quantity": "source_argument",
            })

    # symbol_refs
    for r in (context.get("symbol_refs") or []):
        src = {
            "kind": "binary_symbol",
            "artifact": r.get("artifact"),
            "location": {"function": r.get("name"), "offset": r.get("address")},
            "hash": r.get("artifact_hash"),
            "provenance": "binary symbol reference",
            "method": "symbol_discovery",
            "value": r.get("name"),
        }
        add(src)

    # artifact_paths
    for p in (context.get("artifact_paths") or []):
        src = {
            "kind": "artifact_path",
            "artifact": p,
            "location": {},
            "hash": None,
            "provenance": "artifact path provided",
            "method": "path_discovery",
        }
        add(src)

    # persisted_refs (already analyzed)
    for pr in (context.get("persisted_refs") or []):
        src = {
            "kind": "persisted_result",
            "artifact": pr.get("path"),
            "location": pr.get("location", {}),
            "hash": pr.get("hash"),
            "provenance": "persisted analysis result",
            "method": "persisted_discovery",
            "analyzed": True,
        }
        add(src)

    # contradiction detection: same property_hint? We don't have property hints here.
    # Detect contradictions by artifact+location with differing hash/value.
    contradictions = []
    by_art = {}
    for s in discovered:
        key = (s.get("artifact"), json.dumps(s.get("location"), sort_keys=True))
        by_art.setdefault(key, []).append(s)
    for key, grp in by_art.items():
        hashes = {g.get("hash") or g.get("verified_hash") for g in grp}
        hashes.discard(None)
        if len(hashes) > 1:
            contradictions.append({
                "artifact": key[0],
                "location": key[1],
                "hashes": sorted(hashes),
                "note": "contradictory hashes for same artifact/location",
            })

    # stats
    status_counts = {}
    for s in discovered:
        st = s.get("status", "discovered")
        status_counts[st] = status_counts.get(st, 0) + 1

    stats = {
        "n_discovered": len(discovered),
        "n_accessible": status_counts.get("accessible", 0) + status_counts.get("analyzed", 0),
        "n_analyzed": status_counts.get("analyzed", 0),
        "n_inaccessible": len(inaccessible),
        "n_duplicates": len(duplicates),
        "n_contradictions": len(contradictions),
        "status_counts": status_counts,
    }

    # Rz/Capstone memory evidence (optional, generic)
    rz_observations = []
    for mr in (context.get("memory_ranges") or []):
        if _rz_run is None:
            errors.append("rz_memory_evidence unavailable")
            continue
        artifact = mr.get("artifact")
        start = mr.get("start", 0)
        length = mr.get("length", 0)
        target = mr.get("target", target)
        records, obs, cs_res = _rz_run(artifact, start, length, target)
        rz_observations.extend(obs)
        # register each memory operand as a discovered source
        for rec in records[:50]:
            src = {
                "kind": "rz_memory_operand",
                "artifact": artifact,
                "location": {"function": target, "offset": rec.get("instruction_address")},
                "hash": cs_res.get("precheck", {}).get("input_hash"),
                "provenance": "capstone memory operand extraction",
                "method": "rz_memory_evidence",
                "value": rec.get("displacement"),
            }
            add(src)
    # precomputed memory observations
    for o in (context.get("memory_observations") or []):
        rz_observations.append(o)
    # store for caller
    context["_rz_observations"] = rz_observations
    # Flow analysis (optional, generic)
    flow_observations = []
    for fr in (context.get("flow_ranges") or []):
        if _flow_run is None:
            errors.append("flow_access unavailable")
            continue
        artifact = fr.get("artifact")
        start = fr.get("start", 0)
        length = fr.get("length", 0)
        target = fr.get("target", target)
        flow, obs, cs_res = _flow_run(artifact, start, length, target)
        if flow is not None:
            flow_observations.extend(obs)
            # register a discovered source
            src = {
                "kind": "flow_analysis",
                "artifact": artifact,
                "location": {"function": target},
                "hash": cs_res.get("precheck", {}).get("input_hash"),
                "provenance": "generic flow analysis",
                "method": "flow_access",
                "value": flow.get("n_memory_accesses"),
            }
            add(src)
    context["_flow_observations"] = flow_observations
    # GDB auto-trace observations (optional, generic)
    gdb_auto_obs = context.get("gdb_auto_obs") or []
    context["_gdb_auto_observations"] = list(gdb_auto_obs)
    # LD_PRELOAD observations (optional, generic)
    ldp_obs = context.get("ldpreload_obs") or []
    context["_ldp_observations"] = list(ldp_obs)
    # to_observations: convert discovered sources into observations for collector.
    # Generic mapping: source_ref/binary_symbol/persisted -> identity + origin (and offset if location has offset).
    observations = []
    observations.extend(extra_obs)
    observations.extend(context.get("_rz_observations", []))
    observations.extend(context.get("_flow_observations", []))
    observations.extend(context.get("_ldp_observations", []))
    observations.extend(context.get("_gdb_auto_observations", []))
    for s in discovered:
        if s.get("status") == "inaccessible":
            continue
        # identity observation
        observations.append({
            "obs_id": f"disc_{s['source_id']}_identity",
            "source_artifact": s.get("artifact") or "unknown",
            "kind": "discovered_source",
            "property_hint": "BUFFER_IDENTITY",
            "value": s.get("value") or s.get("artifact"),
            "location": s.get("location", {}),
            "method": s.get("method", "discovery"),
            "proven": False,
        })
        # origin observation (if artifact present)
        observations.append({
            "obs_id": f"disc_{s['source_id']}_origin",
            "source_artifact": s.get("artifact") or "unknown",
            "kind": "discovered_source",
            "property_hint": "BUFFER_ORIGIN",
            "value": "MULTIPLE" if len(discovered) > 1 else "UNKNOWN",
            "value_kind": "MULTIPLE" if len(discovered) > 1 else "UNKNOWN",
            "location": s.get("location", {}),
            "method": s.get("method", "discovery"),
            "proven": False,
        })
        # offset observation only for source_ref with explicit offset metadata
        # (do not treat instruction addresses as buffer offsets)

    result = {
        "status": "PASS_PARTIAL" if discovered else "BLOCKED",
        "decision": "PARTIAL" if discovered else "NOT_DETERMINED",
        "target": target,
        "discovered": discovered,
        "duplicates": duplicates,
        "inaccessible": inaccessible,
        "contradictions": contradictions,
        "observations": observations,
        "stats": stats,
        "errors": errors,
        "provenance": {
            "method": "generic_source_discovery",
            "integrity": "hashes verified where accessible",
            "no_execution": True,
        },
    }
    return result


def discover_and_collect(context, collector_fn=None):
    """Convenience: discover then return observations ready for collector."""
    disc = discover(context)
    return disc, disc.get("observations", [])


__all__ = ["discover", "discover_and_collect", "SOURCE_STATUSES"]
