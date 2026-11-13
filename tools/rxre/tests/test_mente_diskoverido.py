#!/usr/bin/env python3
"""MENTE etapa 2 — dry-run hermético sobre datos sellados PÚBLICOS (filenvercmp, gen 1).

MENTE elige, de las 34.145 parejas selladas, las que MAXIMIZAN el contraste entre
dos hipótesis rivales ingenuas; observa ÚNICAMENTE desde la matriz sellada
(matrix_native.txt); actualiza estatus sin PROVEN ni ratings ordenadaal azar.

El propósito NO es concluir sobre filenvercmp (eso ya está sellado y verificado);
es validar que la maquinaria de hipótesis/predicción funciona sobre datos reales
sellados sin tocar el oráculo ni el binario."""
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.mente import mente_cycle, select_discriminating_inputs, RivalHypothesis

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evidence" / "r3" / "oracle" / "cases_seed20261112.txt"
MATRIX = ROOT / "evidence" / "r3" / "oracle" / "matrix_native.txt"
RECON = ROOT / "evidence" / "r3" / "reconstruction" / "filenvercmp.c"

def _unescape(s):
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and i + 3 < len(s) and s[i+1] == 'x':
            out.append(int(s[i+2:i+4], 16)); i += 4
        else:
            out.append(ord(s[i])); i += 1
    return bytes(out)

def _load():
    pairs, rcs = [], []
    with open(CASES, 'rb') as cf, open(MATRIX, 'rb') as mf:
        for raw in cf:
            a, b = raw.split(b'\t', 1)
            pairs.append((_unescape(a.decode('latin1')), _unescape(b.decode('latin1').rstrip('\n'))))
        for raw in mf:
            rcs.append(int(raw.strip().decode()))
    return pairs, rcs

class _Flat(object):
    """Rival A: comparación plana lexicográfica (rango -1/0/1) — modelo inocentón."""
    @staticmethod
    def predict(x):
        a, b = x["a"], x["b"]
        return (a > b) - (a < b)

class _NaiveVer(object):
    """Rival B: versionado ingenuo — cada trozo de dígitos compara como int64;
    trozos no numéricos como bytes; empate numérico → byte compare con signo."""
    @staticmethod
    def predict(x):
        def tok(s):
            out, cur, num = [], b"", None
            for ch in s:
                isdigit = 48 <= ch < 58
                if num is None:
                    num = isdigit; cur += bytes([ch]); continue
                if isdigit == num:
                    cur += bytes([ch]); continue
                out.append((num, cur)); cur = bytes([ch]); num = isdigit
            out.append((num, cur))
            return out
        for (n1, t1), (n2, t2) in zip(tok(x["a"]), tok(x["b"])):
            if n1 and n2:
                i1, i2 = int(t1), int(t2)
                if i1 != i2:
                    return (i1 > i2) - (i1 < i2)
            else:
                if t1 != t2:
                    return (t1 > t2) - (t1 < t2)
        return (len(x["a"]) > len(x["b"])) - (len(x["a"]) < len(x["b"]))

def _mk_hypotheses():
    return [
        RivalHypothesis(id="FLAT_LESS", property_name="rc sign = memcmp sign",
                        claim="filenvercmp aplica un modelo plano (memcmp significado)",
                        predict=_Flat.predict, domain={"corpus": "seed20261112"}),
        RivalHypothesis(id="NAIVE_VER", property_name="rc sign = naive int version",
                        claim="filenvercmp aplica versionado ingenuo por segmentos",
                        predict=_NaiveVer.predict, domain={"corpus": "seed20261112"}),
    ]

def test_mente_selects_discriminating_pairs():
    pairs, rcs = _load()
    cands = [{"a": a, "b": b, "case_id": i} for i, (a, b) in enumerate(pairs)]
    hyps = _mk_hypotheses()
    ranked = select_discriminating_inputs(hyps, cands)
    assert ranked, "ambos rivales deben disentir en algún punto del corpus sellado"
    assert all(d["disagreeing_pairs"] > 0 for d in ranked)
    assert ranked[0]["disagreeing_pairs"] >= ranked[-1]["disagreeing_pairs"]

def test_mente_sealed_dry_run_observes_without_executing():
    pairs, rcs = _load()
    cands = [{"a": a, "b": b, "case_id": i} for i, (a, b) in enumerate(pairs)]
    hyps = _mk_hypotheses()
    rep = mente_cycle(
        hyps, cands, target_binary=str(RECON),
        target_runner=lambda x: rcs[x["case_id"]],
    )
    assert rep["selected"] is not None
    assert rep["observation"]["ok"] is True
    total = len(rep["refuted"]) + len(rep["surviving"]) + len(rep["indeterminate"])
    assert total == 2
    assert rep["epistemic_status"] in {"NOT_DETERMINED", "REFUTED_ALL", "UNKNOWN_WITHOUT_OBSERVED_EVIDENCE"}
    assert "PROVEN" not in str(rep)

def test_twin_models_yield_indistinguishable_domain():
    pairs, rcs = _load()
    cands = [{"a": a, "b": b, "case_id": i} for i, (a, b) in enumerate(pairs)]
    hyps = [
        RivalHypothesis(id="A", property_name="f", claim="modelo A", predict=_Flat.predict,
                        domain={"corpus": "seed20261112"}),
        RivalHypothesis(id="B", property_name="f", claim="gemelo de A", predict=_Flat.predict,
                        domain={"corpus": "seed20261112"}),
    ]
    rep = mente_cycle(hyps, cands, target_binary=str(RECON),
                      target_runner=lambda x: rcs[x["case_id"]])
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "limitacion" in rep
