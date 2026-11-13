#!/usr/bin/env python3
"""M263 profiles — hermetic: profiles apply ONLY when the binary sha256 matches a sealed hash.
Zero historical leakage for foreign binaries. No real binaries required."""
import sys, os, json, hashlib, copy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import rxre.semantic.reconstructor as rc
import rxre.semantic.profiles as profiles_mod

LS_SHA = "54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c"
GREP_SHA = "f0320b67dd6fe51276a6b0c57dac81d0fa5950dee0275ee30364e6b459b88af4"

def _report(path):
    return {"artifact": {"path": path},
            "callgraph": {"edges": [
                {"call_type": "CALL_INDIRECT", "source_offset": 0x392f, "caller_offset": 0x392f,
                 "contextual_resolutions": [
                     {"target_symbol": "__libc_start_main", "caller_offset": 0x392f,
                      "context_id": "ctx1", "binary_sha256": LS_SHA, "context_inputs": {}}
                 ]}]},
            "limitations": []}

def test_profiles_have_sealed_hashes():
    prof = profiles_mod.load_profiles()
    assert LS_SHA in prof and prof[LS_SHA]["profile_id"] == "m263-ls-202611"
    assert GREP_SHA in prof and prof[GREP_SHA]["profile_id"] == "m263-grep-202611"
    assert prof[LS_SHA]["reachability"]["0x392f|__libc_start_main"]["r"] == "REACHED"

def test_profile_applies_on_sealed_hash(monkeypatch, tmp_path):
    target = tmp_path / "bin-cualquiera.bin"; target.write_bytes(b"fake-ls-bytes")
    monkeypatch.setattr(profiles_mod, "_hash_of", lambda p: LS_SHA)
    rep = _report(str(target))
    rc.m263_enrich(rep)
    c = rep["callgraph"]["edges"][0]["contextual_resolutions"][0]
    assert c["reachability_status"] == "REACHED"
    assert c["observability_status"] == "OBSERVED"
    assert c["causality_result"] == "STATIC_SUPPORTED"
    assert rep["callgraph"]["causal_analysis"]["counts_by_reachability"] == {"REACHED": 1}
    assert "m263-ls-202611" in rep["profile_application"]

def test_profile_never_applies_on_foreign_hash(monkeypatch, tmp_path):
    target = tmp_path / "foreign.bin"; target.write_bytes(b"not-the-sealed-binary")
    monkeypatch.setattr(profiles_mod, "_hash_of", lambda p: hashlib.sha256(b"foreign").hexdigest())
    rep = _report(str(target))
    rc.m263_enrich(rep)
    c = rep["callgraph"]["edges"][0]["contextual_resolutions"][0]
    assert c["reachability_status"] == "CONDITION_UNKNOWN"
    assert c["causality_result"] == "NOT_DETERMINED"
    assert c["observability_status"] == "INSUFFICIENT_INSTRUMENTATION"
    assert rep["callgraph"]["causal_analysis"]["counts_by_reachability"] == {"CONDITION_UNKNOWN": 1}
    assert "sin perfil experimental" in rep["profile_application"]

def test_profile_missing_file_fail_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(profiles_mod, "_hash_of", lambda p: None)
    rep = _report("/nonexistent/binary")
    rc.m263_enrich(rep)
    c = rep["callgraph"]["edges"][0]["contextual_resolutions"][0]
    assert c["reachability_status"] == "CONDITION_UNKNOWN"
    assert "sin perfil experimental" in rep["profile_application"]

def test_grep_blocked_callsites_bound(monkeypatch, tmp_path):
    """grep profile: callsite 0xcfec must map to OBSERVATION_BLOCKED, ls profile must not."""
    rep = _report("dummy")
    e = rep["callgraph"]["edges"][0]
    e["source_offset"] = 0xcfec
    e["contextual_resolutions"][0].update({"target_symbol": "sym.null_action", "caller_offset": 0xcfec, "binary_sha256": GREP_SHA, "context_id": "ctx2"})
    target = tmp_path / "g.bin"; target.write_bytes(b"x")
    monkeypatch.setattr(profiles_mod, "_hash_of", lambda p: GREP_SHA)
    rep = _report(str(target))
    ee = rep["callgraph"]["edges"][0]
    ee["source_offset"] = 0xcfec
    ee["contextual_resolutions"][0].update({"target_symbol": "sym.null_action", "caller_offset": 0xcfec, "binary_sha256": GREP_SHA, "context_id": "ctx2"})
    rc.m263_enrich(rep)
    c = ee["contextual_resolutions"][0]
    assert c["observability_status"] == "OBSERVATION_BLOCKED_BY_OPERATIONAL_CONSTRAINT"
    assert c["domain_status"] == "OPERATIONALLY_RESTRICTED"
