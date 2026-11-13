#!/usr/bin/env python3
"""gen_fold_cases.py — generador determinista de corpus para R3-fold (etapa 3).
Emite A y B por linea: A es el texto de entrada escapado; B la salida de fold -w 4 escapada.
Uso: python3 gen_fold_cases.py <seed> <count>"""
import random, sys, subprocess

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261113
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
W = 4
rng = random.Random(SEED)

CLASSES = {
    "ascii": list(range(0x20, 0x7F)),
    "ascii_low": [0x30, 0x31, 0x41, 0x61, 0x2D, 0x2E],
    "combining": [0x0300, 0x0301, 0x0302, 0x0327],
    "cjk": [0x4E2D, 0x6C34, 0x3042, 0x31FF, 0x1100, 0xAC00, 0xD55C],
    "conjoining": [0x1160, 0x1161, 0x11A8, 0x11BA],
    "fullwidth": [0xFF01, 0xFF21, 0xFF61],
    "Cf": [0x2066, 0x2069, 0x200B],
    "word_1cell": [0x00A0, 0xAD],
}
WEIGHTS = [("ascii", 55), ("combining", 8), ("cjk", 12),
           ("conjoining", 5), ("fullwidth", 6), ("Cf", 6),
           ("word_1cell", 4), ("ascii_low", 4)]

def rand_text():
    n = rng.randint(0, 24)
    cps = []
    for _ in range(n):
        if rng.random() < 0.05:
            cps.append(0x09)  # tab
        picked = rng.choices([c for c, _ in WEIGHTS], weights=[w for _, w in WEIGHTS])[0]
        cps.append(rng.choice(CLASSES[picked]))
    return cps

def esc(buf: bytes) -> str:
    return ''.join(f'\\x{b:02x}' for b in buf)

buf_list = []
for _ in range(COUNT):
    cps = rand_text()
    buf_list.append(''.join(chr(cp) for cp in cps).encode('utf-8'))

for cp in (0x4E2D, 0x1100, 0xFF01, 0x0301, 0x00A0, 0x2069):
    for prefix in range(0, 9):
        buf_list.append(('A' * prefix + chr(cp) + 'B' * 3).encode('utf-8'))

out_path = sys.argv[3] if len(sys.argv) > 3 else None
lines = []
for raw in buf_list:
    p = subprocess.run(["/usr/bin/fold", "-w", str(W)], input=raw,
                       capture_output=True, timeout=10)
    assert p.returncode == 0, f"fold rc={p.returncode} on input {raw!r}"
    lines.append(esc(raw) + '\t' + esc(p.stdout))
text = '\n'.join(lines) + '\n'
if out_path:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text)
print(f"total={len(lines)} seed={SEED} width={W}", file=sys.stderr)
