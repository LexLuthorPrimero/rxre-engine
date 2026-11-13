# RXRE — Limitaciones externas conocidas

RXRE no oculta limitaciones. Estas son las que afectan cualquier lectura del proyecto hoy.

## 1) Independencia y auditoría
- **Independencia física Nivel 2 ausente.** Host único (`kalm`). No hay segundo host; no hay host remoto accesible; no hay hardware verificado externo.
- Toda validación es `SAME_HOST` y/o `SAME_UID` salvo indicación explícita contraria.
- **No hay verificador humano independiente asignado.** Puerta `PUERTA.py` en estado `CONTESTED` (cond. 3 pendiente de revisor formal desde 2026-10-19).
- Las firmas criptográficas si se añaden no "autonomizan" el cierre; son evidencia, no aprobación.

## 2) Hardware target
- GPU Polaris12 validada por **API Vulkan/SPIR-V vía `require_gpu()`**; no hay lectura directa de registros (`/dev/mem`, `debugfs`, `UMR`, `sysfs`) permitida sin privilegios.
- `MMIO/UMR` no verificados por ejecución directa. `e2e_005` registra `2735 gfx refs`, `72 polaris refs`; **hardware físico no confirmado**.
- Device-only PKU/eGPU no probado; heterogéneo multi-GPU no probado.
- Otras generaciones AMD/NVIDIA/ARM no probadas.

## 3) Almacenamiento y persistencia
- `rxre.sqlite3` (270.336 B, 2026-10-19) protegida; solo appended; triggers prohíben `DELETE/UPDATE`.
- `.rxre/` contiene capturas/gpu0; pendiente política de exclusión en `.gitignore`.
- `/tmp` volátil: plataformas recientes pierden `/tmp/m453…`; artefactos críticos deben promoverse (pendiente `store/`).

## 4) Producto e integración
- **Sin integración en producción**. Sin puerta de aceptación completa.
- **R3 today**: `filenvercmp` sobre `/usr/bin/ls` y `wc` sobre `/usr/bin/wc` — 0 divergencias en ambas generaciones selladas; verificación independiente de terceros NOT_EXECUTED. (ver rxre-cleanroom v1.2.0 + rxre-engine README/attack; este documento conservará el estado histórico cuando corresponda)
- `wc` y `ls` completos rechazados por `fidelity_domain_v2` (no construida para cubrirlos).
- No hay comando `rxre reconstruct` públicamente estable.

## 5) Publicación remota
- `origin` `main` → `c682c4a` (0 archivos tracked); local `HEAD` `5d84e831`; `merge-base` vacío.
- **Publicación:** `READY_NOT_PUBLISHED`; `push` no autorizado.
-`MANUAL_RECONCILIATION_REQUIRED` desde `SPE 27/28`.

## 6) Documentación y métricas
- **Métrica externa ausente**: no existe aún un resultado medible con `N` funciones reales, cero divergencias, firmadas, por un tercero independiente.
- No se ha declarado criterio de éxito operacional externo: único criterio externo permitido = autoría/reproducibilidad verificada por tercero.
- Anexo del Plan Maestro crece más rápido que las capacidades; indexar (hecho: `RXRE_INDICE.md`) ayuda, no resuelve.

## 7) Legales y alcance
- Licencia `MIT` (ver LICENSE); sin GPL v2. Documentos de informe tienen aviso de autoría.
- Fixtures `rxre.min.elf`, `amdgpu.ko`, etc. pueden no distribuirse.
- Ningún binario de terceros se redistribuye.

## 8) Qué NO se admite
- `op:claim`, `--auto`, `sudo`, `/dev/mem`, `debugfs` sin autorización explícita.
- Declaraciones `PROVEN` automáticas.
- Integración, promoción, generalización o despliegue productivo por esta o la anterior sesión.
- Reescritura de evidencia histórica.

## 9) Limitaciones de las limitaciones
Toda limitación puede quedarse desactualizada. La fuente de verdad para capacidades hoy es `README.md` + secciones recientes del Plan Maestro (§1041..§1045). Las capacidades futuras declarasadas en documentos antiguos no son realidad; deben verificarse antes de cualquier acción.

---

## 10) Limitaciones descubiertas por el reconocimiento tecnológico exterior (2026-11-12)

El reconocimiento directo del repositorio (`RECONOCIMIENTO-TECNOLOGICO/`) añade estas limitaciones (ninguna nueva promesa, ninguna versión nueva):

1. **Ninguna herramienta externa instalada esta sesión (SVF, PhASAR, Miasm, Triton, RetDec, Remill, Anvill, Rellic, oFrak, Patcherex2, Maat, Binsec, BeaEngine, REA) está integrada en el pipeline.** Todas son `INVOCABLE`, no `INTEGRADA`; ninguna tiene licencia/path certificado para integración propia.
2. **Los inventarios históricos "27 tecnologías", "24 tecnologías" y "13 tecnologías" no se ratifican.** ~5,9 GB de clones vendorizados (mlflow, semgrep, hindersight, cognee, MemOS, openhands, llvm-project, linux, VK-GL-CTS, mesa, piglit, drm, etc.) carecen de consumidor 1ª-party observado.
3. **La suite de tests de la raíz** (`tests/` — 192 archivos) **no es ejecutada por ningún runner automático** del repo (solo `tools/rxre/tests/test_*.py` vía `run_tests.sh`).
4. **Store.py + M415**: compat declarada rota contra esquemas en disco (`operations` sin `declared_scope`); dos generaciones coexisten (`store.py` / `store_compat.py`).
5. **Misma-hoya**: toda validación `SAME_HOST`/`SAME_UID`; independencia Nivel 2 inexistente (host único `kalm`). **PUERTA** sigue `CONTESTED` (cond. 3 sin revisor humano desde 2026-10-19).
6. **`tools/rea/` vendorizado** (4 031 archivos, 138 MB) sin integración al pipeline y sin uso en el núcleo; `rea-agents` instalado fuera del repo (`/home/lucas/Escritorio/rea-install`) por separado y tampoco integrado.
7. **GPUs**: ejecución acotada al compute "42" (RADV y llvmpipe); sin MMIO/UMR/debugfs/`/dev/mem`; sin lectura de registros.
8. **No existe `rxre reconstruct`** ni pipeline certificado de lifting→IR→C que devuelva binarios semánticamente equivalentes en dominio general.
9. **`import angr`** no funciona en el entorno (findings 1573); **`Ghidra ET_REL`** no soportado.
10. **Contraseñas sudo en código** de tests (`test_umr_*.py`, `test_agua_plan008.py`) — hecho documentado, no corregido por respeto al freeze.

Cada ítem corresponde a evidencia en `RECONOCIMIENTO-TECNOLOGICO/EVIDENCIAS.md` y `LIMITACIONES.md` del repositorio.
