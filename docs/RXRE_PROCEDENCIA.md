# RXRE — Procedencia de artefactos

Mapa de los artefactos estructurales clave → origen → hash → estado epistémico → verificabilidad. Estable el 2026-11-12.

## 1) Identidad y gobernanza

| Artefacto | Origen | Hash (2026-11-12) | Estado |
|---|---|---|---|
| `RXRE_IDENTIDAD.md` | 2026-11-12; Dirección explicíta | `cce22881eb…` | `PROVEN` (existencia, vinc. con pasos de verificación) |
| `RXRE_ESTADO.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_ESENCIA.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_INDICE.md` | 2026-11-12 autogenerado desde el Plan Maestro | (calcular) | `PARTIAL` |
| `RXRE_FLUJO.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_PROTOCOLO_SELLADO.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_PROCEDENCIA.md` | 2026-11-12 (este archivo) | (calcular) | `PARTIAL` |
| `RXRE_CHANGELOG.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_LIMITACIONES.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `RXRE_OBSOLETOS.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |
| `VERIFIED_HASHES.md` | 2026-11-12 (esta sesión) | (calcular) | `PARTIAL` |

## 2) Artefactos protegidos / bases

| Artefacto | Origen | Hash | Estado | Verifica |
|---|---|---|---|---|
| `AGENTS.md` | 2025–2026, actualización continua | `25d57344dcef…` | `PRESERVED` | `sha256sum` / `cmp` |
| `rxre.sqlite3` | 2026-10-19 (intacto) | `c24d58d6…` (270.336 B) | `PRESERVED` / `APPEND_ONLY` | `sha256sum` / `stat` |
| `core/store.py` | 2026-10-19 | (ver `AGENTS.md`) | `PRESERVED` | `git diff` (sin cambios registrados) |
| `core/evidence_integrity.py` | 2026 | (ver `AGENTS.md`) | `PRESERVED` | `git diff` (sin cambios registrados) |
| Contratos `manifest_binding_contract.py`, `claim_evaluator.py`, `scope_provenance_contract.py`, `unified_verified_contract.py` | 2026 | (ver `AGENTS.md`) | `PRESERVED` | `git diff` (sin cambios) |

## 3) Evidencia GPU / E2E

| Artefacto | Origen | Estado | Alcance |
|---|---|---|---|
| `audit/evidence/e2e_001..010` | 2026-10-19/20 | `VALID` / `PARTIAL` | GPU shaders SPIR-V vía Vulkan; `MMIO` aparte |
| `audit/claims.csv` | 2026-10 | `PARTIAL` | F2/F3; C3 pendiente de universo |
| `gpu0/` (`original`, `restaurado`, `snapshot_meta.json`) | interno | `INTERNAL` | Fixtures; `.gitignore` debe excluirlos |

## 4) Artefactos de reconstrucción

| Artefacto | Origen | Estado | Alcance |
|---|---|---|---|
| `recon_ls` / `reconstruction/filenvercmp.c` | 2026-11-12 | `OPEN — NOT_PASS` | 791 divergencias |
| `pair_matrix_255.csv`, `pair_matrix_interior.csv` | 2026-11-12 | `PROVEN` (completitud frente al dominio de 1 byte) | Interior comparador |
| `w_end_probe.csv` | 2026-11-12 | `PROVEN` (255/255) | Fin de lado |
| `harness/verify_recon`, `oracle/matrix_gen` | 2026-11-12 | `PARTIAL` | Harness ejecutado; no certifica poder general |

## 5) Plan Maestro y copias

| Artefacto | Estado |
|---|---|
| `RXRE_PLAN_MAESTRO.md` (`rxre/`) | `e45e8072…` — 1.724.407 B — sincronizada |
| `documentacion/RXRE_PLAN_MAESTRO.md` | `e45e8072…` — sincronizada (`cmp` OK) |
| Tercera copia física | **NO LOCALIZADA** — discrepancia explícita §1044.7/§1045.4 |

## 6) Aplicabilidad

Ninguno de los artefactos `PARTIAL` autoriza paso a producción ni promoción de etiquetas. La aplicabilidad queda decidida por **verifier independiente externo** o **audiencia con poder de decisión humana**, nunca por RXRE mismo.
