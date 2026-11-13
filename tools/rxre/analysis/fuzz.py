"""M584 Fuzzing integrado minimal (mutador seed + clasificación).
Solo seeds reales sintéticos; clasificación crash/hang/ok por resultado func. Sin ejecutar binarios externos.
"""
from __future__ import annotations
import random

def mutate(seed: bytes, rng: random.Random) -> bytes:
    if not seed: return b""
    b = bytearray(seed)
    for _ in range(max(1, len(b)//8)):
        i = rng.randrange(len(b))
        b[i] ^= (1 << rng.randrange(8))
    return bytes(b)

def classify(result: str) -> str:
    if result.startswith("CRASH"): return "crash"
    if result.startswith("HANG"): return "hang"
    if result.startswith("OK"): return "ok"
    return "unknown"

def fuzz_once(seed: bytes, oracle_fn, rng: random.Random) -> str:
    m = mutate(seed, rng)
    return oracle_fn(m)
