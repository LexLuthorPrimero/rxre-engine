#!/usr/bin/env python3
"""DISCOVERY — etapa 6 MENTE: generación de hipótesis rivales sobre un binario ELF real.

Objetivo: reconstruir semántica sobre artefactos SIN perfiles históricos (no hereda
konocimiento del ls ni del grep; no aplica perfiles _M263). Trabaja sólo con:

  1. Evidencia física: identificador sha256 del binario + recuperación de rodata strings.
  2. Reconocimiento estructural: funciones FUNCTION_CANDIDATE del reconstructor existente.
  3. Rivales generados a partir de literales visibles: modelos independientes para el mismo
     patrón de comportamiento (prefijo/exact/first-byte). Secuencialmente:
     a) se listan candidatos FUNCTION_CANDIDATE con balance size/basic_blocks;
     b) se generan >=3 rivals independientes sobre un literal candidato;
     c) la discriminación entre rivals solo ocurre con ejecución opt-in (mente_cycle);
     d) ningún rival puede elevarse a PROVEN — necesita tercera parte E2E-039.

Invariantes:
- No se importa ningún perfil experimental _M263_* / _M263_CAUSAL; no se hereda
  ningún conocimiento ls ni grep; esto será explícito: _no_profile_imported = True.
- Nunca se llama `PROVEN`; el estatus máximo alcanzable es NOT_DETERMINED (suele darse).
- Si falta un requisito (instrumento/runtime/predicción rival), el resultado es
  NOT_DETERMINED, no un error tragado.
- No se modifica el ELF target; toda observación es vía ejecución voluntaria.
"""
from __future__ import annotations

import hashlib, json, os, re, subprocess, sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, "..", ".."))
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from rxre.semantic.reconstructor import reconstruct
from rxre.semantic.mente import RivalHypothesis, select_discriminating_inputs, mente_cycle

_NO_PROFILE_IMPORTED = True  # marker; never contains ls/grep experiment IDs

def _sha256_file(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def _strings_rodata(binary_path: str, min_len: int = 4):
    try:
        p = subprocess.run(["strings", "-n", str(min_len), binary_path],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return []
    if p.returncode != 0:
        return []
    return [l for l in p.stdout.splitlines() if l]

def _pick_function_candidate(recon_votes: List[Dict]) -> Optional[Dict]:
    cand = [h for h in recon_votes if h.get("classification") == "FUNCTION_CANDIDATE"]
    if not cand:
        return None
    cand.sort(key=lambda h: (int(h.get("basic_blocks", 0) or 0),
                             int(h.get("size", 0) or 0)), reverse=True)
    return cand[0]

def _viable_literals(strings: List[str]) -> List[str]:
    out = []
    for s in strings:
        s = str(s)
        if not (3 <= len(s) <= 16):
            continue
        if not all(32 <= ord(c) < 127 for c in s):
            continue
        low = s.lower()
        if low in ("gnu", "libc", "usage", "name", "abort", "error", "error:", "warning"):
            continue
        out.append(s)
    return out[:8]

def _rivals_from_literal(literal: str) -> List[RivalHypothesis]:
    literal_b = literal.encode("utf-8", errors="replace")
    rs = []
    rs.append(RivalHypothesis(
        id=f"PREFIX({literal})",
        property_name=f"comparte prefijo con {literal!r}",
        claim=f"returns distinguishing tag iff input starts with '{literal}'",
        predict=lambda x, L=literal_b: 1 if bytes(x.get("input", b"")).startswith(L) else 0,
        domain={"mode": "prefix_startswith", "literal": literal}))
    rs.append(RivalHypothesis(
        id=f"EXACT({literal})",
        property_name=f"igualdad total con {literal!r}",
        claim=f"returns distinguishing tag iff input == '{literal}'",
        predict=lambda x, L=literal_b: 1 if bytes(x.get("input", b"")) == L else 0,
        domain={"mode": "exact_equality", "literal": literal}))
    rs.append(RivalHypothesis(
        id="FIRSTBYTE",
        property_name="clasifica por primer byte",
        claim="returns distinguishing tag based on input[0]",
        predict=lambda x: 1 if bytes(x.get("input", b""))[:1] in (b"a", b"A", b"b", b"B") else 0,
        domain={"mode": "first_byte_category"}))
    return rs

def discover_unknown_function(binary_path: str,
                              timeout: int = 120,
                              candidate_index: Optional[int] = None) -> Dict[str, Any]:
    """Descubre FUNCTION_CANDIDATE más grande y rivales semánticos.

    Devuelve dict:
    - status: RIVALS / NO_FUNCTION_CANDIDATES / NOT_DETERMINED
    - artifacts: {path, sha256, functions}
    - candidate: {function, offset, size, basic_blocks, ...}
    - rivals: [rivals with id, property_name, domain, prediction_spec]
    - evidence: {strings, rodata candidates, reason}
    - semantics_status: always NOT_DETERMINED
    - _no_profile_imported: True
    """
    recon = reconstruct(binary_path, backend_id="rizin", timeout=timeout) if os.path.isfile(binary_path) else {}
    cand_list = recon.get("hypotheses", []) if isinstance(recon, dict) else []
    arch = recon.get("artifact", {}) if isinstance(recon, dict) else {}
    if not cand_list:
        return {
            "status": "NO_FUNCTION_CANDIDATES",
            "artifact": arch,
            "target_sha256": _sha256_file(binary_path) if os.path.isfile(binary_path) else None,
            "recon": {"artifact": arch, "counts": recon.get("counts") if isinstance(recon, dict) else None},
            "_no_profile_imported": _NO_PROFILE_IMPORTED,
        }

    cand = cand_list[candidate_index] if candidate_index is not None and candidate_index < len(cand_list) else _pick_function_candidate(cand_list)
    strings = _strings_rodata(binary_path)
    literals = _viable_literals(strings)
    primary = literals[0] if literals else None
    rivals = _rivals_from_literal(primary) if primary else []

    return {
        "status": "RIVALS" if rivals else "NOT_DETERMINED",
        "artifact": arch,
        "target_sha256": _sha256_file(binary_path),
        "candidate": {
            "function": cand.get("function"),
            "offset": int(cand.get("offset") or 0),
            "size": int(cand.get("size") or 0),
            "basic_blocks": int(cand.get("basic_blocks") or 0),
            "nargs": cand.get("nargs"),
            "type": cand.get("type"),
            "selection_reason": cand.get("selection_reason"),
            "cfg_status": cand.get("cfg_status"),
            "evidence": cand.get("evidence"),
        } if cand else None,
        "literal": primary,
        "literals_visible": literals,
        "rivals": [{"id": r.id, "property_name": r.property_name,
                    "claim": r.claim, "domain": r.domain} for r in rivals],
        "semantics_status": "NOT_DETERMINED",
        "reason": "rivals generados desde literales visibles en rodata; experimento discriminante pendiente de ejecución ópt-in",
        "_no_profile_imported": _NO_PROFILE_IMPORTED,
    }
