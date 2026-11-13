#!/usr/bin/env python3
"""R3-Fase2 hito 15 — corpus para wc --files0-from en es_AR.utf8.
Línea: "<name> \\t <contenido hexa-escapado>" — una entrada por archivo del grupo.
Nombre: ASCII imprimible sin '/' ni espacios ni caracteres de control; contenido UTF-8."""
import random, sys
SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 20261127
random.seed(SEED)
PIECES = [b'a',b'b',b'c',b'0',b'9',b' ',b'\t',b'\n',b'\r',b'\x0b',b'\x0c',
          b'\xc3\xa9',b'\xc2\xa0',b'\xe2\x82\xac',b'\xe4\xb8\xad',b'\xe2\x80\x93',
          b'\xf0\x9f\x98\x80',b'\xcc\x81',b'\xe0\xa1\xa8',b'\xd0\xbf',b'\xe4\xb8\xad']
NAME_CHARS = list('abc123') + ['_','-']

def esc(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b < 127 and b not in (0x5c,):
            out.append(chr(b))
        elif b == 0x09: out.append('\\t')
        elif b == 0x0a: out.append('\\n')
        else: out.append('\\x%02x' % b)
    return ''.join(out)

entries = set()
i = 0
while len(entries) < 3000:
    content = b''.join(random.choice(PIECES) for _ in range(random.randint(0, 24)))
    name = 'g%05d_%s_%s.txt' % (i, ''.join(random.choice(NAME_CHARS) for _ in range(4)),
                                ''.join(random.choice(NAME_CHARS) for _ in range(4)))
    i += 1
    entries.add((name, content))
entries = sorted(entries, key=lambda t: t[0])
with open(sys.argv[2], 'w', newline='\n', encoding='ascii') as f:
    for name, content in entries:
        f.write(name + '\t' + esc(content) + '\n')
print(f'files={len(entries)}', file=sys.stderr)
