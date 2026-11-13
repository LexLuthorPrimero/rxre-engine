# RXRE — Estado actual

**Fecha de corte:** 2026-11-12 · **Identidad:** ver `RXRE_IDENTIDAD.md`

## Resumen ejecutivo

| Eje | Veredicto |
|---|---|
| Identidad | **PUBLISHED** — `RXRE_IDENTIDAD.md`; Plan Maestro actualizado (§1045, ambas copias `rxre/` y `documentacion/`, sha256 `e45e8072…`) |
| Documentación | **PARTIAL** — addenda §1044–§1045 selladas; índice regenerable; historial preservado |
| Motor de reconstrucción (`filevercmp`) | **OPEN — NOT_PASS** (791/34.145; ^§1044) |
| GPU Polaris 12 | **PARTIAL** — validado por Vulkan/SPIR-V (E2E-006..E2E-019); `MMIO`/`UMR`/`debugfs` **BLOCKED** |
| Independencia física | **BLOCKED** — host único (`kalm`) |
| Publicación remota | **READY_NOT_PUBLISHED** — `c682c4a` (0 tracked) vs local `HEAD 5d84e831`; `MANUAL_RECONCILIATION_REQUIRED` |
| `AGENTS.md` / `rxre.sqlite3` / `core/store.py` | **PRESERVED** — hashes verificados en esta sesión |

## Evidencia verificada en esta sesión

| Item | Valor |
|---|---|
| `AGENTS.md` | `25d57344dcef…` · 55.103 B |
| `README.md` | `6319569587…` · 6.686 B |
| `RXRE_IDENTIDAD.md` | `cce22881eb…` · 513 B |
| `RXRE_PLAN_MAESTRO.md` | `e45e8072…` · 1.724.407 B · 12.835 líneas |
| `rxre.sqlite3` | `c24d58d6…` · 270.336 B |

## Conteos estructurales

- **1.320** encabezados `## ` en el Plan Maestro
- Documentos `.md` en el repo: **4.924**
- Archivos en `tests/`: **198**
- `AGENTS.md` y derivados remiten a `store.py`, contratos protegidos, DB append-only.

## Capacidades verificadas

- GPU shaders SPIR-V vía `require_gpu()` — evidencia en E2E-006..E2E-019 (documentadas, no re-ejecutadas en esta sesión).
- Integridad de evidencia (`hash` + identidad física) — `test_integridad_adv_final.py` 8/8 (documentado).
- Subfunciones de `filevercmp` verificadas aisladamente: byte comparator (0/32.385), `file_prefixlen` (7.320/7.320), `w_of` (255/255).
- Pipeline Ghidra/Remill/Anvill/Rellic: funciones reales con diferencial nativo (acotado; `check_tuning` 1080/1080).

## Capacidades NO verificadas / bloqueadas

- Reconstrucción semántica end-to-end de binarios reales (`wc`, `ls` completos) — **BLOCKED/OPEN**.
- `filevercmp` con cero divergencias — **OPEN** (791 divergencias).
- Independencia Nivel 2 (replicación externa) — **BLOCKED** (E2E-039).
- `MMIO`/`UMR`/`debugfs`/`/dev/mem` — **BLOCKED** (sin privilegios).
- Publicación remota controlada — **READY_NOT_PUBLISHED**.
- Power-loss / Gate 2 / Recovery global — **NOT_AUTHORIZED**.
- RXRE como motor autónomo general — **NO VERIFICADO**.

## Bases protegidas (intactas)

- `AGENTS.md` (`25d57344…`) · `rxre.sqlite3` (`c24d58d6…`, 270.336 B) · `core/store.py` · contratos protegidos · `jorgeeee.md`
- Tercera copia del Plan Maestro: **no localizada** (discrepancia explícita en §1044.7/§1045.4)

---

## Anexo 2026-11-12 — Reconocimiento tecnológico exterior (no verificado por terceros)

**Documento:** `RECONOCIMIENTO-TECNOLOGICO/` (directorio en el repositorio; ver `RECONOCIMIENTO-TECNOLOGICO/SYNC.md` para índices y confrontación con este documento).

**Datos descubiertos (lectura directa del repositorio, sin ejecutar suites):**

| Eje | Valor encontrado |
|---|---|
| Tecnologías contabilizadas | **74** (28 propias, 30 externas, 4 adaptadas, 6 compuestas, 6 experimentales) |
| Inventario "27 fundacionales" del Plan Maestro | **No ratificado**; ~13 identificables; resto clones/referencias sin integración |
| Inventario "24 tecnologías" (M626) | **No ratificado**; `PARTIAL`, sin verificación externa |
| Inventario "13 tecnologías" | **No existe** (0 coincidencias; quizá "13 adapters" de RXRE-1635) |
| `core/` en raíz | No existe; ruta real `tools/rxre/core/store.py` |
| Tests citados (8/8, 5/5, …) | Documentales; **no re-ejecutados** en este reconocimiento (`PARTIAL`) |
| PUERTA.py | `CONTESTED` (condición 3 pendiente desde 2026-10-19) |
| RXRE+REA | `NOT_PROVEN`; `tools/rea/` vendorizado sin integración al pipeline |
| Herramientas externamente instaladas en esta sesión | SVF, PhASAR, Miasm, Triton, RetDec, Remill, Anvill, Rellic, oFrak, Patcherex2, Maat, Binsec, BeaEngine, REA — **ninguna integrada**; cf. E-19..E-30 |
| `import angr` | **Roto** en este entorno (finding 1573) |
| Estado de reconstrucción (`filevercmp`) | **OPEN — NOT_PASS** (791/34 145 divergencias; verificación propia) |

**Consecuencias para la tabla de veredicto anterior:**

- La fila "Documentación … PARTIAL" sigue siendo correcta; este reconocimiento no altera esa lectura, la precisa.
- La fila "Motor de reconstrucción … OPEN — NOT_PASS" queda confirmada por verificación directa.
- Las cifras históricas "27/24/13" **no se conservan** por conveniencia; el inventario descubierto tiene prioridad sobre los catálogos anteriores.

**Cómo leer este anexo:** estados marcados como "documental" no fueron re-verificados; estados marcados como "verificado" provienen de `/tmp/rxre-tech-recognition/EVIDENCIAS.md` (now copied into `RECONOCIMIENTO-TECNOLOGICO/EVIDENCIAS.md`) o de evidencia en este repo con fecha 2026-11-12. No promueve ni degrada ningún estado epistémico; solo documenta lo que está y lo que no está.
