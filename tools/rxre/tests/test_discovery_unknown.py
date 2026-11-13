#!/usr/bin/env python3
"""DISCOVERY — etapa 6 prueba-de-fuego (laboratorio hermético).

Construimos un binario desconocido (fuente NO conocida por el reconstruer;
fuente NO entregada al módulo de descubrimiento), aplicamos discovery + MENTE
sobre el literal visible en .rodata, y comprobamos que el modelo de prefijo
verdadero sobrevive mientras que los otros rivals caen refutados.

Esto NO afirma capacidad general de reconstrucción. Lo demostrado: al menosun
fall-through razonable de rivals con evidencia estructural sobre un binario
no preparado para este sistema ocurre. P0 permanece.
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
#include <stdlib.h>
int mystery(const char *s) {
    if (0 == strncmp(s, "alpha", 5)) return 42;
    if (0 == strncmp(s, "beta", 4))  return 7;
    return 0;
}
int main(int argc, char **argv) {
    if (argc < 2) return 127;
    return mystery(argv[1]);
}
"""

def _build_unknown(tmp_path):
    src = tmp_path / "mystery.c"
    src.write_text(MYSTERY_SOURCE)
    out = tmp_path / "mystery"
    p = subprocess.run(["gcc", "-O0", "-fno-inline", "-o", str(out), str(src)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-300:]
    return out

def _run_target(byte_inputs: bytes) -> int:
    chosen = Path(sys.argv[0]).temporary_directory if hasattr(sys.argv[0], 'temporary_directory') else None
    raise NotImplementedError

def test_discovery_unknown_binary_pipeline(tmp_path):
    binary = tmp_path / "mystery"
    src = tmp_path / "mystery.c"
    src.write_text(MYSTERY_SOURCE)
    p = subprocess.run(["gcc", "-O0", "-fno-inline", "-o", str(binary), str(src)],
                       capture_output=True, text=True)
    assert p.returncode == 0, p.stderr[-300:]

    res = discover_unknown_function(str(binary), timeout=60)
    assert res["status"] == "RIVALS", res
    assert res["candidate"] is not None
    # ground truth candidate must be the one containing mystery
    # literals visible in rodata must include alpha / beta
    literals = res["literals_visible"]
    assert any("alpha" in s.lower() for s in literals), literals
    assert any("beta" in s.lower() for s in literals), literals
    # _no_profile_imported must be True (this milestone does NOT consume ls/grep knowledge)
    assert res["_no_profile_imported"] is True
    assert res["semantics_status"] == "NOT_DETERMINED"

def test_full_cycle_discriminates_rivals(tmp_path):
    """Encuentra el candidato grande, obtiene rivals desde .rodata y discriminación MENTE."""
    binary = tmp_path / "mystery2"
    src = tmp_path / "mystery2.c"
    src.write_text(MYSTERY_SOURCE)
    p = subprocess.run(["gcc", "-O0", "-fno-inline", "-o", str(binary), str(src)],
                       capture_output=True, text=True)
    assert p.returncode == 0

    res = discover_unknown_function(str(binary), timeout=60)
    assert res["status"] == "RIVALS"

    # ground-truth rival (known to the lab compiler-time, NOT to discovery at runtime)
    def _bytes(x, L):
        return x["input"].encode("utf-8", errors="replace")
    rivals = [
        RivalHypothesis(id="PREFIX", property_name="prefix mystery",
                        claim="returns 42/7/0 by prefix",
                        predict=lambda x, bl=None: 42 if x["input"].startswith("alpha") else (7 if x["input"].startswith("beta") else 0),
                        domain={"mode": "prefix"}),
        RivalHypothesis(id="GT_LEN", property_name="length-based",
                        claim="returns 42 if len==5 readiness",
                        predict=lambda x: 42 if len(x["input"]) == 5 else 0,
                        domain={"mode": "length"}),
        RivalHypothesis(id="NULL", property_name="always zero",
                        claim="always 0",
                        predict=lambda x: 0,
                        domain={"mode": "null"}),
    ]

    inputs = [{"input": "alpha"}, {"input": "alphabet"}, {"input": "beta"}, {"input": "betap"}, {"input": "x"}]

    def _runner(x):
        out = subprocess.run([str(binary), x["input"]], capture_output=True, text=True, timeout=5)
        return out.returncode

    rep = mente_cycle(rivals, [x for x in inputs], target_binary=str(binary), target_runner=_runner)
    # rivals: PREFIX survives, GT_LEN and NULL refuted
    assert "PREFIX" in rep["surviving"], rep
    assert "GT_LEN" in rep["refuted"], rep
    assert "NULL" in rep["refuted"], rep
    # honesty: PREFIX never PROVEN
    assert rep["epistemic_status"] == "NOT_DETERMINED"
