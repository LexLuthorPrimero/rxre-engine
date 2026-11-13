#!/usr/bin/env python3
"""MENTE etapa 3 — rivalidad BYTES / codepoints / WCWIDTH sobre el corpus sellado de fold (gen 13).

rival BYTES:       cuenta bytes/casos (cada byte vale 1, avance al wrap); no maneja EAW/combinantes.
rival CODEPOINTS:  cuenta codepoints (todos = 1); ignora combinantes/tab/wide.
rival WCWIDTH:     EAW W/F=2; Mn/Cc/Cn/Cs/Co→0; jamo conjoining U+1160-11FF→0; soft hyphen quirk=1;
                   Tab→avance al siguiente stop de 8; salto de línea ANTES del cp que exceda w
                   con contenido no vacío; línea vacía puede desbordarse.
La observación proviene exclusivamente de la matriz sellada (campo B del corpus).
"""
import sys, os, unicodedata, json
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.mente import mente_cycle, select_discriminating_inputs, RivalHypothesis

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "evidence" / "r3" / "fold_20261113" / "cases_fold_seed20261113.txt"

def _unescape(s: str) -> bytes:
    o, i = b'', 0
    while i < len(s):
        if s[i] == '\\' and s[i + 1] == 'x':
            o += bytes([int(s[i + 2:i + 4], 16)]); i += 4
        else:
            o += s[i].encode('latin1'); i += 1
    return o

def _lines(cps: str):
    parts = [cps]
    for cut in '\n\r\x0c':
        parts = sum((p.split(cut) for p in parts), [])
    return parts

def _width_piece(piece: str) -> int:
    w = 0
    for ch in piece:
        if ch == '\t':
            w = ((w // 8) + 1) * 8; continue
        cp = ord(ch)
        if 0x1160 <= cp <= 0x11FF: continue
        if cp == 0x00AD: w += 1; continue
        if unicodedata.combining(ch) != 0: continue
        if unicodedata.category(ch)[0] == 'C': continue
        if unicodedata.east_asian_width(ch) in ('W', 'F'): w += 2
        else: w += 1
    return w

def _wcwidth(cps: str) -> int:
    """Máximo cell-width por línea (para discriminación alternativa)."""
    parts = cps.split('\n') if cps else ['']
    return max((_width_piece(p) for p in parts), default=0)

def _by_bytes(x):
    """bytes/`w` wrapping simulado (modelo ingenuo): cuenta bytes y rompe cada w bytes."""
    lines = _lines(x["cps"])
    w = 4
    out = []
    for piece in lines:
        b = piece.encode('utf-8')
        col = 0
        content = False
        for i, byte in enumerate(b):
            if col + 1 > w and content:
                out.append('\n'); col = 0; content = False
            out.append(chr(byte)); col += 1; content = True
        out.append('\n')
    return ''.join(out).rstrip('\n') + ('\n' if out and out[-1] == '\n' else '')

def _by_codepoints(x):
    lines = _lines(x["cps"])
    w = 4
    out = []
    for piece in lines:
        col = 0
        content = False
        for ch in piece:
            if col + 1 > w and content:
                out.append('\n'); col = 0; content = False
            out.append(ch); col += 1; content = True
        out.append('\n')
    return ''.join(out).rstrip('\n') + ('\n' if out and out[-1] == '\n' else '')

def _by_wcwidth(x):
    """Función WCWIDTH (construir la salida real del wrap conforme al modelo sellado)."""
    w = 4
    out = []
    col = 0; line_has_content = False; i = 0
    src = x["cps"]
    while i < len(src):
        ch = src[i]
        if ch == '\t':
            target = ((col + 1 + 7) // 8) * 8
            if target > w and line_has_content:
                out.append('\n'); col = 0; line_has_content = False; target = 8
            out.append('\t'); col = target; line_has_content = True; i += 1; continue
        if ch == '\n':
            out.append('\n'); col = 0; line_has_content = False; i += 1; continue
        cp = ord(ch)
        if 0x1160 <= cp <= 0x11FF: adv = 0
        elif cp == 0x00AD: adv = 1
        elif unicodedata.combining(ch) != 0: adv = 0
        elif unicodedata.category(ch)[0] == 'C': adv = 0
        elif unicodedata.east_asian_width(ch) in ('W', 'F'): adv = 2
        else: adv = 1
        if col + adv > w and line_has_content:
            out.append('\n'); col = 0; line_has_content = False
        out.append(ch); col += adv; line_has_content = True; i += 1
    return ''.join(out)

def _load():
    out = []
    for raw in open(CASES, 'rb').read().decode('latin1').splitlines():
        a, b = raw.split('\t', 1)
        try:
            cps = _unescape(a).decode('utf-8')
        except UnicodeDecodeError:
            continue
        out.append((cps, _unescape(b)))
    return out

def test_python_wcwidth_model_reproduces_sealed_oracle_exactly():
    cases = _load()
    bad = [a for a, b in cases if _by_wcwidth({"cps": a}).encode('utf-8') != b]
    assert not bad, f"{len(bad)} casos difieren: {[repr(c) for c in bad[:3]]}"
    assert len(cases) > 2000

def test_ente_fold_refutes_bytes_and_codepoints():
    cases = _load()
    cands = [{"cps": a, "case_id": i} for i, (a, _) in enumerate(cases)]
    hyps = [
        RivalHypothesis(id="BYTES", property_name="fold por bytes",
                        claim="fold wrapiza por bytes, no por cell width",
                        predict=lambda x: _by_bytes(x), domain={"corpus": "seed20261113"}),
        RivalHypothesis(id="CODEPOINTS", property_name="fold por codepoints",
                        claim="fold wrapiza por codepoints, no por cell width",
                        predict=lambda x: _by_codepoints(x), domain={"corpus": "seed20261113"}),
        RivalHypothesis(id="WCWIDTH", property_name="fold por cell width",
                        claim="fold wrapiza por cell width (tab stop 8, EAW)",
                        predict=lambda x: _by_wcwidth(x), domain={"corpus": "seed20261113"}),
    ]
    expected = [b for _, b in cases]
    rep = mente_cycle(hyps, cands, target_binary=CASES.as_posix(),
                      target_runner=lambda x: expected[x["case_id"]].decode('utf-8'))
    assert "BYTES" in rep["refuted"]
    assert "CODEPOINTS" in rep["refuted"]
    assert "WCWIDTH" in rep["surviving"]
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "PROVEN" not in str(rep)

def test_twin_wcwidth_indistinguishable():
    cases = _load()
    cands = [{"cps": a, "case_id": i} for i, (a, _) in enumerate(cases)]
    hyps = [
        RivalHypothesis(id="WC", property_name="f", claim="w",
                        predict=lambda x: _by_wcwidth(x), domain={"corpus": "seed20261113"}),
        RivalHypothesis(id="WC2", property_name="f", claim="w gemelo",
                        predict=lambda x: _by_wcwidth(x), domain={"corpus": "seed20261113"}),
    ]
    expected = [b for _, b in cases]
    rep = mente_cycle(hyps, cands, target_binary=CASES.as_posix(),
                      target_runner=lambda x: expected[x["case_id"]].decode('utf-8'))
    assert rep["epistemic_status"] == "NOT_DETERMINED"
    assert "limitacion" in rep
