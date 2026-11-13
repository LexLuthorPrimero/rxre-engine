# RXRE — CHANGELOG documental

## 2026-11-13 (bounded semantic-obligation tooling)

- **Añadido `tools/rxre/semantic/semantic_obligations.py`**: parser SMT-LIB con validación estructural de tres obligaciones BV32 concretas (`x*256 == x<<8`, `x*256 == x*25`, `x*256 == x<<7`). **No** afirma equivalencia general ni promueve binarios a `PROVEN`.
- **Añadido `tools/rxre/tests/test_semantic_obligations.py`**: identifica las obligaciones esperadas y rechaza fórmulas vacías o de ancho incorrecto. **2 tests** verificados localmente.

## 2026-11-13 (basename milestone v1.9.0)

- **§1055 R3 — sexto objetivo sellado (basename)**: propiedad acotada “último componente”; corpus 2×1.987/2.013 (seeds 20261114/15), UTF-8 wide chars + boundary buckets; reconstrucción C11 independiente (`basewrap.c`); verify.sh **16 etapas** (basename 14/16), manifiesto ampliado a **65 artefactos**; identidad fail-closed de `/usr/bin/basename` (sha256 `1ef99139…`, coreutils-9.10-5.fc44); `test_discovery_on_basename.py` (2 herméticos; gate **80 passed, 2 skipped**). Alcance honesto: único operando path, sin flags/sufijo; 0 divergencias contra oráculo nativo en hosts del autor. Verificación de terceros: **NOT_EXECUTED**. v1.9.0 etiqueta y publica con autorización explícita del propietario (2026-11-13). Update-25.

## 2026-11-13 (transparency v1.5.1)

- **Transparencia pública actualizada**: README/QUICKSTART/verify.sh header y summary en sync con los cinco objetivos sellados (filenvercmp/wc/fold/tr/dirname) y con manifiesto **60 artefactos**; coverage summary declara los cinco; identidad fail-closed pin de los cinco binarios.
- **P1 refforzado**: `evaluate_contract()` ya no admite observación vacía ni auto-reflexiva romántica (test_5c2 / test_5d nuevos); replay ejecuta con payload original de `request_json` verbatim; `test_replay_uses_original_request_payload` exige timeout original y flags de request; función `test_5c_resultado_declarado_sin_observacion_no_acepta` ya existía y soportada; tests nuevos admitidos; terceros NOT_EXECUTED.

## 2026-11-13 (tr milestone v1.4.0)

- **§1049 R3 — cuarto objetivo sellado (tr, `-s x`)**: property reconstruction byte-exact sobre corpus 2×2.513 (seeds 20261113/14), identidad fail-closed `/usr/bin/tr` sha256 b1d1bfbe…, manifest ampliado 56 artefactos, verify.sh 14 etapas con tr. Update-18. Terceros NOT_EXECUTED.

## 2026-11-13 (dirname milestone v1.5.0)

- **§1050 R3 — quinto objetivo sellado (dirname)**: bounded property reconstrucciónbyte-exact sobre corpus 2×1.901–1.917 (seeds 20261113/14), C11 independiente, verify.sh 15 etapas con dirname, manifest ampliado 60 artefactos, identidad push fail-closed /usr/bin/dirname (aac6a889…), stage 13/15. Update-19. Terceros NOT_EXECUTED.

## 2026-11-13 (MENTE synthesis e2e)

- **§1054 MENTE synthesis e2e**: `test_discovery_synthesis.py` — primer bucle completo discover→synthesis→byte-exact-diff sobre target desconocido compilado en tmp_path (no source opened by pipeline); literals 'alpha'/'beta' recuperados de rodata; C regenerado feamente (strncmp+sentinels); differential vs original 0 mismatches en ~25 trials; verify pin espera **78 passed, 2 skipped**. Terceros NOT_EXECUTED. P0 remains OPEN para binarios sin literal resources.

## 2026-11-13 (P0 on dirname)

- **§1053 MENTE multi-round**: `mente_cycle` ahora integra iteraciones de discriminación, usado por `test_discovery_loopbench.py` — 3 rivales refutados, PREFIX sobrevive, NOT_DETERMINED. verify pin espera **77 passed, 2 skipped**. Terceros NOT_EXECUTED.



- **§Etapa 6 Tests sobre binario real fijados**: `test_discovery_on_dirname.py`; `.rodata`-literal analysis (rizin izj); no false literal candidates dumped onto any classification PASS; `_no_profile_imported == True`; verify expects pins **78 passed, 2 skipped** distilled. Terceros NOT_EXECUTED.

## 2026-11-13 (P0 + bug crítico Fixes: discovery + reconstructor)

- **Bug latente en `reconstructor.py`**: `subprocess`/`re`/`_json` no apropiadamente importados -> todos los binarios analizados quedaban `ANALYSIS_FAILED` por 0 CFG. Corregido. Capacidad general de análisis desbloqueada.  (v1.6.0)
- **Bug latente en `_rizin_cfg` denominadores / defaults**: funciones FUNCTION_CANDIDATE siempre 0 cfgs -> ahora trabajan correctamente.
- **`docs/RXRE_CHANGELOG.md` apropiadamente actualizado** para abarcar ambos errores. (LANGDIR)

## 2026-11-13 (transparency v1.5.1)

- **§1048 R3 — mente fold rivals**: `test_mente_fold_rivals.py` hermético sobre corpus sellado (gen seed20261113); clone WCWIDTH reproduce 2.554/2.554; rival BYTES/CODEPOINTS refuted; WCWIDTH survive NOT_DETERMINED. verify gate 69 passed, 2 skipped. Update-17. Terceros NOT_EXECUTED.

## 2026-11-13 (fold multi-width)

- **§1047 R3 — fold multi-width**: milestone `fold` ampliado de un único width a seis regeneraciones selladas/gated (-w 4 × seeds 13/14 + -w 1/2/3/8), 0 divergencias; verify.sh cubre las seis; manifiesto extendido y regenerado (SEAL.txt actualizado). Update-16 en EXPEDIENTE_R3.md. Terceros NOT_EXECUTED.

## 2026-11-13 (fold milestone)

- **§1046 R3 — tercer objetivo sellado (fold)**: property reconstruction de `/usr/bin/fold -w 4` (cell width, tab stop 8) sellada con 2 generaciones de corpus (2.554 casos c/u; total=2554 ×2, 0 divergencias) y verify.sh con nueva etapa 11/13 (identidad fail-closed de /usr/bin/fold, sha256 95030461…). Manifiesto sellado ahora vincula 47 artefactos. Update-15 en EXPEDIENTE_R3.md. Verificación de terceros: NOT_EXECUTED.

## 2026-11-12

- **§1044 R3** — cadena E2E de `filevercmp` sobre `/usr/bin/ls`: `OPEN — NOT_PASS` (791/34.145) — **[HITÓRICO / SUPERSEDED 2026-11-12, update-5]**: las 791 divergencias fueron resueltas; estado vigente en `evidence/r3/EXPEDIENTE_R3.md` (§11 + updates 6–10). No leer como estado actual.
- **§1045** — identidad oficial publicada: método primario; modelo falsable; `RXRE_IDENTIDAD.md`.
- **Añadidos** (esta sesión):
  - `RXRE_ESENCIA.md`, `RXRE_ESTADO.md`, `RXRE_INDICE.md`, `RXRE_FLUJO.md`,
  - `RXRE_PROTOCOLO_SELLADO.md`, `RXRE_PROCEDENCIA.md`, `RXRE_CHANGELOG.md`,
  - `RXRE_LIMITACIONES.md`, `RXRE_OBSOLETOS.md`, `VERIFIED_HASHES.md`
- **Limitaciones preservadas:** sin `--auto`, sin `op:claim`, `AGENTS.md`/DB intactos; R3 abierto; independencia física bloqueada; publicación `READY_NOT_PUBLISHED`.

## 2026-11-12 (M1266 fases)

- A1-DIGEST PASS (scratch); A2 PARTIAL; B2 tmpfs/ext4 PASS_PARTIAL; power-loss NOT_VERIFIED; Gate 2/Recovery/EXP-01…15 no autorizados.
- Contrato `OUTBOX_EVENT_V1 v1.1.0` **RATIFIED**. `OBX1` no migrado.

## 2026-11-11

- M1256..M1265 — reconstrucción `filenvercmp` acotada; `check_tuning` 1080/1080; denominador común de cobertura limitada.
- G1035/G1037/G1042/G1043 EXECUTED (close).

## 2026-10-19 (línea base)

- `SPE 25..29`; `PUB-001..016`; `AUDIT_FINAL`; controversia de desreplegamiento.
- `e2e_001..010` capturados y etiquetados; GPU validado por Vulkan/SPIR-V; `F2` pendiente.
- Bases intactas; `jorgeeee.md` preservado.

## 2026-10-18..2026-10-30 (misiones primeras fases)

- `M300..M350`; arquitectura v3; verificación independiente; sellado; TEERRA/AIRE/FUEGO.
- `benchmark_polari12`; `RX550`; `amdgpu` cargas; GPU validado como oracle SPIR-V; `MMIO` aparte.

## Convenciones

- `PASS` solo integridad / captura física.
- `PARTIAL` admite límites documentados.
- `BLOCKED` sin modificar; código/DB/contratos quedan como están.
- `NOT_DETERMINED` honesto.
