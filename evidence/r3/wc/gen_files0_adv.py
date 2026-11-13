#!/usr/bin/env python3
"""R3-Fase2 hito 17 — corpus adversarial para wc --files0-from (seed 20261128).
Objetivo: rodear los bordes — vacío, solo LF, CRLF, NUL-embebido, combinantes,
fullwidth, isolates, NBSP vs espacio, UTF-8 válido mixto."""
import random, sys
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261128
random.seed(SEED)
PIECES = [b'a',b'b',b'0',b'9',b' ',b'\t',b'\n',b'\r',b'\x0b',b'\x0c',b'\x00',
          b'\xc3\xa9',b'\xc2\xa0',b'\xe2\x82\xac',b'\xe4\xb8\xad',b'\xe2\x80\x93',
          b'\xf0\x9f\x98\x80',b'\xcc\x81',b'\xe0\xa1\xa8',b'\xd0\xbf',b'\xe4\xb8\xad',
          b'\xe3\x80\x80',b'\xe2\x81\xa6',b'\xe2\x81\xa9',b'\xef\xbc\xa1']
EDGES = [b'', b'\x0a', b'\x0d\x0a', b'\x00', b'\xff\n', b'\xc2\xa0\n',
         b'\x65\xcc\x81\n', b'\xcc\x81\n', b'\n\n\n', b'\x09\x09\n',
         b'\xcc\x81\xcc\x81\xcc\x81', b'a\xcc\x81b\xcc\x81c\n', b'\xef\xbc\xa1',
         b'\xe2\x81\xa6a\xe2\x81\xa9b\n', b'\xc3\x85ong\n', b'\xf0\x9f\x98\x80\n']
NAME_CHARS = list('abcxyz_0123456789-')

def esc(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b < 127 and b != 0x5c: out.append(chr(b))
        elif b == 0x09: out.append('\\t')
        elif b == 0x0a: out.append('\\n')
        elif b == 0x0b: out.append('\\v')
        elif b == 0x0c: out.append('\\f')
        elif b == 0x0d: out.append('\\r')
        else: out.append('\\x%02x' % b)
    return ''.join(out)

entries = []
for idx, edge in enumerate(EDGES):
    name = 'e_edge_%03d.txt' % idx
    entries.append((name, edge))
while len(entries) < 2200:
    content = b''.join(random.choice(PIECES) for _ in range(random.randint(0, 48)))
    name = 'a%05d_%s_%s.txt' % (len(entries) + 1000,
                                ''.join(random.choice(NAME_CHARS) for _ in range(5)),
                                ''.join(random.choice(NAME_CHARS) for _ in range(5)))
    entries.append((name, content))
random.shuffle(entries)
with open(sys.argv[2], 'w', newline='\n', encoding='ascii') as f:
    for name, content in entries:
        f.write(name + '\t' + esc(content) + '\n')
print(f'cases={len(entries)} files={len(entries)}', file=sys.stderr)
