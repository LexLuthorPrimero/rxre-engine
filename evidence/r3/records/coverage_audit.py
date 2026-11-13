#!/usr/bin/env python3
"""R3 corpus composition audit (seed 20261112/20261113).

Quantifies what the sealed filenvercmp corpora actually exercise — and what it
does NOT — so '0 divergences on our corpus' is stated against measured coverage,
not vibes. Never claims exhaustiveness; it's a composition/hiding description.

Input format per line: `<nameA>\\t<nameB>` with \\xHH escaping of non-printable bytes.
Matrix format per line: int in {-1, 0, 1} assertion by the native oracle.
"""
import sys
def unesc(s):
    out = bytearray(); i = 0
    while i < len(s):
        if s[i] == '\\' and s[i+1] == 'x': out.append(int(s[i+2:i+4], 16)); i += 4
        else: out.append(ord(s[i])); i += 1
    return bytes(out)

def analyze(cases_path, matrix_path, label=''):
    cases = [l.rstrip('\n') for l in open(cases_path)]
    matrix = [int(l) for l in open(matrix_path)]
    assert len(cases) == len(matrix)
    total = len(cases)
    feats = dict(utf8=0, tilde=0, space=0, dot_lead=0, prefix_rel=0,
                 numeric_only=0, digit_heavy=0, long_ver=0, empty=0)
    outcome = {}
    sign_count = {-1: 0, 0: 1, 1: 0}
    sign_count = {-1: 0, 0: 0, 1: 0}
    longest = 0
    for line, exp in zip(cases, matrix):
        a_raw, b_raw = line.split('\t', 1)
        a, b = unesc(a_raw), unesc(b_raw)
        longest = max(longest, len(a), len(b))
        if any(x >= 0x80 for x in a) or any(x >= 0x80 for x in b): feats['utf8'] += 1
        if b'~' in a or b'~' in b: feats['tilde'] += 1
        if b' ' in a or b' ' in b: feats['space'] += 1
        if a.startswith(b'.') or b.startswith(b'.'): feats['dot_lead'] += 1
        if a.startswith(b) or b.startswith(a): feats['prefix_rel'] += 1
        da, db = a.isdigit(), b.isdigit()
        if da and db: feats['numeric_only'] += 1
        dig = sum(1 for c in a + b if 0x30 <= c <= 0x39) / max(1, len(a) + len(b))
        if dig > 0.8: feats['digit_heavy'] += 1
        if len(a) > 32 or len(b) > 32: feats['long_ver'] += 1
        if len(a) == 0 or len(b) == 0: feats['empty'] += 1
        outcome[exp] = outcome.get(exp, 0) + 1
        sign_count[(exp > 0) - (exp < 0)] += 1
    print(f'== {label} ({cases_path})')
    print(f'total_cases={total} longest_name_bytes={longest}')
    for k, v in feats.items():
        print(f'  {k:14s} {v:6d}  ({100.0*v/total:.2f}%)')
    print(f'  unique return values: {len(outcome)} (unclamped deltas, e.g. -120, 97, 2)')
    print('  top-5 values (freq): ' + ', '.join(f'{v}:{c}' for v, c in sorted(outcome.items(), key=lambda kv: -kv[1])[:5]))
    print('  sign distribution:')
    for k in (-1, 0, 1):
        lab = {-1: 'negative', 0: 'equal', 1: 'positive'}[k]
        print(f'    {lab:9s} {sign_count.get(k, 0):6d}  ({100.0*sign_count.get(k, 0)/total:.2f}%)')

if __name__ == '__main__':
    base = sys.argv[1] if len(sys.argv) > 1 else '.'
    analyze(f'{base}/cases_seed20261112.txt', f'{base}/matrix_native.txt', 'seed 20261112')
    analyze(f'{base}/cases_seed20261113.txt', f'{base}/matrix_native_20261113.txt', 'seed 20261113')

