"""RXRE structural extractor subordinate to reconstructor M268 (M294).

Chain: EVIDENCE -> STRUCTURAL CANDIDATES -> FIELD ACCESS GRAPH ->
SEMANTIC HYPOTHESES -> CONTRACT -> VALIDATION

Consumes reconstructor outputs (inventory / xrefs / CFG / callgraph /
contextual / causal dims M268) without rebuilding them. No parallel
CFG/callgraph engine. Deterministic IDs and serialization.
"""
import hashlib
import json
import os
import re
import subprocess

FIELD_TYPES = ("POINTER", "INTEGER", "INLINE_DATA", "LINK", "ARRAY", "UNKNOWN")
EPISTEMIC = ("PROVEN", "PARTIAL", "NOT_DETERMINED", "PROVEN_ABSENT",
             "NOT_OBSERVED", "UNREACHABLE_IN_TEST", "BLOCKED", "INVALIDATED")
OWNERSHIP = ("OWNED", "BORROWED", "SHARED", "TRANSFERRED",
             "RETAINED_TO_EXIT", "UNKNOWN")
ALIAS = ("MUST_ALIAS", "MAY_ALIAS", "NO_ALIAS", "UNKNOWN")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8192), b""):
            h.update(b)
    return h.hexdigest()


def det_id(binary_sha, alloc_hex, size, offset):
    s = "%s|%s|%d|%d" % (binary_sha, alloc_hex, size, offset)
    return "e%s" % hashlib.sha256(s.encode()).hexdigest()[:16]


def parse_objdump_range(binary_path, start, stop):
    out = subprocess.run(["objdump", "-d", "--start-address=%s" % start,
                          "--stop-address=%s" % stop, binary_path],
                         capture_output=True, text=True, timeout=60).stdout
    return out.splitlines()


# Regex for Intel-style AT&T mem operands: 0xNN(%rXX) or (%rXX)
_MEM_RE = re.compile(r"(-?0x[0-9a-fA-F]+|-?0x0)?\(%r[a-z0-9]+\)")
_BASE_RE = re.compile(r"\((%r[a-z0-9]+)\)")
_OFF_RE = re.compile(r"(-0x[0-9a-fA-F]+|0x[0-9a-fA-F]+)\(\s*%r")


def _parse_offset(field):
    f = field.strip()
    if not f:
        return 0
    try:
        return int(f, 16)
    except ValueError:
        return 0


def extract_field_accesses(lines):
    """Group memory accesses by (base_reg, offset) to avoid conflating
    distinct entities that share an offset (e.g. table %r13 vs entry
    %rbx at +0/+8). Returns dict (base, offset) -> {instrs, width_hint}.

    Width from mnemonic; conservative: never invent C type.
    """
    by_key = {}
    for ln in lines:
        if ":" not in ln:
            continue
        m = _MEM_RE.search(ln)
        if not m:
            continue
        bm = _BASE_RE.search(ln)
        base = bm.group(1) if bm else "?"
        token = m.group(1) or "0x0"
        off = _parse_offset(token)
        if off < 0 or off > 0x200:
            continue
        mnem = ln.split("\t")[-1].strip().split()[0] if "\t" in ln else ln.strip().split()[-1]
        key = (base, off)
        slot = by_key.setdefault(key, {"offsets": set(), "instrs": [], "mnems": set(), "bases": set()})
        slot["offsets"].add(off)
        slot["bases"].add(base)
        if len(slot["instrs"]) < 12:
            slot["instrs"].append(ln.strip()[:160])
        slot["mnems"].add(mnem)
        if mnem.startswith("movups") or mnem.startswith("movdqu"):
            w = 16
        elif mnem.startswith("movb") or mnem.startswith("andb") or mnem.startswith("cmpb"):
            w = 1
        elif mnem.startswith("movq"):
            w = 8
        elif mnem.startswith("movl") or mnem.startswith("movs") or mnem.startswith("movss"):
            w = 4
        elif mnem in ("add", "sub", "cmp", "test", "inc", "dec"):
            w = 4
        else:
            w = 0
        slot["width"] = max(slot.get("width", 0), w)
    return by_key


def infer_type(mnems, instrs):
    joined = " ".join(sorted(mnems)) + " " + " | ".join(instrs)
    if any("call" in i.lower() and "*0x" in i for i in instrs):
        return "POINTER", "callback slot (call *off(reg)) observed in disasm"
    if any(i.strip().endswith(("*0x30(%r13)", "*0x38(%r13)", "*0x40(%r13)", "*0x40(%rbx)"))
           for i in instrs):
        return "POINTER", "indirect call through offset -> callback pointer"
    arith = any(m in ("add", "sub", "cmp") for m in mnems)
    indirect = any("call" in i.lower() for i in instrs)
    if arith and not indirect:
        return "INTEGER", "arithmetic/compare on offset without dereference proof"
    if any(m.startswith("movups") or m.startswith("movdqu") for m in mnems):
        return "INLINE_DATA", "vector/array copy (movups/movdqu) at offset"
    if any("lea" in i.lower() for i in instrs):
        return "POINTER", "address taken (lea) -> pointer candidate"
    # plain mov to/from reg with no call: ambiguous pointer vs int
    return "UNKNOWN", "no dereference/call proof; kept UNKNOWN (no C type invented)"


def validate_contract(c):
    errs = []
    if not isinstance(c.get("identity"), str) or not c["identity"]:
        errs.append("identity missing")
    for f in c.get("fields", []):
        typ = f.get("observed_type", f.get("type"))
        if typ not in FIELD_TYPES:
            errs.append("field type %s invalid" % typ)
        if f.get("epistemic") not in EPISTEMIC:
            errs.append("field epistemic invalid")
    return (len(errs) == 0, errs)


def extract_contract(binary_path, candidate, provenance):
    """candidate: {alloc_site, size, func_start, func_end, role}
    Optional candidate["ranges"]: list of [start, end] to merge access
    graphs across init/insert/free functions (shared entity).
    provenance: {recon_sha, context_refs, dynamic_refs, method}
    Field graph derived by executing objdump on the ELF and parsing
    bytes. Semantics/ownership/lifecycle attached as separate
    hypotheses with own epistemic states.
    """
    bsha = provenance["binary_sha256"]
    ranges = candidate.get("ranges") or [(candidate["func_start"], candidate["func_end"])]
    combined = []
    for (s, e) in ranges:
        combined.extend(parse_objdump_range(binary_path, s, e))
    by_key = extract_field_accesses(combined)
    fields = []
    for (base, off) in sorted(by_key.keys(), key=lambda k: (k[1], k[0])):
        slot = by_key[(base, off)]
        typ, why = infer_type(slot["mnems"], slot["instrs"])
        fields.append({
            "id": det_id(bsha, candidate["alloc_site"], candidate["size"], off) + "-" + base,
            "base_reg": base,
            "offset": off,
            "offset_hex": hex(off),
            "width_observed": slot.get("width", 0),
            "observed_type": typ,
            "type_evidence": why,
            "readers": slot["instrs"][:4],
            "writers": slot["instrs"][:4],
            "mnems": sorted(slot["mnems"]),
            "epistemic": "PARTIAL",
            "semantic_hypothesis": None,  # filled by ASSISTED step, never from offset alone
            "category": "STRUCTURAL_FACT",
        })
    return {
        "identity": "%s/%s" % (os.path.basename(binary_path), candidate["role"]),
        "binary": binary_path,
        "binary_sha256": bsha,
        "candidate": candidate,
        "size": candidate["size"],
        "fields": fields,
        "provenance": provenance,
    }


def contract_from_extraction(ext, semantic, ownership, lifecycle, callbacks):
    """semantic: {offset_hex: {name, epistemic, cap}} ASSISTED labels.
    Ownership/lifecycle/callbacks: separate contracts each own epistemic.
    """
    fields = []
    for f in ext["fields"]:
        s = semantic.get(f["offset_hex"], {})
        fields.append(dict(f, semantic_name=s.get("name"),
                           semantics_state=s.get("epistemic", "NOT_DETERMINED"),
                           category="SEMANTIC_INFERENCE" if s else "STRUCTURAL_FACT"))
    return {
        "identity": ext["identity"],
        "binary_sha256": ext["binary_sha256"],
        "size": ext["size"],
        "fields": fields,
        "relationships": semantic.get("_relations", []),
        "ownership_contract": ownership,
        "lifecycle_contract": lifecycle,
        "callback_contract": callbacks,
      "provenance": ext["provenance"],
        "limits": semantic.get("_limits", []),
    }


def serialize_contract(contract):
    ok, errs = validate_contract(contract)
    if not ok:
        raise ValueError("contract malformed: %s" % errs)
    return json.dumps(contract, sort_keys=True, ensure_ascii=False)


def determinism_check(fn, *args, **kwargs):
    a = fn(*args, **kwargs)
    b = fn(*args, **kwargs)
    return serialize_contract(a) == serialize_contract(b)


# ---- M295: identity / alias / relations (additive, retrocompatible) ----
REL_TYPES = ("CONTAINS", "POINTS_TO", "REFERENCES", "LINKS_TO",
             "SHARES_WITH", "TRANSFERS_TO", "CONSUMES", "RELEASES")

# ---- M298: pointer-transfer events (additive, retrocompatible) ----
# Covers COPY/ALIAS/PUBLISH lineage without conflating object/ptr/
# address/content/ownership. REALLOC excluded from dynamic claims.
TRANSFER_EVENTS = ("POINTER_COPY", "POINTER_STORE", "POINTER_LOAD",
                   "ARGUMENT_TRANSFER", "RETURN_TRANSFER",
                   "CONTAINER_INSERT", "CONTAINER_REMOVE", "PUBLISH",
                   "LAST_USE", "FREE", "REFERENCE_INVALIDATION")


def transfer_edge(inst_id, event, src_loc, dst_loc, func_hex, instr_hex,
                  alias, evidence, epistemic, provenance):
    if event not in TRANSFER_EVENTS:
        raise ValueError("transfer event %s invalid" % event)
    if alias not in ALIAS:
        raise ValueError("alias %s invalid" % alias)
    return {"instance": inst_id, "event": event, "src": src_loc,
            "dst": dst_loc, "func": func_hex, "instr": instr_hex,
            "alias": alias, "evidence": evidence,
            "epistemic": epistemic, "provenance": provenance}


def build_lineage_chain(inst_id, edges):
    """Assemble ALLOC->...->FREE for one instance from observed edges
    (sorted deterministically by event order). Unknown steps stay
    absent; never synthesized. Each edge must carry the same instance
    or the chain builder refuses silently (returns only prefix)."""
    chain = []
    for e in edges:
        if e.get("instance") != inst_id:
            continue
        chain.append(e)
    order = {name: i for i, name in enumerate(TRANSFER_EVENTS)}
    return sorted(chain, key=lambda e: order.get(e.get("event", ""), 99))


def make_entity_id(binary_sha, alloc_site, size, alloc_ctx):
    s = "%s|%s|%d|%s" % (binary_sha, alloc_site, size, alloc_ctx)
    return "ent_%s" % hashlib.sha256(s.encode()).hexdigest()[:16]


# ---- M296: instance granularity (additive, retrocompatible) ----
# ALLOCATION_SITE_ID = class origin (== old ENTITY_ID lineage, kept for
# M293-M295 consumers). ALLOCATION_EVENT_ID / ENTITY_INSTANCE_ID =
# concrete instance, unique per event (generation+ordinal), stable across
# runs for the same observed order (addresses NOT hashed: ASLR-safe).
def make_site_id(binary_sha, alloc_site, size, alloc_ctx):
    return make_entity_id(binary_sha, alloc_site, size, alloc_ctx)


def make_event_id(binary_sha, alloc_site, size, alloc_ctx, generation, ordinal):
    s = "%s|%s|%d|%s|g%d|%d" % (binary_sha, alloc_site, size,
                                 alloc_ctx, generation, ordinal)
    return "evt_%s" % hashlib.sha256(s.encode()).hexdigest()[:16]


def make_instance_id(binary_sha, alloc_site, size, alloc_ctx, generation, ordinal):
    s = "%s|%s|%d|%s|g%d|%d" % (binary_sha, alloc_site, size,
                                 alloc_ctx, generation, ordinal)
    return "ins_%s" % hashlib.sha256(s.encode()).hexdigest()[:16]


def make_generation(observed_ptr, history):
    """history: list of {ptr, freed:bool} observed in order. Generation
    of observed_ptr = 1 + # prior alloc/free cycles that reused ptr.
    New ptr never seen => generation 1. Same ptr after free => +1.
    Deterministic w.r.t. observed order, independent of ASLR values."""
    gen = 1
    for h in history:
        if h.get("ptr") == observed_ptr and h.get("freed"):
            gen += 1
    return gen


def resolve_instance_alias(a, b, evidence):
    """evidence: {same_instance_ref, distinct_live, reused_released,
    cross_binary, same_site_only}. Between concrete instances:
    - same_instance_ref (ptr equality without intervening free/reuse)
      => MUST_ALIAS within instance-continuity scope.
    - distinct_live (two live ptrs, different alloc events)
      => NO_ALIAS (never fuse same-site live objects).
    - reused_released (same address, new generation after free)
      => NO_ALIAS (new instance, id differs even though address matches).
    - same_site/size/ctx alone => UNKNOWN (class match, not instance)."""
    if evidence.get("distinct_live"):
        return ("NO_ALIAS", "two live instances, distinct alloc events")
    if evidence.get("reused_released"):
        return ("NO_ALIAS", "address reused after free: new generation")
    if evidence.get("same_instance_ref") and not evidence.get("freed_between"):
        return ("MUST_ALIAS", "same instance ref, no free/reuse between")
    if evidence.get("cross_binary"):
        return ("UNKNOWN", "cross-binary identity not provable")
    if evidence.get("same_site_only"):
        return ("UNKNOWN", "same alloc site is class match, not instance")
    return ("UNKNOWN", "insufficient instance evidence")


def make_location(region, base_hex, offset_hex):
    return {"region": region, "base": base_hex, "offset": offset_hex,
            "id": "loc_%s" % hashlib.sha256(
                ("%s|%s|%s" % (region, base_hex, offset_hex)).encode()
            ).hexdigest()[:12]}


def make_context(func_hex, instr_hex, path, domain):
    return {"func": func_hex, "instr": instr_hex, "path": path,
            "domain": domain,
            "id": "ctx_%s" % hashlib.sha256(
                ("%s|%s|%s|%s" % (func_hex, instr_hex, path, domain)).encode()
            ).hexdigest()[:12]}


def build_entity_registry(binary_sha, candidates):
    """candidates: [{alloc_site, size, alloc_ctx, role}] -> entities with
    ENTITY_ID (logical), MEMORY_LOCATIONs, ACCESS_CONTEXTs. (base,offset)
    is an observation key only, never identity.
    M296: candidates may carry generation/ordinal/ptr/history ->
    adds ALLOCATION_SITE_ID (class), ALLOCATION_EVENT_ID,
    ENTITY_INSTANCE_ID, LIFETIME_GENERATION. Without event data,
    instance fields are None (class-only, NOT claimed as instance)."""
    ents = []
    history = []
    for idx, c in enumerate(candidates):
        eid = make_entity_id(binary_sha, c["alloc_site"], c["size"], c["alloc_ctx"])
        site = make_site_id(binary_sha, c["alloc_site"], c["size"], c["alloc_ctx"])
        has_event = ("generation" in c) or ("ordinal" in c) or ("ptr" in c)
        if has_event:
            gen = c.get("generation")
            if gen is None and "ptr" in c:
                gen = make_generation(c["ptr"], history)
            if gen is None:
                gen = 1
            ordinal = c.get("ordinal", idx)
            evt = make_event_id(binary_sha, c["alloc_site"], c["size"],
                                c["alloc_ctx"], gen, ordinal)
            ins = make_instance_id(binary_sha, c["alloc_site"], c["size"],
                                   c["alloc_ctx"], gen, ordinal)
        else:
            gen = None
            evt = None
            ins = None
        ents.append({
            "entity_id": eid,
            "allocation_site_id": site,
            "allocation_event_id": evt,
            "entity_instance_id": ins,
            "lifetime_generation": gen,
            "role": c["role"],
            "size": c["size"],
            "alloc_site": c["alloc_site"],
            "alloc_ctx": c["alloc_ctx"],
            "locations": [make_location("heap", c.get("ptr", "alloc_ret"), "0x0")],
            "contexts": [make_context(c.get("func", "?"), c["alloc_site"], "alloc", c.get("domain", "static"))],
            "lineage": [binary_sha[:12], c["alloc_site"], c["alloc_ctx"]],
        })
        history.append({"ptr": c.get("ptr"), "freed": bool(c.get("freed"))})
    return ents


def resolve_alias(loc_a, loc_b, evidence):
    """evidence: {ptr_equal_dynamic: bool, same_alloc_site: bool,
    context_scoped: str|None, contradict_observed: bool}
    MUST_ALIAS only if ptr_equal_dynamic and same_alloc_site lineage and
    no contradiction; offset/size equality alone => UNKNOWN (never MUST)."""
    if evidence.get("ptr_equal_dynamic") and evidence.get("same_alloc_site") \
            and not evidence.get("contradict_observed"):
        return ("MUST_ALIAS",
                "ptr equality observed + same alloc lineage (ctx=%s)"
                % evidence.get("context_scoped", "global"))
    if evidence.get("contradict_observed") and evidence.get("distinct_proof"):
        return ("NO_ALIAS", "contradiction with distinctness proof")
    if evidence.get("same_offset_or_size_only"):
        return ("UNKNOWN", "offset/size equality is not identity proof")
    if evidence.get("chain_next"):
        return ("MAY_ALIAS", "chained link candidate, variable target")
    return ("UNKNOWN", "insufficient identity evidence")


def validate_alias(a):
    return a.get("alias") in ALIAS and a.get("rel_type", "ALIAS") is not None


def structural_rel(src, dst, rel_type, alias, evidence, epistemic, provenance):
    return {"src": src, "dst": dst, "rel": rel_type, "alias": alias,
            "evidence": evidence, "epistemic": epistemic,
            "provenance": provenance}
