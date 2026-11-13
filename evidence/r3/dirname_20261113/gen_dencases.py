#!/usr/bin/env python3
"""gen_dencases.py — generador determinista de corpus para R3-dirname (etapa 5-bis).
Propiedad acotada: GNU dirname — directorio padre acotado.
Emite A\\tB: A = input raw escapado, B = output de /usr/bin/dirname <A> escapado."""
import random, sys, subprocess

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261113
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
rng = random.Random(SEED)

NAME_PARTS = [
    'a', 'b', 'c', 'ab', 'abc', 'x1', '.local', 'foo', 'bar', 'baz',
    'a', 'x', 'y', 'z', 'name', 'dir2', 'x.c',
]
SEG = list(range(0x20, 0x7E))   # printable ASCII, no '/'
UNI_SEG = [0x4E2D, 0x6C34, 0x3042, 0x1100, 0x1160, 0xFF01]

def rand_seg():
    r = rng.random()
    if r < 0.55:
        n = rng.randint(1, 10)
        return ''.join(rng.choice(NAME_PARTS + ['x', 'y', 'z', '1', '0']) for _ in range(n)).encode()
    if r < 0.75:
        return bytes([rng.choice([c for c in range(0x61, 0x7B)] + [0x30 + i for i in range(10)]) for _ in range(rng.randint(1, 12))])
    if r < 0.85:
        seg = ''.join(rng.choice(['中', '水', 'あ', 'ᄀ', 'ᅡ', '！']) for _ in range(rng.randint(1, 6)))
        return seg.encode('utf-8')
    if r < 0.95:
        return ('a' + '.' * rng.randint(1, 6) + 'b').encode()
    return b'.'

def rand_path():
    kind = rng.random()
    trailing = rng.choices([0, 1, 2, 3], weights=[70, 12, 10, 8])[0]
    if kind < 0.08:
        path = ''.join(['/'] * rng.randint(1, 3))
    elif kind < 0.15:
        path = './'
    elif kind < 0.22:
        path = '.'
    elif kind < 0.35:
        path = '/' + '/'.join(rand_seg().decode('utf-8', errors='replace') for _ in range(rng.randint(1, 5)))
    elif kind < 0.50:
        path = '/' + '/'.join((rand_seg().decode('utf-8', errors='replace')) for _ in range(rng.randint(1, 6)))
    elif kind < 0.65:
        path = '/' + '/'.join(rand_seg().decode('utf-8', errors='replace') for _ in range(rng.randint(0, 7)))
    elif kind < 0.78:
        path = '/'.join(rand_seg().decode('utf-8', errors='replace') for _ in range(rng.randint(1, 5)))
    else:
        segs = [rand_seg().decode('utf-8', errors='replace') for _ in range(rng.randint(1, 6))]
        path = ('/' + '/'.join(segs)) if rng.random() < 0.7 else '/'.join(segs)
    path += '/' * trailing
    return path

def esc(b: bytes) -> str:
    return ''.join(f'\\x{x:02x}' for x in b)

cases = set()
for _ in range(COUNT):
    cases.add(rand_path())
# boundary buckets
for base in ['/a/b/c', '/', '.', 'foo/bar', './x', '//a//b//', '/a//b', '///x/', './', '.',
             'abc/def/ghi', '/a', './/', '/one/two/three/four/', '//a//b//c//']:
    for trail in ['', '/', '//', '///']:
        cases.add(base + trail)

seen = set()
n = 0
with open(sys.argv[3], 'w', encoding='latin1') as f:
    for raw_path in list(cases):
        p = subprocess.run(['/usr/bin/dirname', raw_path], capture_output=True, timeout=5)
        assert p.returncode == 0, (p.returncode, p.stderr)
        rb = raw_path.encode('utf-8')
        cb = p.stdout.decode('utf-8').rstrip('\n').encode('utf-8')
        f.write(esc(rb) + '\t' + esc(cb) + '\n')
        n += 1
print(f"total={n} seed={SEED}", file=sys.stderr)
