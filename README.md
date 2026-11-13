# RXRE engine

**TL;DR — you can stop reading here.** RXRE is an AI-assisted reverse-engineering
**research project**. It has produced one strong artifact type: sealed,
zero-tolerance, byte-exact reconstructions of specific GNU coreutils 9.10
binaries (e.g. `filenvercmp` inside `ls`, and `wc` — both now reproducible by
anyone). Third-party independent verification has **not** happened. You can
verify the entire claim for yourself with **one command** (`evidence/r3/verify.sh`,
about 2 minutes, needs only gcc/sha256sum/pytest). MIT.

## Status, stated precisely

- **Public research engine, not a service.** Its reconstructions are semantic
  contracts verified under specific corpora and locales — not drop-in replacements.
- **Third-party verification: NOT_EXECUTED.** All evidence is from one host,
  one UID, the same human author (with AI-assisted tooling). The blind-verification
  issue that decides the question lives in the sibling package
  [rxre-cleanroom#1](https://github.com/LexLuthorPrimero/rxre-cleanroom/issues/1).
- **No general claims.** No PASS, no global correctness, no independent
  "RXRE is right" for any other binary, no coverage beyond the sealed artifacts.
- GPU access is restricted to shader compilation/execution via Vulkan/SPIR-V.
  No MMIO, no `/dev/mem`, no `root`, no `--auto`, no global rollback.
- **PUERTA acceptance (its gate, condition 3): PENDING_EXTERNAL_REVIEWER** by design.

## What is actually verified

Only five targets exist, with sealed evidence inside `evidence/r3/`:

| Target | Artifact | Corpus | Result |
|---|---|---|---|
| filenvercmp (sort = version) in /usr/bin/ls — sha256 54e936d3... | semantic C reconstruction | 34,145 x 2 sealed pairs (seeds 20261112/13, 0 divergences); adversarial challenge 3,100+141 / 0 divergences; locale-invariance byte-equal C ≡ es_AR.utf8; i18n black-box 200 names identity vs native ls -v | ok byte-exact vs native |
| wc in /usr/bin/wc — sha256 81d61459... | semantic C reconstruction | C locale + es_AR.utf8; default / flags / -m multibyte / -L width / --files0-from / flags x multibyte / files0-from adversarial | ok 0 divergences vs native GNU |
| fold in /usr/bin/fold — sha256 95030461... | property reconstruction (line-wrap width) | 2 sealed generations (2.554 each, -w 4, seeds 20261113/14) + gated w=1/2/3/8 corpora (1.054 each; 6 gated regenerations); valid UTF-8 only; byte-exact vs native `/usr/bin/fold -w N` | ok 0 divergences vs native GNU |
| tr in /usr/bin/tr — sha256 b1d1bfbe... | property reconstruction (squeeze of byte-x runs, `tr -s x`) | 2 sealed generations (2.513 each, seeds 20261113/14); byte-exact vs native `/usr/bin/tr -s x` with harness over stdin | ok 0 divergences vs native GNU |
| dirname in /usr/bin/dirname — sha256 aac6a889... | property reconstruction (parent directory, bounded) | 2 sealed generations (1.917/1.901, seeds 20261113/14); byte-exact vs native `/usr/bin/dirname` with harness over stdin | ok 0 divergences vs native GNU |

Details, logs and matrices live in `evidence/r3/` (`EXPEDIENTE_R3.md` is the full
case file — Spanish).

## New here? Read [`QUICKSTART.md`](QUICKSTART.md) first (15 minutes, verification-first).

## Verify it yourself — one command

```sh
sh evidence/r3/verify.sh
```

One command; it checks the **SHA-256 of 60 sealed artifacts** against their
manifest, verifies the identity of the native reference binaries
(`/usr/bin/ls`, `/usr/bin/wc`, `/usr/bin/fold`; fail-closed), rebuilds the reconstruction, and re-runs the differential
comparison on **both generations of `filenvercmp` (34,145 × 2)** plus
the **challenge corpus (3,100 + 141 deliberately identical a==b = 3,241 cases)**,
the **locale-invariance test**,
the **i18n black-box**, the **fold property reconstruction** (2 sealed generations, byte-exact), and **all `wc` corpora** (LC_ALL=C and es_AR.utf8;
bytes/chars/-L/flags), then runs the engine's Python test suites. Expected
tail: `total=34145 mismatches=0` twice, `total=3100 mismatches=0`,
`total=3241 mismatches=0`, `locale invariance OK`, `i18n black-box OK`,
two `total=2554 mismatches=0` lines for **fold**,
twelve `total=… mismatches=0` lines for `wc`, `78 passed, 2 skipped` (the 2 skips
are `test_replay_mision` cases whose precondition is the author's private operations
DB, deliberately not distributed; they run wherever that DB exists), then
`VERIFY: all steps passed`.

## For independent reviewers

[`reviewer-kit/`](reviewer-kit/) contains the step-by-step verification guide,
the counterexample report template, and the scope/limits of this package. If you
reproduce or refute the sealed chain, file it as an issue with your environment
and exact commit.

## Repository layout

```
tools/rxre/        engine source (auditor architecture, contracts, verifier, API)
tools/rxre/tests/  adversarial test suites (integrity, contracts, reproducibility)
evidence/r3/       sealed artifact set (corpora, matrices, reconstruction, seals, journals)
docs/              method identity documents (Spanish)
audit/evidence/    the two evidence records referenced by the integrity suite
GLOSSARY.md        terms in EN+ES (PUERTA, seal-before-reveal, semantic contract, R3…)
```

## Not here on purpose

- No SQLite databases, no third-party source or binaries, no private captures.
- No marketing claims this repo can't show you the bytes of. The method is
  interesting precisely because it is falsifiable.

## Corpus sensitivity (quantitative, not self-congratulation)

`evidence/r3/records/coverage_report.txt` (generated by `coverage_audit.py`) shows what the
**original seed 20261112/20261113 generations** exercise — it was generated for those two
sealed corpora, not for the challenge corpus. The challenge corpus deliberately targets the
original weak spots instead: 1,875/3,100 cases with names ≥32 B, 95.1% with UTF-8 bytes,
225 distinct return values, plus 141 deliberately identical a==b pairs (= 3,241 total in
hito 13b). Compare like with like:: UTF-8 content 3.89% of cases, tilde 13.45%, dot-leading 5.47%,
prefix-related 5.09%, numeric-only 2.30%, long names (>32 B) 0%. Outcome balance:
49.6% negative / 0.66% equal / 49.8% positive, with ~640 distinct unclamped return values
(not just -1/0/1). **Gap honesty:** UTF-8 filename coverage is thin in byte-level terms; a
black-box `es_AR.utf8` i18n seal (200 names, `ls -Av` vs reconstruction) lives in
`evidence/r3/filenvercmp_i18n_20261126/` — still not broad generalization. If your adversary
generator beats this corpus, file it in the sibling issue — that's a positive result.

An optional `Dockerfile` exists for reviewers who want a pinned toolbox (gcc + python + pytest).
Built and run with **rootless podman 5.8.7** on this host: image boots `verify.sh`, and its suites
pass (one host-artifact-bound test skips honestly because the sealed reference artifact lives on
the author's private host; everything else passes). The image is pinned to `fedora:44` precisely
because its `/usr/bin/ls` matches the sealed reference hash of this package.

## Documentation map

- English entry points: this README, `GLOSSARY.md`
- Spanish case files: `docs/RXRE_ESENCIA.md`, `docs/RXRE_LIMITACIONES.md`, `docs/RXRE_PROCEDENCIA.md`,
  `evidence/r3/EXPEDIENTE_R3.md`
- Sibling public package: `rxre-cleanroom` [v1.5.3](https://github.com/LexLuthorPrimero/rxre-cleanroom/releases/tag/v1.5.3) — same brother-in-arms, aligned release; commended to the same blind-verification call.
- Own auditable snapshot: [v1.6.0 release](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.6.0) (`rxre-engine-1.6.0.zip`; current — **FIVE bounded targets sealed**: filenvercmp, wc, fold, tr, **and dirname**; verify gate `78 passed, 2 skipped`; 15 stages; 60-artefact manifest). Superseded snapshots kept byte-exact: [v1.5.3](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.5.3) (transparency/content fix), [v1.5.1](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.5.1), [v1.5.0](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.5.0) (FIVE targets + transparency), [v1.4.0](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.4.0) (FOUR targets), [v1.3.10](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.3.10), [v1.3.9](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.3.9), [v1.3.8](https://github.com/LexLuthorPrimero/rxre-engine/releases/tag/v1.3.8).

## License & authorship

MIT (see `LICENSE`). Original work by Lucas Cañete. GNU coreutils binaries, if
used as runtime oracles, belong to their rights-holders; nothing here redistributes
them. The corpus and matrices were synthesized by the author.

Co-developed with AI tooling under human ownership. Human ownership of claims
and auditability rests with Lucas Cañete; AI assistance does not constitute an
independent verification of any fact, and this repo does not treat it as one.
