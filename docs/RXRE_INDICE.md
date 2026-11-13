# RXRE — Índice del Plan Maestro

Autogenerado 2026-11-12. El Plan Maestro (1.724.407 B · 12.835 líneas · 1.320 `## `) es append-only y mezcla narrativa, evidencia y dictamen. Este índice orienta; no sustituye la lectura ni garantiza vigencia.

## Partes principales

| Parte | Líneas aprox. | Contenido |
|---|---|---|
| Reapertura / narrativa inicial | 1–915 | Origen, arquitectura de elementos, TIERRA, 249A–249H, dictámenes |
| Actualización verificador independiente | 1026–1237 | Actualización §1–5, correcciones antes de consolidar |
| Estructura documental recomendada → Dictamen | 1165–1237 | Recomendación y dictamen |
| Objetivo → protecciones | 1238–1434 | Inventario, contraste, ocho elementos, TIERRA, AIRE/ÉTER, fuego, tabla maestra |
| Consolidado inicial | 1434–2800 | Consolidado de fases |

## Apéndices por familia de misiones

| Familia | Misiones | Dictamen global (hoy) |
|---|---|---|
| Reconstrucción / juegos | M800–M875 (aprox) | PARTIAL / NOT_VERIFIED |
| Verificación / contrato uniforme | M900–M940 | PARTIAL |
| E2E-001..010 GPU AMD | E2E-006..E2E-019 | PARTIAL (SPIR-V validado) |
| Independencia física | E2E-038/E2E-039 | BLOCKED (host único `kalm`) |
| VC / GAP / POLS | POLS-046.. | Varios |
| M1234–M1265 | 2026-11-11 | Mixto; `PASS` acotado sólo dominio |
| M1266 | 2026-11-12 | A1 PASS, A2 PASS_PARTIAL, B2 PASS_PARTIAL, power-loss NOT_VERIFIED, G1043 EXECUTED |
| R3 | 2026-11-12 | **OPEN — NOT_PASS** (791/34.145 divergencias) |
| Identidad | 2026-11-12 | **PUBLISHED** (§1045; `RXRE_IDENTIDAD.md`) |

## Secciones más recientes (2026-11-11/12)
- §1026 M1256 · selección y caracterización del objetivo
- §1027 M1257 · reconstrucción independiente
- §1028 M1258 · oráculo y pruebas discriminantes
- §1029 M1259 · diferencial nativo
- §1030 M1260 · generalización y decisión
- §1031 M1261 · contrato común de reconstrucción
- §1032 M1262 · adaptadores de referencia
- §1033 M1263 · diferencial común
- §1034 M1264 · adversariales
- §1035 M1265 · cierre
- §1036 M1266 (Fase 0) · ERRATA y vectores canónicos
- §1037 M1266 (Fase 1) · A1-DIGEST
- §1038 M1266 · ERRATA contractual v19.3.11
- §1039 M1266-DECISION-001 · D01–D06
- §1040 M1266-D06 · MANIFEST_V1 ratificación
- §1041 M1266 v19.3.11 · ESP pecificación publicada
- §1042 M1266 · Outbox v1.1.0 ampliación
- §1043 M1266 · B2 tmpfs/ext4 · PWL-01 fases 1–2 PASS
- §1044 R3 · cadena E2E filenvercmp `OPEN — NOT_PASS`
- §1045 Identidad oficial `PUBLISHED`

## Llaves para no perderse

- **Identidad**: `RXRE_IDENTIDAD.md` (empezar por esto)
- **Estado real hoy**: `RXRE_ESTADO.md`
- **Gobernanza**: `AGENTS.md`
- **Método**: `RXRE_PROTOCOLO_SELLADO.md`
- **Procedencia**: `RXRE_PROCEDENCIA.md`
- **MVP que falta**: comando `rxre reconstruct` (no existe aún)
- **Evidencia en repo**: `audit/evidence/e2e_001..010`, `audit/claims.csv`, `rxre.sqlite3` (protegida)
- **Bases protegidas**: `AGENTS.md`, `core/store.py`, `rxre.sqlite3`, contratos — **nunca reescribir ni datos**
