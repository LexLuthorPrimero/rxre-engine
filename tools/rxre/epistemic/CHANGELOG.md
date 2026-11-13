# Changelog — Librería Epistémica

## [v0.1.0] - 2026-11-07
- Extracción M437 (§191) `PASS_PARTIAL`: 10 módulos stdlib, API mínima, 41/41 tests.
- Formalización Fase 1 (esta entrada): README, suite independiente, inventario de `EXTRACTION_BLOCKED`, manifiesto de regresión.

### Added
- `EpistemicState/AcceptanceDecision/SealPhase`, `guard_promotion`, `seal_*`, `admit_claim`, `prepare/record_effect/confirm/reconcile`, `authorize_and_consume/audit_ledger`, `EvidenceBundle/Ref`, errores.
- Tests `test_epistemic_framework.py` (41) + `test_epistemic_distinctions.py`.

### Known limitations
- `sandbox/verifier/db_auth_actor/buffer_contract` EXTRACTION_BLOCKED (BLOCKED).
- Regresión `PASS_PARTIAL` por 2 fallos preexistentes `test_semantica_estructural_contraste` (no causados por extracción).
- Sin telemetría, sin telemetría de aliado; serialización determinista SHA-256.
