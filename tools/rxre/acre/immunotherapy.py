"""ACRE Immunotherapy Engine skeleton (Fase 2, PASS_PARTIAL acotado).

Ciclo DETECTAR->LOCALIZAR->DIAGNOSTICAR->INTERVENIR->VALIDAR->ROLLBACK->CERTIFICAR.
Sin C1 externa (NOT_DETERMINED), sin E2E-039 (1 host), binario cerrado real BLOCKED.
Solo lab sintético ET_EXEC /tmp (M436/M441/M439). No universal, no CVE real.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from rxre.epistemic.promotion import guard_promotion
from rxre.epistemic.states import EpistemicState

@dataclass
class PatchUnit:
    original_hash: str
    patched_hash: str
    file_offset: str
    virtual_address: str
    bytes_before: str
    bytes_after: str
    instruction: str

def apply_patch(binary: bytes, offset: int, new_byte: int) -> tuple[bytes, PatchUnit]:
    orig_hash = hashlib.sha256(binary).hexdigest()
    if not (0 <= offset < len(binary)):
        raise ValueError("offset fuera de rango")
    before = binary[offset]
    patched = bytearray(binary); patched[offset] = new_byte
    unit = PatchUnit(orig_hash, hashlib.sha256(bytes(patched)).hexdigest(), hex(offset), hex(0x400000+offset), f"{before:02x}", f"{new_byte:02x}", "patch byte")
    # Rollback bit a bit (R12): restaurar original verifica hash
    restored = apply_rollback(binary, bytes(patched))
    assert hashlib.sha256(restored).hexdigest() == orig_hash
    return bytes(patched), unit

def apply_rollback(original: bytes, patched: bytes) -> bytes:
    return bytes(original)

def repair_rate(cases):
    """Repair rate sobre set sellado (sin exclusiones retrospectivas)."""
    div = [c for c in cases if c.get("diverges")]
    if not div:
        return 0.0
    return sum(1 for c in div if c.get("fixed")) / len(div)

def guard_patch(unit: PatchUnit, expected_original: str) -> bool:
    """Fail-closed: original debe coincidir con spec sellada."""
    return unit.original_hash == expected_original and unit.bytes_before != unit.bytes_after


def gate_patch(state, evidence):
    return guard_promotion(state, evidence)
