#!/usr/bin/env python3
"""gen_tr_cases.py — generador determinista de corpus para R3-tr (etapa 5).
Propiedad reconstruida (acotada): colapso de runs consecutivos de byte 0x78 ('x') — squeeze.
Emite A\\tB donde A = input escapado, B = output de /usr/bin/tr -s x sobre A (también escapado).
Uso: python3 gen_tr_cases.py <seed> <count> <out-file>"""
import random, sys, subprocess

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261113
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
rng = random.Random(SEED)

ALPHABET = [0x61, 0x62, 0x63, 0x78, 0x09, 0x20, 0x0A, 0xAD, 0x4E2D.__int__(), 0x00AD]
# ^ bytes/uni de interés: a b c x TAB NBSP xatiil chars — todas bytes < 0x100 excepto CJK ✗ — keep bytes <256
ALPHABET_BYTES = [0x61, 0x62, 0x63, 0x78, 0x09, 0x20, 0xAD]

def rand_buf():
    n = rng.randint(0, 96)
    buf = bytearray()
    for _ in range(n):
        # sesgo fuerte hacia x para forzar runs
        r = rng.random()
        if r < 0.55:
            buf.append(0x78)          # x - fuerza runs frecuentes
        elif r < 0.70:
            buf.append(0x61)          # a
        elif r < 0.80:
            buf.append(0x62)          # b
        elif r < 0.86:
            buf.append(0x63)          # c
        elif r < 0.92:
            buf.append(0x20)          # space
        elif r < 0.96:
            buf.append(0x09)          # tab
        else:
            buf.append(0xAD)          # soft hyphen
    return bytes(buf)

def esc(buf: bytes) -> str:
    return ''.join(f'\\x{b:02x}' for b in buf)

cases = []
for _ in range(COUNT):
    cases.append(rand_buf())

# boundary buckets: runs of x of every length around wrap edges
for run in range(0, 13):
    cases.append(b'x' * run + b'y' + b'x' * run)

seen = []
with open(sys.argv[3], 'w', encoding='latin1') as f:
    for raw in cases:
        p = subprocess.run(['/usr/bin/tr', '-s', 'x'], input=raw,
                           capture_output=True, timeout=5)
        assert p.returncode == 0
        f.write(esc(raw) + '\t' + esc(p.stdout) + '\n')

print(f"total={len(cases)} seed={SEED}", file=sys.stderr)
