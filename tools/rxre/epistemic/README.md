# Librería de Gobernanza Epistémica — v0.1.0

Runtime mínimo, stdlib-only (solo `hashlib/json/enum`), sin dependencias RXRE/GPU/rizin.
Extracción documentada M437 (§191) desde `verifier/promotion+sandbox`, `contracts/admission_tierra+coordination`, `core/db_auth_actor`, `buffer_contract`.

## API
- `EpistemicState` (PROVEN/PARTIAL/NOT_DETERMINED/BLOCKED/ABSTAINED), `AcceptanceDecision`, `SealPhase`
- `guard_promotion(state, evidence)` → decide fail-closed (PROVEN→ACCEPT_WITH_DOMAIN, PARTIAL→ACCEPT_LIMITED requiere limitaciones, resto WITHHOLD/DETACH/ABSTAIN/REJECT)
- `seal_prediction(prediction)` + `validate_seal_before_reveal(seal, evidence_time, seal_time)`
- `admit_claim(statement, object_hash, scope, scope_provenance, ...)` solo `EXPLICIT`
- `prepare/record_effect/confirm/reconcile` (PREPARED→EFFECT_APPLIED→CONFIRMED)
- `authorize_and_consume(verification_ref, consumer_id)` + `audit_ledger()` (jsonl encadenado por hash)
- `EvidenceBundle`/`EvidenceRef`, `EpistemicError/AdmissionError/SealViolation/PromotionDenied`

## Reglas (fail-closed)
- `PARTIAL` sin `limitations` → `WITHHOLD` (no promovible).
- Estado desconocido/ausente/malformado → `REJECT/WITHHOLD`, nunca promoción silenciosa.
- `scope_provenance EXPLICIT` obligatorio; INFERRED/UNKNOWN → rechazado.
- Serialización JSON determinista (`sort_keys=True`); hashes SHA-256.

## EXTRACTION_BLOCKED (no extraídos, documentados BLOCKED)
- `sandbox.py` (bwrap/contención OS), `independent_verifier.py` (multi-modelo), `db_auth_actor.py` (SQLite/DB_AUTH_ACTOR_M294), `buffer_capacity_provenance_contract.py` (11 props, dominio ilegal de buffers). Extraerlos sin cambiar semántica no es posible sin deps RXRE/GPU.

## Tests independientes
`tools/rxre/tests/test_epistemic_framework.py` 41/41, `test_epistemic_distinctions.py`.
Regresión: PASS_PARTIAL (2 fallos preexistentes en `test_semantica_estructural_contraste.py` no atribuibles).

Licencia/uso: interno RXRE, reutilizable como gobernanza de agentes/CI con incertidumbre.
