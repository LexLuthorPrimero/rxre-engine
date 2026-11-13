# RXRE — Documentos candidatos a archivo (no eliminar)

Estos archivos están completos pero: duplicados, sobre-detallados para público, o complementarios. Ninguno debe borrarse sin revisión.

## Candidatos a archivo (`docs/archive/`)
- `AUDIT_FINAL.md` y `AUDIT_FINAL_SUBAGENTES.md` (solapados en propósito).
- `TRABAJO_EJECUTADO.md`, `CONSOLIDADO_EJECUTADO.md` (histórico descriptivo de misiones).
- `Diagramas corregidos — 7, no 20.md` y `Diagramas corregidos v2.md` (versión derivada).
- `jorn*` / `jorgeeee.md` (notas personales enormes; preservar pero mover a `/archivo/` del repo).
- `docs/RXRE-005-FIELD-REPORT.md`, `RXRE-AUTONOMOUS-*` (miscelánea de misiones autónomas con riesgo de extraer conclusiones no verificadas).
- `INFORME_RXRE_PUB_001.md`..`016.md` (informes de publicación muy largos; útil colapsar en un solo `PUBLICACIONES.md`).

## Candidatos a consolidación
- `DECISIONES_ESTRUCTURALES.md` — útil; revisar vigencia fecha a fecha.
- `RECONCILIACION_LOCAL_REMOTO.md` + `PLAN_RECONCILIACION_SPE_28.md` — consolidar en una sola guía de publicación controlada.
- `M820_DOCUMENTARY_INTEGRITY_RECONCILIATION_DESIGN.md` — verificar si su objetivo fue absorbido.

## Candidatos a mantener tal cual
- `AGENTS.md` — ley fundamental de gobernanza.
- `README.md` — estado público del repo.
- `RXRE_PLAN_MAESTRO.md` — evidencia append-only histórico (no reescribir).
- `docs/` — colección de auditoría; archivar pero no borrar.

## Verificación
Cada archivo candidato a archivado debe: (1) tener hash documentado (`sha256sum`); (2) preservarse en `git` (adición, no eliminación) o en `store/artifacts/` con manifest; (3) conservar su procedencia (misión/fecha/decisor).

## Cuándo archivar
Idealmente tras congelación por `§1000..`; o tras publicación externa controlada. Hasta entonces: consultar antes de mover. La estructura `docs/archive/` no existe aún; crearla implica convención explícita.
