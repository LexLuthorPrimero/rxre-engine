#!/usr/bin/env python3
"""MENTE etapa 1 — experimento sintético hermético: hipótesis rivales sobre un
clasificador de bytes compilado on-the-fly; la prueba de fuego es que MENTE elige
la entrada que DISCRIMINA y que contradice sólo a la hipótesis que merece serlo."""
import sys, os, json, hashlib, subprocess, textwrap
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.mente import mente_cycle, select_discriminating_inputs, RivalHypothesis

C = r"""
#include <stdio.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    char b = argv[1][0];
    printf(VARIANT, b);
    return 0;
}
"""
VARIANTS = {
    "eq_m":  ' "1" : "0", b == \'m\' ?',   # placeholder replaced below
}

def _build(tmp_path, name, source):
    src = Path(tmp_path) / f"{name}.c"
    src.write_text(source)
    out = Path(tmp_path) / name
    p = subprocess.run(["gcc", "-O2", "-o", str(out), str(src)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-200:]
    return out

EQ_M   = '"1" : "0"\n'  # unused
SRC_EQ  = '#include <stdio.h>\n#include <string.h>\nint main(int argc,char**argv){if(argc<2)return 2;char b=argv[1][0];puts(b==\'m\'?"1":"0");return 0;}\n'
SRC_GE  = '#include <stdio.h>\n#include <string.h>\nint main(int argc,char**argv){if(argc<2)return 2;char b=argv[1][0];puts(b>=\'m\'?"1":"0");return 0;}\n'

def ry_eqM():  # rival: salida es 1 iff b=='m'
    return RivalHypothesis(id="EQ_M", property_name="classifier(b)=='m'?",
                           claim="f(b) == 1 exactamente cuando b=='m'",
                           predict=lambda x: "1" if x[0] == ord('m') else "0",
                           domain={"bytes": "a..z"})

def ry_geM():  # rival: salida es 1 iff b>='m'
    return RivalHypothesis(id="GE_M", property_name="classifier(b)>='m'?",
                           claim="f(b) == 1 exactamente cuando b>='m'",
                           predict=lambda x: "1" if x[0] >= ord('m') else "0",
                           domain={"bytes": "a..z"})

def ry_eqM_coll():  # rival gemelo de EQ_M
    h = ry_geM()
    h.id = "EQ_M_TWIN"
    h.claim = "gemelo distinta trayectoria"
    h.predict = lambda x: "1" if x[0] == ord('m') else "0"
    return h

def test_select_discriminating_input_ge_vs_eq():
    hyps = [ry_eqM(), ry_geM()]
    cand = [b"a", b"f", b"m", b"s", b"z"]
    ranked = select_discriminating_inputs(hyps, cand)
    # Cualquier candidato < 'm' discrimina (GE_M -> "0", EQ_M -> "0" ... no: "a" ambos 0).
    # Discrepan allí donde b>='m' y b!='m' (EQ_M "0" vs GE_M "1"), p. ej. 's' o 'z'.
    inputs = [c["input"] for c in ranked]
    assert b"s" in inputs and b"z" in inputs
    assert all(r["disagreeing_pairs"] > 0 for r in ranked)

def test_mente_refutes_wrong_rival_on_real_binary(tmp_path):
    binary = _build(tmp_path, "cls_ge", SRC_GE)
    hyps = [ry_eqM(), ry_geM()]
    rep = mente_cycle(hyps, [b"a", b"f", b"m", b"s", b"z"], str(binary))
    # EQ_M es falsa (ge >= m)
    assert "EQ_M" in rep["refuted"]
    assert "GE_M" in rep["surviving"]
    assert rep["refuted"] == ["EQ_M"]
    assert rep["epistemic_status"] == "NOT_DETERMINED"

def test_mente_refutes_ge_on_eq_binary(tmp_path):
    binary = _build(tmp_path, "cls_eq", SRC_EQ)
    hyps = [ry_eqM(), ry_geM()]
    rep = mente_cycle(hyps, [b"a", b"f", b"m", b"s", b"z"], str(binary))
    assert "GE_M" in rep["refuted"]
    assert "EQ_M" in rep["surviving"]

def test_mente_reports_indistinguishable_when_no_discriminant(tmp_path):
    binary = _build(tmp_path, "cls_eq2", SRC_EQ)
    hyps = [ry_eqM(), ry_eqM_coll()]     # gemelo exacto: no hay entrada que los separe
    rep = mente_cycle(hyps, [b"a", b"f", b"m", b"s", b"z"], str(binary))
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "limitacion" in rep
    assert rep["refuted"] == []

def test_mente_fail_closed_on_unexecutable_target(tmp_path):
    binary = _build(tmp_path, "cls_eq3", SRC_EQ)
    binary.unlink()
    hyps = [ry_eqM(), ry_geM()]
    rep = mente_cycle(hyps, [b"a", b"f", b"m", b"s", b"z"], str(binary))
    assert rep["epistemic_status"] == "UNKNOWN_WITHOUT_OBSERVED_EVIDENCE"
    assert rep["limitacion"].startswith("target no ejecutable")

def test_winner_is_never_called_proven(tmp_path):
    binary = _build(tmp_path, "cls_eq4", SRC_EQ)
    hyps = [ry_eqM(), ry_geM()]
    rep = mente_cycle(hyps, [b"a", b"f", b"m", b"s", b"z"], str(binary))
    import json
    raw = json.dumps(rep)
    ama = [k for k, v in rep.items() if str(v) == "PROVEN"]
    assert ama == [], ama
    assert "PROVEN" not in rep["epistemic_status"]

def test_empty_candidates_yield_not_determined(tmp_path):
    binary = _build(tmp_path, "cls_eq5", SRC_EQ)
    rep = mente_cycle([ry_eqM(), ry_geM()], [], str(binary))
    assert rep["epistemic_status"] == "NOT_DETERMINED"

def test_experiment_input_selection_is_minimal_and_repeatable(tmp_path):
    binary = _build(tmp_path, "cls_eq6", SRC_EQ)
    hyps = [ry_eqM(), ry_geM()]
    rep1 = mente_cycle([ry_eqM(), ry_geM()], [b"a", b"f", b"m", b"s", b"z"], str(binary))
    rep2 = mente_cycle([ry_eqM(), ry_geM()], [b"a", b"f", b"m", b"s", b"z"], str(binary))
    assert rep1["selected"]["input"] == rep2["selected"]["input"]
