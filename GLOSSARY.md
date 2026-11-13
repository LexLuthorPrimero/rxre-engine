# GLOSSARY — RXRE terminology

Terms used across this repository, in EN with ES equivalents.

**Seal-before-reveal (sellado antes de revelar)** — Protocol where a corpus and its expected
output are cryptographically hashed *before* the producing oracle is consulted; prevents
adaptive fitting. The producing run is genuinely part of the seal.

**Zero-tolerance differential verification (verificación diferencial a tolerancia cero)** — Any
single mismatch between reconstruction and native oracle is a refutation. No approximate pass,
no "within noise". After fix, the same corpus is re-run from scratch (both generations).

**Semantic contract (contrato semántico)** — A reconstruction claiming to reproduce the
*observable behavior* of a target binary under a sealed domain, not to port its disassembly 1:1.
Only the verified domain is claimed; everything else is out of scope and labeled as such.

**Oracle (oráculo)** — The real, stripped binary itself, used read-only (mmap) at verification
time to label the expected answers; never altered, never executed beyond that call pattern.

**Corpus sealed (corpus sellado)** — The set of test inputs, hashed and committed before any
analysis of the native outputs. Any change invalidates the seal.

**PUERTA / PUERTA condition 3 (PUERTA, condición 3)** — RXRE's internal acceptance gate.
Condition 3 requires the acceptance review to be performed by an independent human reviewer who
did not participate in the work; it is deliberately PENDING_EXTERNAL_REVIEWER — the author cannot
self-promote.

**R3** — The sealed-milestone verification cycle series (R1–R3). Each Rx closes one reconstruction
under zero-tolerance verification. R3 = the cycle that produced filenvercmp and wc milestones.

**LC_ALL / locales** — `LC_ALL=C`: POSIX minimal locale; `es_AR.utf8`: Spanish UTF-8 locale.
Both are claimed separately; no locale implies another.

**wcwidth(3) / East-Asian Wide** — glibc's per-codepoint display-cell width used by `wc -L`.
Ranges and exceptions (East-Asian Wide, combining marks, Hangul conjoining jamo, visible Cf) are
documented and verified 1:1 against glibc on all 292,531 assigned codepoints (mismatch=0) for
*this host's glibc only*.

**Verification by third parties (terceros)** — Review by someone with no involvement in the work,
who re-creates the evidence from scratch and reports either `VERIFICADO_POR_TERCERO` or
`NO_REPRODUCE`. Currently NOT_EXECUTED; see
[rxre-cleanroom#1](https://github.com/LexLuthorPrimero/rxre-cleanroom/issues/1).

**PASS / PROVEN / PARTIAL / BLOCKED / NOT_DETERMINED** — The RXRE evidence states. Nothing in this
repo claims PASS where the chain is incomplete; absence of a reported bug is not a proof.

**R3 seal numbers / evidence fields** — `evidence_id`, `sha256`, `dev`/`ino`, seal hash: identity
and integrity descriptors of an artifact in this research flow.
