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

Only two targets exist, with sealed evidence inside `evidence/r3/`:

| Target | Artifact | Corpus | Result |
|---|---|---|---|
| `filenvercmp` (sort = version) in `/usr/bin/ls` (sha256 `54e936d3…`) | semantic C reconstruction | 34,145 × 2 sealed pairs (seeds 20261112/13, 0 divergences, both generations) | ✓ byte-exact vs native |
| `wc` in `/usr/bin/wc` (sha256 `81d61459…`) | semantic C reconstruction | C locale (default / flags / `-m` ≡ `-c` / `-L`) and es_AR.utf8 (NBSP/high bytes, `-m` multibyte, `-L` with real width table, flags×multibyte) | ✓ 0 divergences everywhere |

Details, logs and matrices live in `evidence/r3/` (`EXPEDIENTE_R3.md` is the full
case file — Spanish).

## Verify it yourself — one command

```sh
sh evidence/r3/verify.sh
```

It checks the sealed corpora SHA-256s against their pre-registered seals,
rebuilds the reconstruction, re-runs the differential comparison on both
generations (34,145 cases each), then runs the engine's Python test suites.
Expected tail: `total=34145 mismatches=0` twice, then `12 passed`, then
`VERIFY: all steps passed`.

Note: the `rxre-cleanroom` package exists so anyone can check on their own
machine without this repo's structure: https://github.com/LexLuthorPrimero/rxre-cleanroom (MIT).

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

## Documentation map

- English entry points: this README, `GLOSSARY.md`
- Spanish case files: `docs/RXRE_ESENCIA.md`, `docs/RXRE_LIMITACIONES.md`, `docs/RXRE_PROCEDENCIA.md`,
  `evidence/r3/EXPEDIENTE_R3.md`
- Sibling public package: `rxre-cleanroom` — same brother-in-arms; its commit hashes are part of
  the public seals in this tree.

## License & authorship

MIT (see `LICENSE`). Original work by Lucas Cañete. GNU coreutils binaries, if
used as runtime oracles, belong to their rights-holders; nothing here redistributes
them. The corpus and matrices were synthesized by the author.

Co-developed with AI tooling under human ownership. Human ownership of claims
and auditability rests with Lucas Cañete; AI assistance does not constitute an
independent verification of any fact, and this repo does not treat it as one.
