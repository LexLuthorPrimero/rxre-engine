#!/usr/bin/env python3
"""DISCOVERY etapa 6 — integración sobre un binario real (el /usr/bin/basename).

No verifica que el discovery RECONSTRUIRÍA basename correctamente — eso es exactamente
lo que todavía falta. Verifica:
- No pica un binario y explota/segfaultea.
- Elegirá un FUNCTION_CANDIDATE con cfg_blocks>0.
- No importa perfiles ls/grep _M263_*.
- Si el binary está desarmado y no hay rodata literals, cae limpio a NOT_DETERMINED.
"""
import sys, os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import pytest
from rxre.semantic.discovery import discover_unknown_function

BASENAME = "/usr/bin/basename"

def test_discovery_real_binary_does_not_crash():
    res = discover_unknown_function(BASENAME, timeout=90)
    assert res["status"] in ("RIVALS", "NOT_DETERMINED")
    cand = res.get("candidate") or {}
    if res["status"] == "RIVALS":
        assert cand.get("basic_blocks", 0) >= 1
    assert res["_no_profile_imported"] is True
    assert res["semantics_status"] == "NOT_DETERMINED"

def test_discovery_on_empty_binary_path():
    res = discover_unknown_function("/nonexistent/path/that/never/exists.elf", timeout=30)
    assert res["status"] in ("RIVALS", "NOT_DETERMINED", "NO_FUNCTION_CANDIDATES")
    assert res["semantics_status"] == "NOT_DETERMINED"
