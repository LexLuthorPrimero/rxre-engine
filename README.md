# RXRE engine

**RXRE is an AI-assisted reverse-engineering research project** focused on
*sealed, zero-tolerance differential verification* of binary reconstructions:
reconstruct a stripped binary's behavior from its bytes, seal a corpus and an
oracle against the real binary **before** judging the reconstruction, then
close the loop until the reconstruction matches the native binary on every
case in the corpus — or report why it cannot.

This repository is the complete **engine** of RXRE: the architecture code
(`tools/rxre/`), its test suites, and the sealed evidence of the two closed
milestones (`evidence/r3/`). It is published so an independent observer can
verify, falsify, or refute — not to advertise.

## Status, stated precisely

- Publication date: 2026-11-13 · License: **MIT** · Author: Lucas Cañete.
- **Third-party verification: NOT_EXECUTED.** All evidence so far was
  produced on one host, one UID, by the same author (and an AI agent working
  under the author's direction). No independent host/model/observer has
  confirmed the sealed claims yet.
- **PUERTA condition 3: PENDING_EXTERNAL_REVIEWER** (acceptance gate of the
  project remains open by design — the gate requires a human reviewer with
  no participation in the work).
- Two milestones are sealed with zero divergencies: `filenvercmp`
  (`/usr/bin/ls`, GNU coreutils 9.10) and `wc`
  (`/usr/bin/wc`, GNU coreutils 9.10), LC_ALL=C and UTF-8. See
  `evidence/r3/EXPEDIENTE_R3.md` for full records, seal-before-reveal
  protocol and limitations. The `wc` milestone now covers: C locale
  (default L/W/B, flags, `-m` ≡ `-c`, `-L`, byte-audit 256/256) and
  UTF-8 (`-m` multibyte = codepoints, and `-L` with a full width table,
  verified 1:1 against glibc `wcwidth(3)` on all 292,531 assigned
  codepoints). Third-party verification of any of these remains
  NOT_EXECUTED.
- The Python test suites pass in a fresh clone of this repository (see
  *Verify it yourself* below). Passing tests demonstrate internal
  consistency of the engine; they do **not** validate binary
  reconstructions, and that is not claimed.
- No MMIO, no `/dev/mem`, no `root`, no `--auto`, `autonomous_loop=False`,
  `max_iter=1` by default. GPU access is restricted to shader execution via
  Vulkan/SPIR-V (`require_gpu()`); all other hardware access is off the table.
- This is a **research engine**, not a production reverse-engineering
  service. Reconstructions are semantic contracts verified under specific
  corpora and locales, not drop-in replacements.

## Layout

```
tools/rxre/        engine source (arquitectura, core, verifier, api, tests)
tools/rxre/tests/  test suites (integrity, contract, reproducibility, v3…)
evidence/r3/       sealed R3 record: corpora, reconstruction, seal logs,
                   reconstruction-vs-native matrices, work journals
docs/              method identity documents (ESENCIA, PROCEDENCIA, LIMITACIONES…)
audit/evidence/    the two evidence records referenced by the integrity suite
```

## Verify it yourself (about 10 minutes)

```sh
git clone https://github.com/LexLuthorPrimero/rxre-engine
cd rxre-engine
python3 -m pytest \
  tools/rxre/tests/test_integridad_adv_final.py \
  tools/rxre/tests/test_contrato_uniforme.py \
  tools/rxre/tests/test_reproducibilidad_end2end.py \
  tools/rxre/tests/test_semantica_estructural_contraste.py \
  tools/rxre/tests/test_arquitectura_v3_01_contracts.py \
  tools/rxre/tests/test_arquitectura_v3_02_v3.py \
  tools/rxre/tests/test_arquitectura_v3_03_mutacion.py -q
```

Expected on a stock Python 3 + pytest 8/9 install: all suites pass
(8/8, 5/5, 2/2, 5/5, 35, 55, 7/7 respectively). If they do not, either the
claim above was defeated (valuable — report it) or the environment differs;
both outcomes are informative.

Reconstruction-verify the sealed oracle against the native binary:

```sh
cd evidence/r3

# public, self-contained verifier (recommended path):
git clone https://github.com/LexLuthorPrimero/rxre-cleanroom
cd rxre-cleanroom && gcc -std=c11 -O2 -o /tmp/verify_f \
  harness/verify_recon.c src/filenvercmp.c && \
  /tmp/verify_f oracle/cases_seed20261112.txt oracle/matrix_native.txt

# the seal logs under evidence/r3/records/ and evidence/r3/EXPEDIENTE_R3.md
# document the full differential loop (25,468 -> 1,014 -> 791 -> ... -> 0).
```

## Not in this repository (on purpose)

- No SQLite databases (live project state is private; the two evidence
  records referenced by the integrity suite are the only ones included).
- No third-party code (no kernel source, no emulators, no vendor copies,
  no proprietary binaries).
- No private intermediate work (`/tmp/rxre-r3/` scratch, backups, `tool-output`).
- No GPU MMIO/`debugfs`/root automation, and none will be added.

## Siblings

- https://github.com/LexLuthorPrimero/rxre-cleanroom — public sealed package
  (MIT): the canonical, self-contained way to verify the reconstructions.
- Issue #1 of that repository is the blind-verification call that decides
  whether the project's primary claim stands.

## License and credit

MIT. See `LICENSE`.

RXRE is an independent project. It is not affiliated with GNU, the Linux
kernel team, AMD, or the REA project. The work was developed by a human
owner with AI-assisted tooling (OpenCode agents). Human ownership of the
claims, the auditability standard and the PUERTA gate rests with Lucas
Cañete.
