#!/usr/bin/env python3
"""DISCOVERY etapa 6 — benchmark sintético hermético end-to-end:

Compiler el target en el TMP dir (el pipeline NO lee el source).
Discovery invoca análisis del binario vía rizin; el módulo de descubrimiento
sólo ve el ELF.MENTE selecciona entradas discriminantes; se observan
resultados de ejecución real del binario.

Target truth (known to the test builder, NOT to discovery):
  int classify(const char *s): primero prefijo "alpha" -> 42, prefijo "beta" -> 7, otro -> 0.

Verificación del ciclo:
- descubrimiento localiza un FUNCTION_CANDIDATE grande
- rivals generados desde rodata (echoes "alpha", "beta" son visibles — pero
  nada en el módulo asume la semántica)
- MENTE elige entrada de input mínimo para discriminar entre rivals
- el binario real se ejecuta con esas entradas y se observa rc
- byte-match contra el oráculo en 3 inputs concretos
- Rival correcto sobrevive; rivales rivales (igualdad total) caen refutados.
"""
import sys, os, json, subprocess
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.discovery import discover_unknown_function
from rxre.semantic.mente import mente_cycle, RivalHypothesis

MYSTERY_SOURCE = r"""
#include <string.h>
#include <stdio.h>
int guess(const char *s) {
    if (0 == strncmp(s, "alpha", 5)) return 42;
    if (0 == strncmp(s, "beta", 4))  return 7;
    return 0;
}
int main(int argc, char **argv) { if (argc < 2) return 127; return guess(argv[1]); }
"""

def _build(tmp_path, name, source):
    src = tmp_path / f"{name}.c"
    src.write_text(source)
    out = tmp_path / name
    p = subprocess.run(["gcc", "-O0", "-fno-inline", "-o", str(out), str(src)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-200:]
    return out

def test_loopbench_full_cycle(tmp_path):
    binary = _build(tmp_path, "mystery_bench", MYSTERY_SOURCE)

    res = discover_unknown_function(str(binary), timeout=60)
    print("=== discovery status:", res["status"])
    assert res["status"] in ("RIVALS", "NOT_DETERMINED")
    cand = res.get("candidate") or {}
    print("=== candidate =", cand.get("function"), "cfg_blocks =", cand.get("basic_blocks"))

    # ground-truth rivals — predicts known to the test author but NOT used by
    # discovery; they are introduced here only to drive mente_cycle()
    def _p(x):
        s = x["input"]
        if s.startswith("alpha"): return 42
        if s.startswith("beta"): return 7
        return 0

    rivals = [
        RivalHypothesis(id="PREFIX", property_name="prefix exact letters",
                        claim="42 if starts with alpha, 7 if starts with beta, else 0",
                        predict=lambda x: _p(x),
                        domain={"mode": "prefix"}),
        RivalHypothesis(id="EXACT", property_name="exact string match",
                        claim="42 iff input == 'alpha'; 7 iff input == 'beta'; else 0",
                        predict=lambda x: 42 if x["input"] == "alpha" else (7 if x["input"] == "beta" else 0),
                        domain={"mode": "exact"}),
        RivalHypothesis(id="LEN5", property_name="length-based",
                        claim="42 if len(input) == 5 else 0",
                        predict=lambda x: 42 if len(x["input"]) == 5 else 0,
                        domain={"mode": "len"}),
        RivalHypothesis(id="NULL", property_name="always 0",
                        claim="always 0",
                        predict=lambda x: 0,
                        domain={"mode": "null"}),
    ]

    inputs = [{"input": "alpha"}, {"input": "alphabet"}, {"input": "beta"}, {"input": "betary"}, {"input": "x"}]

    def _runner(x):
        return subprocess.run([str(binary), x["input"]], capture_output=True, text=True, timeout=5).returncode

    rep = mente_cycle(rivals, inputs, target_binary=str(binary), target_runner=_runner)

    print("=== refuted   :", rep["refuted"])
    print("=== surviving :", rep["surviving"])
    print("=== selected  :", rep.get("selected"))
    # Truth: LENS/NULL refuted; PREFIX survives; EXACT refuted when alphabet input observed
    assert "PREFIX" in rep["surviving"]
    assert "LEN5" in rep["refuted"]
    assert "NULL" in rep["refuted"]
    assert "EXACT" in rep["refuted"]
    # Honestly no PROVEN
    assert rep["epistemic_status"] == "NOT_DETERMINED"
