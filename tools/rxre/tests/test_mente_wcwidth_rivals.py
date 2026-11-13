#!/usr/bin/env python3
"""MENTE etapa 2b — rivalidad BYTES / codepoints / WCWIDTH sobre el oráculo sellado de wc -L.

rival BYTES:      ancho por línea = bytes (splitteando en \n\r\x0c como el oráculo).
rival CODEPOINTS: ancho por línea = cuenta de codepoints (idem).
rival WCWIDTH:    ancho por código Unicode (EAW; Cc/Cf/Cn/Cs/Co/Mn→0; jamo conjoining→0; soft hyphen→1;
                  TAB avanza al siguiente stop de 8; resuelve igual los splits de línea).

La observación proviene exclusivamente de la matriz sellada matrix_native_L_utf8.txt.
El rival implícitamente "preferido" por el oráculo es WCWIDTH; la prueba lo DEMUESTRA
por contradicción de los otros rivales, no por autoridad del autor.
"""
import sys, os, unicodedata
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.mente import mente_cycle, select_discriminating_inputs, RivalHypothesis

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evidence" / "r3" / "wc" / "cases_L_utf8_seed20261123.txt"
MATRIX = ROOT / "evidence" / "r3" / "wc" / "matrix_native_L_utf8.txt"

def _unescape(s: str) -> bytes:
    out, i = [], 0
    while i < len(s):
        if s[i] == '\\' and s[i + 1] == 'x':
            out.append(int(s[i + 2:i + 4], 16)); i += 4
        else:
            out.append(ord(s[i])); i += 1
    return bytes(out)

def _lines(cps: str):
    parts = [cps]
    for cut in '\n\r\x0c':
        parts = sum((p.split(cut) for p in parts), [])
    return parts

def _width_piece(piece: str) -> int:
    w = 0
    for ch in piece:
        if ch == '\t':
            w = ((w // 8) + 1) * 8
            continue
        cp = ord(ch)
        if 0x1160 <= cp <= 0x11FF:
            continue          # jamo conjoining no avanza celda
        if cp == 0x00AD:
            w += 1
            continue          # quirk medido en el oráculo sellado
        if unicodedata.combining(ch) != 0:
            continue
        if unicodedata.category(ch)[0] == 'C':
            continue
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ('W', 'F') else 1
    return w

def _wcwidth(cps: str) -> int:
    return max((_width_piece(p) for p in _lines(cps)), default=0)

def _by_bytes(x):
    return max((len(p.encode('utf-8')) for p in _lines(x)), default=0)

def _by_codepoints(x):
    return max((len(p) for p in _lines(x)), default=0)

def _by_wcwidth(x):
    return _wcwidth(x)

def _load():
    cases = open(CASES, 'rb').read().decode('latin1').splitlines()
    exp = open(MATRIX, 'rb').read().decode('latin1').splitlines()
    cps = []
    for raw in cases:
        try:
            cps.append(_unescape(raw).decode('utf-8'))
        except UnicodeDecodeError:
            cps.append(None)
    return cps, exp

def _cands(cps):
    return [{"cps": c, "case_id": i} for i, c in enumerate(cps) if c is not None]

def test_wcwidth_model_reproduces_sealed_oracle():
    cps, exp = _load()
    good = sum(
        1 for case, e in zip(cps, exp)
        if case is not None and _wcwidth(case) == int(e.strip())
    )
    assert good == len(exp) == 1523, f"wcwidth debe reproducir el oráculo sellado en {len(exp)} casos, obtuve {good}"

def test_mente_refutes_bytes_and_codepoints_rivals():
    cps, exp = _load()
    cands = _cands(cps)
    hyps = [
        RivalHypothesis(id="BYTES", property_name="wc -L por bytes",
                        claim="wc -L cuenta bytes por línea",
                        predict=lambda x: _by_bytes(x["cps"]), domain={"corpus": "seed20261123"}),
        RivalHypothesis(id="CODEPOINTS", property_name="wc -L por codepoints",
                        claim="wc -L cuenta codepoints por línea",
                        predict=lambda x: _by_codepoints(x["cps"]), domain={"corpus": "seed20261123"}),
        RivalHypothesis(id="WCWIDTH", property_name="wc -L por EAW/Unicode",
                        claim="wc -L cuenta EAW/Unicode según reglas de anchura",
                        predict=lambda x: _by_wcwidth(x["cps"]), domain={"corpus": "seed20261123"}),
    ]
    rep = mente_cycle(hyps, cands, target_binary=str(ROOT / "wc" / "src" / "wc_width_table_gen.h"),
                      target_runner=lambda x: int(exp[x["case_id"]].strip()))
    assert "BYTES" in rep["refuted"]
    assert "CODEPOINTS" in rep["refuted"]
    assert "WCWIDTH" in rep["surviving"]
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "PROVEN" not in str(rep)

def test_mente_twin_wcwidth_indistinguishable():
    cps, exp = _load()
    cands = _cands(cps)
    hyps = [
        RivalHypothesis(id="WCWIDTH", property_name="f", claim="wcwidth",
                        predict=lambda x: _by_wcwidth(x["cps"]), domain={"corpus": "seed20261123"}),
        RivalHypothesis(id="WCWIDTH2", property_name="f", claim="gemelo de wcwidth",
                        predict=lambda x: _by_wcwidth(x["cps"]), domain={"corpus": "seed20261123"}),
    ]
    rep = mente_cycle(hyps, cands, target_binary=str(ROOT / "wc" / "src" / "wc_width_table_gen.h"),
                      target_runner=lambda x: int(exp[x["case_id"]].strip()))
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "limitacion" in rep
