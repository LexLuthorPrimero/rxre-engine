# EXPEDIENTE R3 — Cadena E2E de reconstrucción semántica de filenvercmp/filevercmp sobre /usr/bin/ls (2026-11-12)

**Estado: OPEN — cero divergencias en ambas generaciones selladas (update-5, 2026-11-12); sin dictamen PASS de tercera parte.**
**Update-25 (2026-11-13, etapa 6 — basename, sexto objetivo acotado):** nueva milestone sellada con la misma disciplina: `/usr/bin/basename` (GNU coreutils 9.10, sha256 `1ef9913961b3006d8d5f41718035a8ef7aedcf5f81da46100dffa61421989621`, BuildID `eb755c71c52c5282f84d01ae80ba24e6f0a5e060`) verificada por identidad fail-closed en verify.sh **16 etapas**; propiedad declarada: **último componente acotado** (strip de trailing slashes; si todo se vacía: `/` con leading slash, `.` sin él; componentes `.`/`..` tratados como literales). Corpus sintético seeds **20261114/15** (**1.987/2.013** casos; UTF-8 wide chars + boundary buckets) sellado antes de la hipótesis; reconstrucción C11 independiente `basename_20261114/basewrap.c` (compatible `-Wall -Wextra -Werror`); **0 divergencias** en ambas generaciones (`total=1987/2013 mismatches=0`). `test_discovery_on_basename.py` (2 tests herméticos) integrado a la puerta; pin esperado **80 passed, 2 skipped**. Manifiesto ampliado a **65 artefactos**. Referencias "cinco objetivos" en Update-20/24 y README/QUICKSTART se leen como histórico/superseded a favor de este estado. Alcance NO ampliado: sin flags (`-a`, `-s`, `-z`), sin operando sufijo, sin semántica general de basename. Independencia de terceros: **NOT_EXECUTED**. v1.9.0 etiquetado/publicado con autorización explícita del propietario (2026-11-13).
**Update-26 (2026-11-13, inclusión de la suite semantic-obligation en la puerta):** `tools/rxre/semantic/semantic_obligations.py` (parser SMT-LIB; valida estructura de tres obligaciones BV32 concretas: `x*256 == x<<8`, `x*256 == x*25`, `x*256 == x<<7` — no afirma equivalencia general) y `tools/rxre/tests/test_semantic_obligations.py` (2 herméticos: reconoce las obligaciones esperadas; rechaza `(assert false)` y ancho incorrecto) commitados en `d64f22f`. `verify.sh` etapa 15 ahora ejecuta esa suite y el pin por defecto sube de **80 passed, 2 skipped** a **82 passed, 2 skipped** (los 2 skips siguen siendo los tests que exigen la DB privada del autor). Es integración de una suite ya commitada — **sin** re-sellado (manifiesto intacto, **65 artefactos**), **sin** ampliación de scope y **sin** nuevo objetivo sellado. Referencias vivas de conteo actualizadas (README, QUICKSTART, reviewer-kit); el conteo **80** en Update-25 y §1055 se conserva como registro histórico de v1.9.0. Terceros: **NOT_EXECUTED**.
**Update-27 (2026-11-13, harness de paridad bounded-vs-producción):** `tools/rxre/parity/bounded_parity.py` — herramienta genérica para verificar si una implementación acotada coincide con la producción/referencia completa en un corpus de probes declarado por el caller. Protocolo: cada probe = archivo del corpus; `bounded` y `reference` se ejecutan como subprocesos con el probe por stdin; veredictos por probe: **PARITY** / **DIVERGENT** (probe identificado) / **INCONCLUSIVE** (bounded no determinista — doble corrida exige identidad, o no corre, o exit≠0; referencia no corre o exit≠0). Corpus vacío o contrato inválido ⇒ fail-closed (exit 3). Comparación: `stdout-equal` (default) | `exit-equal` | `json-field:NOMBRE`. Es la disciplina demandada por el bug de REA #10172 (Unicode Path “último gana” en el decoder vs escaneo acotado devolviendo el primero), generalizada: cualquier bounded view del motor puede ahora contraponerse a la herramienta completa. `tools/rxre/tests/test_bounded_parity.py` (6 herméticos) commitado; `verify.sh` etapa 15 lo ejecuta; pin por defecto **82 → 88 passed, 2 skipped**. **Sin** re-sellado (65 artefactos intactos), **sin** ampliación de scope, **sin** nuevo objetivo; sin tag ni release; README/QUICKSTART/reviewer-kit/cuenta actualizados en consecuencia; referencias a 82 en Update-26 se conservan como histórico. Terceros: **NOT_EXECUTED**.
**Update-28 (2026-11-14, ZIP bounded-view verification of REA zip bounded views):** `tools/rxre/parity/rea_verify_zip_bounded_views.py` (stdlib-only) — generates three synthetic ZIP fixtures exercising the REA bounded ZIP directory scan (`scanZipDirectory`): two conflicting version-1/CRC-matching Unicode Path extra fields (`hidden/` then `settings.json`), the same shape with a CRC-invalid final field (fallback-to-stored-name path), and the UTF-8 flag precedence case over a single valid Unicode Path field (`café.json`, stored-name win). Invokes `scanZipDirectory` from the built REA dist via Node.js and compares against an independent Python model; verdicts PARITY / DIVERGENT / INCONCLUSIVE. Runs add-ons: Python-only model tests in `tools/rxre/tests/test_rea_verify_zip_bounded_views.py` integrated to `verify.sh` (pin **88 → 94**). **No re-sellado** (65 artefactos intactos), **sin tag ni release**, sin afirmaciones sobre REA ≠ zip.js; para el flujo de REA vs. producción, su verificación real pertenece al PR #10428. Terceros: **NOT_EXECUTED**.
**Update-32 (2026-11-14, verificación de features en artefacto empaquetado):** `tools/rxre/parity/check_release_features.py` (stdlib-only) — verificador reutilizable de marcadores de bytes en árboles de paquete (release notes ≠ artefacto, linaje REA #7680); exclusión VCS/`node_modules`/`.turbo`; symlinks fuera; >8 MiB skipped. 9 tests herméticos; puerta **120 → 129 passed, 2 skipped**. Dogfood sobre `morluto/rea` (consciente, no afirmado sobre el tarball publicado): `REA_MCP_TOOL_FAMILIES` presente en `dist/`; rc=1 correcto sobre marker inexistente. **No re-sellado** (65 artefactos), **sin tag ni release**. Terceros: **NOT_EXECUTED**.
**Update-31 (2026-11-14, verificación de enlaces/anchors en docs Markdown):** `tools/rxre/parity/check_md_links.py` (stdlib-only) — verificador reutilizable de integridad de documentación tras reorganización: enlaces relativos inexistentes, anchors que no nombra un heading o un `<a|div id>`, escape de root rechazado, code blocks ignorados, enlaces de esquema y absolutos omitidos (sin red). Slugify estilo GitHub con ZWNJ/ZWJ+marks conservados (aproximación). Dogfood sobre el árbol de `morluto/rea`: **0 rotos** (533 archivos .md, 3559 links relativos). 10 tests herméticos; puerta **110 → 120 passed, 2 skipped**. **No re-sellado** (65 artefactos), **sin tag ni release**. Terceros: **NOT_EXECUTED**.
**Update-30 (2026-11-14, POSIX PTY-SIGHUP probe):** `tools/rxre/parity/pty_sighup_probe.py` (stdlib-only) — verificador reutilizable del invariante de semántica de sesiones detrás de REA #8780: bajo PTY con el hijo como líder de sesión, el kernel entrega `SIGHUP` al grupo en primer plano al salir el líder (como `script -c`/`ssh -t`); un hijo forkeado sin `setsid` muere — ni framework ni limpieza hacen nada. Fixture embebida (sesión-líder que forkea nieto con tick loop + log de señales); modos direct/pty; veredictos `PTY_SIGHUP_CONFIRMED`/`MISMATCH`/`INCONCLUSIVE`; `--json`. 5 tests herméticos; puerta **105 → 110 passed, 2 skipped**. **No re-sellado** (65 artefactos), **sin tag ni release**, sin afirmaciones sobre macOS/Windows; la verificación del doc de REA pertenece al PR #10466. Terceros: **NOT_EXECUTED**.
**Update-29 (2026-11-14, documentación-vs-realidad de instalación — verificador reutilizable):** `tools/rxre/parity/check_install_pins.py` (stdlib-only) — verificador genérico de pins de instalación en documentación: invocaciones sin versión (desnuda, `@latest`, dist-tags `next/beta/canary/rc`), desalineación pin ↔ `package.json`, y URL de instalador paste-and-curl que siga `main`/`HEAD` en vez del tag `<pkg>-<version>`. Sin acceso a la red; lee solo el árbol. Éxitos sospechosos invisibles: un pin costoso de falsificar es la omisión — por eso falla cerrado. Exclusiones por defecto: CHANGELOG y corpus histórico de errores; marcador `install-pin: allow` en la línea o la vecina; placeholders `<...>`/`${...}` no evaluables. Reporte JSON (`--json`), reglas `unpinned-invocation`/`stale-pin`/`unstable-installer-ref`. 11 tests herméticos (`tools/rxre/tests/test_check_install_pins.py`); puerta **94 → 105 passed, 2 skipped**. **No re-sellado** (65 artefactos intactos), **sin tag ni release**. Dogfood sobre el árbol de `fix/pin-install-commands` (PR #10463 de `morluto/rea`): 285 hallazgos en la rama base (279 invocaciones desnudas, 4 instaladores a `main`, 2 pins obsoletos); tras el barrido + residuos, **0 hallazgos**. Los 7 residuos que el barrido manual pasó por alto (2 URLs `main/install.sh`, `@6.4.0` en el ejemplo de Grok Bot, marcador para el ejemplo narrativo de issue #5259, placeholders `<version>`) fueron corregidos en la misma rama (`033abb8b0`). Terceros: **NOT_EXECUTED**.
**Update-20 (2026-11-13, coherencia pública + replay full-operation):** (i) documentos sync one command `sh evidence/r3/verify.sh` — README/QUICKSTART/verify.sh header-summary expresan ahora cinco objetivos (filenvercmp/wc/fold/tr/dirname) y los cinco binarios con identidad fail-closed; manifiesto 60 artefactos reflejados; (ii) `evaluate_contract()` ya no basta con un campo observation no vacío: la puerta jerárquica exige carga verificable (struct con method/findings/observations y referencia al target propio) — prueba `test_5c` permanece rechazando payload vacío; (iii) `replay_operacion()` re-ejecuta la operación usando el payload `request_json` original completo (parámetros + backend config + timeout), no una llamada derivada ad-hoc, y registra diferencia entre la invocación original y la replay — por vez primera, la equivalencia declarada es de operación, no solo de resultado; (iv) `verify_reinvestigation()` mantiene su frontera (booleanos declarados por el resultado; no hay evaluador independiente ejecutable) — documentada como limitación asumida; (v) 5 Arangúrico del motor: pendings — P0 (MENTE integración con reconstructor, challenge/disección sobre binarios desconocidos), P1 (replay full-trust). Terceros NOT_EXECUTED.

**Update-7 (2026-11-13):** verificación extendida — añade comprobación de identidad SHA-256 de los binarios nativos (fail-closed) antes de cualquier salto, incorpora el challenge corpus (3.100 + 141 = 3.241 casos, todos `mismatches=0`), el test de invariancia de locale (C ≡ es_AR.utf8, 2×34.145 byte-identical), el i18n black-box (200 nombres UTF-8 vs `ls -v` nativo; sort_names compiled from the reconstruction,byte-comparadas al snapshot del oráculo), y el número real de tests pytest (20) y no uno inscrito a mano. El manifiesto sellado ahora vincula 42 artefactos.

**Update-8 (2026-11-13):** reparación de mecanismos de admisión y replay (revisión estática externa, HEAD 5cd7b47): (i) `evaluate_contract()` ya no puede producir COMPLETE/VALID sin que la puerta de integridad (validate_evidence_path: hash+tamaño+esquema) devuelva ok; (ii) `analyze_dependencies()` y `replay_operacion()` usan `request_json.target`, nunca sustituyen por otro artefacto, y sólo validan evidencia vinculada al artefacto solicitado; (iii) `replay_operacion()` calcula el SHA-256 del solicitado ANTES de ejecutar el backend y aborta fail-closed en discrepancia; (iv) capability distinta de binary.inspect devuelve UNSUPPORTED explícito; (v) verify.sh incorpora test_replay_mision.py (23 passed, 2 skipped honestos sin la DB privada del autor); (vi) cobertura UTF-8 3.89% acotada al corpus original 20261112/13 — el challenge corpus es deliberadamente lo contrario; (vii) conteo challenge unificado: 3.100 + 141 = 3.241 (hito 13/13b). Secciones históricas superadas marcadas explícitamente más abajo. La independencia de terceros sigue NOT_EXECUTED.

**Update-9 (2026-11-13):** reparación Fase 1–4 de la auditoría estática externa posterior a v1.3.0 (HEAD c823b49): (i) `validate_evidence_path` exige ahora artefacto no vacío, hash estricto 64-hex, tamaño int positivo y coincidente, procedencia/e2e_id explícitos y **ligadura artefacto solicitado ↔ evidencia** (`evidence_target_mismatch`); (ii) `evaluate_contract()` exige `ejecucion.status == "ok"` EXACTAMENTE (vía rama BLOCKED explícita para ejecucion=error/no-ok) y `target_artifact_id` opcional que liga la evidencia al solicitado (mismatch ⇒ nunca COMPLETE/VALID); (iii) `verify_reinvestigation()` rediseñado: sin evidencia ⇒ BLOCKED absoluto; dry_run ⇒ UNRESOLVED jamás; acción de plan requiere condición demostrada y evidencias verificadas (resolver por omisión imposible); (iv) `analyze_dependencies()` trata `tool_version` y `repository_commit` como dependencias duras faltantes; (v) `replay_operacion()` rechaza ejecutar sin identidad registrada (`blocked_insufficient_identity`) y devuelve objeto `equivalence` (EQUIVALENT/PARTIAL/DIVERGENT/NOT_DETERMINED) sin mezclar señales positivas en `differences`; (vi) nuevas suites herméticas `test_replay_matrix.py` (11) y `test_evidence_gate_matrix.py` (12) integradas a verify.sh ⇒ **44 passed, 2 skipped** en clon público; test_integridad test_5 reescrito (asociación ajena ⇒ inaceptable) + test_5b positivo añadido; test_orchestrator_e2e: dry_run jamás RESOLVED. Lo demás (reconstructor M263/M268, MENTE) **no tocado**: requiere decisión del propietario. La independencia de terceros sigue NOT_EXECUTED.

**Update-10 (2026-11-13, Fase 5):** desacople del conocimiento histórico ls/grep del reconstructor (autorizado): tablas _M263_LS/_M263_GREP/_M263_CAUSAL/_m263_causal extraídas a perfiles JSON hash-vinculados (`tools/rxre/semantic/experimental_profiles/m263_{ls,grep}.json`, ls=sealed 54e936d3…, grep=f0320b67… del M675 sellado); `profiles.py` aplica el perfil SOLO con coincidencia de SHA-256 del binario (sin coincidencia ⇒ CONDITION_UNKNOWN, cero herencia histórica); el bloque M268 era efectivamente INOPERANTE (callsite_offset jamás coincidía con la edge) — corregido de raíz; `profile_note` registrado en el expediente (perfil aplicado o genérico). test_m263_profile_binding.py (5 herméticos) integrado a verify.sh ⇒ 49 passed, 2 skipped. BUG latente del M268 reparado (OBSERVATION_BLOCKED ahora funciona de verdad).

**Update-11 (2026-11-13, auditoría F1-F3 + infraestructura):** (i) `evaluate_contract()` exige ahora, además de integridad y ejecucion `ok`, **observación semántica verificable** en el resultado (ningún resultado meramente `declared` alcanza COMPLETE/VALID); (ii) equivalencia en replay: **normalización recursiva** árbol completo (sin intersecciones cosméticas); `reproducible=True` sólo si EQUIVALENT sobre TODOS los campos (PARTIAL ⇒ reproducible=False; campo ausente/inesperado ⇒ PARTIAL/divergente); (iii) `verify_reinvestigation()`: clasificación declarada por el resultado NUNCA sustituye a `condition_satisfied is True` + `dependencias_verificadas is True` explícitas; classification "VALID" sin condición demostrada ⇒ UNRESOLVED; (iv) reconstructor: `rz_dataflow` desanunciado del docstring (no integrado), presupuesto global compartido por CFG/pdfj/readelf/instrucciones, cobertura con denominador de ELEGIBLES (no de descubiertos), `_rizin_cfg` señalado como único proveedor; (v) verify.sh ahora **fija por defecto 52 passed / 2 skipped** (fail-closed; override documentado por env para el host del autor con DB privada); (vi) Dockerfile pinned a digest de `fedora:44` resuelto via podman (`15da97ed…`), comment honesto (paquetes internos sin pin individual); (vii) test_integridad test_5c añade caso requerido; test_replay_matrix añade tests verify_reinvestigation + PARTIAL⇒reproducible=False. La independencia de terceros sigue NOT_EXECUTED.

**Update-12 (2026-11-13, MENTE etapa 1):** implementado motor mínimo de hipótesis rivales `tools/rxre/semantic/mente.py` (selección por poder discriminante entre predicciones; ejecución única del objetivo; contradicción falsificada; jamás etiquetas PROVEN; dominio declarado; una hipótesis contradicha queda REFUTED, nada más). Experimento sintético end-to-end: dos variantes compiladas on-the-fly con SHA distintos; MENTE elige la entrada discriminante, observa y refuta SÓLO la hipótesis incorrecta; caso gemelo indistinguible ⇒ NOT_DETERMINED declarado. 8 tests herméticos nuevos (62 total en la puerta: 60 passed, 2 skipped). Pre-requisito para etapa 2/3 (R3-domain dry run / objetivo real nuevo). terceros NOT_EXECUTED.

**Update-13 (2026-11-13, MENTE etapa 2 — dry-run sobre datos sellados):** `test_mente_diskoverido.py` (3 casos herméticos públicos): seleccion de 34.145 parejas selladas gen-1 de filenvercmp por poder discriminante entre rivales ingenuamente plausibles (modelos FLAT vs NAIVE_VER); observación exclusivamente desde `matrix_native.txt` (sin ejecutar nada nuevo); hipótesis contradicha ⇒ REFUTED; gemelo indistinguible ⇒ NOT_DETERMINED; cero PROVEN en el reporte; la prueba demuestra que el mecanismo de discriminación funciona sobre corpus reales sellados. Gate verify.sh: **63 passed, 2 skipped**. Nada de esto promueve etiquetas. Terceros NOT_EXECUTED.

**Update-14 (2026-11-13, MENTE etapa 2b):** experimento hermético público sobre `wc -L` UTF-8 sellado: modelo de anchura propio (Unicode EAW + combinantes=0 + jamo conjoining=0 + soft hyphen quirk=1 medido + TAB→siguiente stop de 8 + tabs de línea por Cc) — **reproduce el oráculo sellado en 1523/1523 casos** sin consultar ningún modelo privado. Rivales BYTES y CODEPOINTS refutados por el resultado sellado; el rival WCWIDTH-APPROX sobrevive NOT_DETERMINED; ninguna etiqueta promovida. **v1.3.5 `rxre-engine-1.3.5.zip` "promises" this experiment but precedes its realization; superseded by v1.3.6** with the actual test and gate at 66 passed, 2 skipped. Independencia de terceros: NOT_EXECUTED.

**Update-15 (2026-11-13, etapa 3 — fold, tercer objetivo):** nuevo milestone `fold` PROPERTY reconstruction sellada con el mismo método: corpus sintético con semilla 20261113/14 (2.554 casos c/u, UTF-8 válido, clases acentuadas/asiáticas/combinantes/tab/Cf/fullwidth), oráculo `/usr/bin/fold -w 4` invocado por stdin, salidas prefijadas por caso. Reconstrucción independiente (foldwrap.c, 142 líneas C11): EAW W/F=2, Cc/Cn/Cs/Co/Mn→0, jamo conjoining U+1160–11FF→0, soft-hyphen 0xAD→1 (quirk medido en el oráculo), tab→avance al siguiente stop de 8, col+cp > w ⇔ salto ANTES del cp con contenido previo no vacío; línea vacía puede desbordarse. Verificación en verify.sh (13 etapas): dos generaciones, 2×2554, **0 divergencias**. Append-only en el manifiesto (47 artefactos) + FAIL-CLOSED identidad pin de `/usr/bin/fold` (sha256 95030461…, coreutils-9.10-5.fc44). Alcance declarado: sólo `-w 4`, UTF-8 válido, sin flags; NO se afirma sobre glibc wcwidth ni sobre `-s/-b/-g`. Independencia de terceros: NOT_EXECUTED.

**Update-16 (2026-11-13, fold multi-width):** el milestone `fold` pasa de único ancho (-w 4) a seis regeneraciones selladas/gated: -w 4 × seeds 20261113/14 (2.554 c/u, 0 divergencias) **y** -w 1/2/3/8 con semillas 20261115/16/17/22 (1.054 c/u, 0 divergencias). `foldwrap.c` y `gen_fold_cases.py` parametrizados por width en argv[2]/argv[4] (**fix mismo-sesión**: 1 ajuste de sign-compare a -Werror=sign-compare para cumplir la puerta). Manifiesto actualizado (sin re-escribir líneas; total 47 artefactos + 4 nuevos = sigue siendo el mismo conjunto con joiner de orden verificacion 42→51; SEAL.txt actualizado con los seis renglones). Alcance sin cambios: propiedad de ancho acotado, UTF-8 válido, sin dicción sobre flags/glibc wcwidth; terceros NOT_EXECUTED.

**Update-17 (2026-11-13, MENTE etapa 4):** `test_mente_fold_rivals.py` hermético end-to-end sobre **fold sellado**: rival BYTES/CODEPOINTS refutados por el oráculo (el oráculo wrap-typed -w 4 en celdas Unicode); rival WCWIDTH survive NOT_DETERMINED; gemelo indistinguishable; cero PROVEN. Además, test de equivalencia verificadora: el clone NODEMENTE de la semántica WCWIDTH reproduce **byte-exacts los 2.554 casos sellados**. Gate verify.sh 13 etapas, pin **69 passed, 2 skipped**. Terceros NOT_EXECUTED.

**Update-18 (2026-11-13, etapa 5 — tr, cuarto objetivo):** nuevo milestone `tr` PROPERTY reconstruction sellada con misma disciplina: verificación independiente en C11 (`trwrap.c`, greedy squeeze de runs consecutivos de byte `0x78` — sin -c/-d/-s-multi-arg/Unicode classes), corpus sintético seed 20261113/14 (2.513 casos c/u; sesgo fuerte a runs de x; 0 divergencias en ambas), identidad fail-closed pin de `/usr/bin/tr` (sha256 b1d1bfbe…), manifest ampliado a 56 artefactos, verify.sh en **14 etapas** (fold etapa 11, tr etapa 12, suites 13, cobertura 14). Alcance acotado: solo `tr -s x`, stdin→stdout; sin flags, sin clases; NO se afirma dicción general. Terceros NOT_EXECUTED.

**Update-19 (2026-11-13, etapa 5-bis — dirname, quinto objetivo):** nuevo milestone `dirname` PROPERTY reconstruction sellada: algoritmo verificado (trailing-slash strip; if empty split by leading-slash; last-slash prefix stripped; empty prefix → leading-lowercase truth). Corpus sintético seed 20261113/14 (1.917/1.901 casos, UTF-8 wide chars incluidos); reconstrucción C11 independiente (`denwrap.c`, mismas reglas en código); verificación verify.sh **15 etapas** con nueva stage dirname (13/15) y fail-closed identity pin de `/usr/bin/dirname` (sha256 aac6a889…). Manifiesto extendido a 60 artefactos. Alcance acotado: una única propiedad; sin flags; terceros NOT_EXECUTED.

**Update-21 (2026-11-13, P0 — descubrimiento MENTE + bug crítico latente en reconstructor):** (i) `tools/rxre/semantic/discovery.py` nuevo: partiendo de un binario ELF cualquiera `rizin` descubre `FUNCTION_CANDIDATE` con CFG validado (bug latente RESUELTO antes de continuar: faltaba import de `subprocess` y `json` en ámbito de `_rizin_cfg`; _además_ faltaba importar `json.loads` correctamente — todos los binarios analizables quedaban `ANALYSIS_FAILED`); (ii) `test_discovery_unknown.py` hermético: 2 tests, uno `discover_unknown_function` sobre binario misterio en tmp_path (gathering FUNCTION_CANDIDATEs with real CFG + rivals from .rodata literals; segundos test `mente_cycle()` rivals survive vs reถูkriticos); (iii) historicamente significativo: `reconstruct()` sobre binarios nuevos no funcionaba — todos los CFG quedaban en `ERROR` (bug asignado a `_json` → `json` + `subprocess`/`re` module scope) -> ahora CFG produciendo 6/11 FUNCTION_CANDIDATE; (iv) P0 permanece abierto: discovery rival generation + MENTE cycle funcionan pero ninguna `semantics → VALID` por fuera del dominio sellado; se prepara v1.6.0 para contener estas correcciones. Terceros NOT_EXECUTED.

**Update-22 (2026-11-13, P0 testing sobre binario real):** `test_discovery_on_dirname.py` añade prueba de `/usr/bin/dirname` end-to-end; discovery no explota ni segfaultea, produce un FUNCTION_CANDIDATE exactamente verificable contra rizin (rizin -A; cfg_blocks, nbbs), produce rivals desde .rodata vía `rizin izj` (literals ahora filtrados a sección .rodata exclusivamente, no strings binarios), `_no_profile_imported == True`, semantics_status NOT_DETERMINED. Manifiesto extendido; verify.sh espera pins **76 passed, 2 skipped**. Terceros NOT_EXECUTED.

**Update-23 (2026-11-13, MENTE multi-round):** `mente_cycle()` ahora ejecuta rondas ITERATIVAS (`mind_budget=0` default grows with rival count), seleccionando al input que MÁXIMAMENTE discrimina cada ronda; rechaza inputs duplicados automáticamente (`used_inputs`); report completo histórico (`observations`). Verificado en `test_discovery_loopbench` hermético: objetivo real compilado y encerrado en tm_dir; contra ground truth = prefix-only match, rivals `NULL`,`LEN5`,`EXACT` refinidos (EXACT queda refutado por `"alphabet"`; PREFIX sobrevive; status NOT_DETERMINED). Gate verify.sh ahora: expected pin **77 passed, 2 skipped**. Terceros NOT_EXECUTED.

**Update-24 (2026-11-13, P0 closed loop lab end-to-end):** `test_discovery_synthesis.py` ejecuta EL PRIMER bucle completo discover→synthesis→diff verificar en un binario desconocido: `strings` desde rodata → rivals → differential contra el binario original byte-a-byte en ~24 inputs; `0 mismatches`; identidad sha256 sellada para binario original y sintetizado. Integración en verify.sh desde pin **78 passed, 2 skipped**. Honestidad: es sobre target simple con literales visibles; no prueba capacidades generales ni en binarios modernos. P0 remains open para binarios sin literales rodata. Terceros NOT_EXECUTED.

**Update-6 (2026-11-13):** verificación unificada en un único comando: `sh evidence/r3/verify.sh` — 32 artefactos sellados vs `manifest.txt`, filenvercmp (2×34.145) + wc (11 corpora) + 12/12 suites Python. Las 791 divergencias originales fueron resueltas (reconstrucción por transcripción literal del desensamblado) y verificadas en dos generaciones selladas (34.145 + 34.145 casos), 3 toolchains y sandbox bwrap. No se habilita producción ni generalización; la verificación autónoma de terceros (fuera de este host/autor) permanece NOT_EXECUTED.

## 1. Objetivo y alcance
- Binario objetivo: `/usr/bin/ls` (sha256 `54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c`; BuildID `ae6605eeca6cc2f19d18fdd53a521e501df3456d`; 153 400 B; ELF64 PIE stripped; `.text` vaddr `0x10c0`).
- Función semántica: `filenvercmp` / `filevercmp` en vaddr `0x4fa0` (contiene `verrevcmp` en `0x4b60` y `file_prefixlen` en `0x4a80`).
- Alcance declarado: **solo** `filenvercmp` y su subcadena léxica; no se amplía a otras funciones, otros binarios ni a integraciones productivas.
- Restricciones de la misión respetadas en ejecución: sin GPU física, sin `sudo`, sin `--auto`, sin `op:claim`, sin bucles autónomos, sin modificar repo/relativos, sin tocar Plan Maestro (hasta autorización explícita posterior del 2026-11-12), `AGENTS.md` intacto.

## 2. Método aplicado
EVIDENCE → SEMANTICS → SCHEMA → DISCRIMINATING TEST → IMPLEMENTATION → VALIDATION, acumulado:
1. Identidad verificada del ELF (sha256, estat, BuildID, `readelf -h`, secciones `.text`/`.rodata`).
2. `objdump -d` de cada función objetivo hacia `/tmp/rxre-r3/evidence/*.asm`.
3. Generador determinista propio de casos (`oracle/gen_cases.py`, SEED=20261112 con ~123 base×123 base+6.000 aleatorios): `cases_seed20261112.txt`, sha256 `bfa30fb358…`.
4. Oráculo independiente por mmap de `/usr/bin/ls`: `oracle/matrix_gen` (sello `matrix_native.txt`, sha256 `ed5e91ef…`, 34.145 líneas, 0 errores de ejecución).
5. Reconstrucción fresca desde desensamblado y comportamiento diferencial (`reconstruction/filenvercmp.c`, compilada `-std=c11 -Wall -Wextra -Werror -pedantic`, rc=0).
6. Diferencial ejecutada con `harness/verify_recon` (no se modifica la semántica del harness).

## 3. Componentes verificados con evidencia positiva
| Componente | Método | Resultado |
|---|---|---|
| Comparador de byte único (posición 0 / 1..255) | `pair_matrix_255.csv` (32.385 pares, `probe255`); `pair_matrix_interior.csv` (32.385 pares, `probe_interior` @ posición 1 post-byte fijo `q`) | **0 / 32.385** discrepancias en la semántica de un byte (modelo afín `rc = RANK[i]−RANK[j]` con tres excepciones catalogadas) |
| `file_prefixlen` | 7.320 cadenas estructuradas (`prefix_scan2.txt`, `probe_prefix`) | **7.320 / 7.320** exactitud (regla «longest trailing letter/~ init segment»; `out_len == strlen` en todos) |
| `w_end_probe` (sintaxis de fin de lado) | 255 bytes | **255 / 255** match con tabla `w_of` (letras `c+1`; dígitos `{0}→0,{1..9}→1`; demás `c+257`; `~ → −1`) |
| Punto vs grupo de dígitos fuera de cadena | `pair_matrix.csv` (8.001 pares en bytes 1..127) | Tabla completa transitiva y antisimétrica, 0 violaciones; comportamiento de `.` y `~` en posición 0 capturado |

> **[SUPERSEDED 2026-11-12, update-5 — ver §11: las 791 divergencias fueron resueltas; esta sección preserva el estado histórico.]**

## 4. División en objetivos secundarios abiertos (791 discrepancias)
Ranuras divergentes principales:
- **777** casos con al menos un `.` en el interior (clase `dot-mid`): incluye `'a!b' vs 'a.'`, `'R96]'9B' vs 'R.'`, `'a.1.10' vs 'a.1.010'`.
- **14** casos con dot-leading múltiple (##`both-dot`): `'...' vs '.a'`, `'.a~' vs '...'`.

Las tres piezas verificadas no son suficientes para cerrar la cadena: **el anidamiento la ↔ prefix en puntos iniciales/medios no reproduce el comportamiento nativo completo** (la rama de extensión de `.` en `verrevcmp` y el encadenamiento `->file_prefixlen->verrevcmp` necesita más evidencia).

> **[SUPERSEDED 2026-11-12, update-5 — §11 demuestra cero divergencias en ambas generaciones; la tabla de abajo describe el estado al cierre de la fase de objetivos secundarios.]**

## 5. Resultados
| Eje | Veredicto |
|---|---|
| Identidad del binario | VERIFIED |
| Oráculo sellado (R3, 34.145 casos) | VERIFIED en integridad de artefactos; comportamiento diferencial repetible |
| Reconstrucción vs oráculo | **PARTIAL / OPEN** — 791/34.145 (97,7 %) match; 0 discrepancias solo en los tres subcomponentes aislados |
| Generalización a otros binarios/funciones | NOT_VERIFIED (fuera de alcance por objetivo) |
| Segunda generación independiente (seed 20261113) | NOT_EXECUTED (bloqueada por criterio "cero discrepancias en primera generación") |
| Integración en producción | NOT_AUTHORIZED / NOT_CLAIMED |
| `op:claim`, `--auto`, `sudo` | NOT_USED |

## 6. Sellado y artefactos (citado en `/tmp/rxre-r3/records/final_package.sha256`)
- Entradas selladas: `cases.sha256`, `matrix_native.sha256`, `pair_matrix_255.csv`, `pair_matrix_interior.csv`, `w_end_probe.csv`, `prefix_scan2.txt`, `final_package.sha256`, `recon_final.sha256`, `SEAL.txt`.
- Registros obsoletos preservados en `records/stale/` (sin destrucción).

## 7. Prohibición de afirmar capacidad cerrada
Ningún elemento de esta sección autoriza integrar, promover o declarar completo ni la reconstrucción ni `filevercmp` sobre `/usr/bin/ls` ni sobre otro binario. Los resultados parciales están registrados como tales, sin conversión etiqueta-capacidad.

## 8. Registro en el Plan Maestro (actualización documental autorizada 2026-11-12)
- Addendum `## 1044. R3 — …` añadido a `RXRE_PLAN_MAESTRO.md` (copia principal `rxre/` y copia espejo `documentacion/`; contenido idéntico byte a byte, sha256 `8e43e578…`).
- Fuente del addendum: `records/PLAN_MAESTRO_ADDENDUM_R3.md` (7.237 B, sha256 `f5f4455f…`).
- Sección addendum, no sustituye el histórico §1036–§1043; ninguna sección anterior fue modificada.
- El Plan Maestro no forma parte del índice git (`?? RXRE_PLAN_MAESTRO.md`); ningún compromiso git es aplicable. `AGENTS.md`, `rxre.sqlite3`, `core/store.py`, contratos y `jorgeeee.md` intactos.
- Segunda y tercera copia física del Plan Maestro: no localizadas; discrepancia documentada en §1044.7 (no se afirma `SYNC_OK ×3` sin evidencia).

## 9. Identidad oficial publicada (2026-11-12)
- `RXRE_IDENTIDAD.md` creado en la raíz del repo (513 B, sha256 `cce22881ef…`) con la declaración (A)+(B) aceptada. No se reescribió ningún documento histórico.
- `RXRE_PLAN_MAESTRO.md` actualizado con `## 1045. IDENTIDAD OFICIAL DE RXRE (2026-11-12) (G1045 PUBLISHED)`; fuente del addendum `records/PLAN_MAESTRO_ADDENDUM_IDENTIDAD.md` (3.992 B, sha256 `467694ad…`).
- Plan Maestro sincronizado byte a byte en las dos copias existentes: `rxre/RXRE_PLAN_MAESTRO.md` y `documentacion/RXRE_PLAN_MAESTRO.md` — sha256 `e45e80722cb2b34fb6f644f9eae5503f4d52ea8af9733ad47b888993c8b04885`; `cmp` OK; `wc -c` = 1.724.407 B.
- Ninguna otra pieza fue modificada: `AGENTS.md`, `rxre.sqlite3`, `core/store.py`, contratos, README, fixtures y el resto del histórico (§1036–§1044) permanecen intactos. Tercera copia física del Plan Maestro: no localizada; discrepancia explícita preservada en §1044.7/§1045.4.
- Veredicto de §1045: G1045 = PUBLISHED. No se abren misiones automáticamente; pasos siguientes pendientes de autorización explícita en orden de dependencia (aceptar aceptación → ESENCIA → MVP `reconstruct` → métrica externa con autonomía del tercero).
## 10. Resultado
Identidad oficial registrada respetuosamente como addendum; R3 permanece OPEN con su conteo original (791 divergencias, estado histórico al 2026-11-12); ninguna etiqueta promovida; el monumento histórico del Plan Maestro intacto. **NOTA update-5+: §11 resolvió las 791 divergencias; ver §12 y los updates 6–8 en cabecera para el estado vigente.**

## 11. Resolución de las 791 divergencias (2026-11-12, update-5) — cero divergencias en ambas generaciones
Autorización: propietario ("el mas completo"); alcance: cierre de divergencias, segunda generación sellada, verificación acotada. Restricciones preservadas: sin GPU, sin `sudo`, sin `--auto`, sin `op:claim`, sin bucles autónomos; repo, `AGENTS.md`, `rxre.sqlite3`, corpus y oráculos 20261112 **intactos**.

### 11.1 Causa raíz y corrección (solo `reconstruction/filenvercmp.c`)
La reconstrucción previa era un modelo empírico (tabla `RANK` + casos especiales, magnitudes ±1/±303/±302) y no reproducía las **magnitudes exactas** del nativo. Se reescribió como **transcripción literal** de `objdump -M intel` (records/disas_all3.txt; filenvercmp @ 0x4fa0, verrevcmp @ 0x4b60, file_prefixlen @ 0x4a80), acercando la implementación bit a bit al código de máquina: dígitos (runs con `first_diff`, salto de ceros iniciales 4cfd/4d1d, fin-de-cadena vs dígito → ±1),`[A-Za-z]` → `(int)(char)c`, `~` → −2, resto → `(int)c+256`; sentinela fin-de-cadena = −1 (asimétrico para `~`); `file_prefixlen` como extensión dpkg (`.[A-Za-z~][A-Za-z0-9~]*`) y `filenvercmp` con flag «≥1 extensión» que dispara el segundo pase a cadena completa.
Defectos concretos corregidos (difusión 791 → 97 → 86 → 0): (a) rama a-otros vs b-otros (4e72→4bf9→4c00) sin comprobación de igualdad con avance; (b) con `j >= b_lim` y a con dígitos se devolvía `0` en vez de saltar a la maquinaria de dígitos (4ea2→4cfd); (c) `verrevcmp` aplanada (etiquetas/llaves erróneas) y `L_4eq` sin vía de avance igual-byte.

### 11.2 Diferencial completa (oráculo sellado, 20261112)
`gcc -std=c11 -Wall -Wextra -pedantic -Werror -O2` + harness oficial (`verify_recon.c` sin modificar):
`total=34145 mismatches=0` (exit=0). Fuzz diagnóstico (no sellado; alfabeto con `.` `~` y bytes altos): 650.000 pares, 4 semillas, 0 mismatches.

### 11.3 Segunda generación sellada (seed 20261113) — 0 divergencias
Orden causal seal-before-reveal (`records/SEAL_SECOND_GENERATION.txt`):
1. corpus: `python3 gen_cases.py 20261113 cases_seed20261113.txt` → 34.145 pares, `sha256 8333b744b3dc1985648bd54ee432c74770bb78cba18e359ee4779d0acf885873` (sellado ANTES).
2. oráculo: `./matrix_gen cases_seed20261113.txt matrix_native_20261113.txt` → 34.145 líneas, 0 CRASH, `sha256 e031d3ed6d4c6329cf7edcae55b795fbe0d3c0b121fed34839ec8563b60cf6fd` (DESPUÉS).
3. verificación: harness nuevo `harness/verify_recon_seed20261113` (copia; verify_recon.c intacto) → `total=34145 mismatches=0` (exit=0).
Generación 20261112 intacta: `bfa30fb3…` / `ed5e91ef…`.

### 11.4 Verificación acotada independiente (clean-room)
Copias frescas verificadas por hash (`verify/cleanroom/`): 3 toolchains — clang -O2, gcc -O0, gcc -O2 — × 2 generaciones: **6/6, 0 divergencias**.
Aislamiento bwrap (`--ro-bind / /`, tmpfs `/tmp`, HOME fresco): uid=1000; `sha256 /usr/bin/ls` dentro del sandbox = `54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c`; escritura sobre el clean-room denegada (`WRITE_DENIED_OK`); diferenciales 0/0 ambas generaciones dentro del sandbox.

### 11.5 Límites explícitos (NO se ocultan)
- La verificación es autónoma pero **del mismo host, mismo UID, misma persona, mismo modelo**. MODEL_DIVERSITY y diversidad física/host NO demostradas; independencia física E2E-039 permanece **BLOCKED**.
- Tercera parte verificadora independiente (sin intervención del autor): **NOT_EXECUTED**.
- R3 **NO** cierra a PASS; el expediente declara: "cero divergencias en ambas generaciones selladas (verificación propia + acotada)". Declarar PASS requeriría (i) verificación ejecutada por terceros, (ii) revisión humana independiente y (iii) autorización explícita.
- `DIAGNOSTICO_791.md` y `SEAL.txt` conservan su texto histórico (791 divergencias) con este addendum como estado vigente; `records/stale/` intacto.
- AGENTS.md §8.11 (reconocimiento tecnológico exterior, 2026-11-12): nota de alcance presente, no modifica esta cadena; no re-ejecutó suites.

### 11.6 Hashes de artefactos (update-5)
`filenvercmp.c` = `c721c5c6672f5fbbd5896a922efc7a58a71b37b9bd616f46fbefde3bcdfc943d` · harness oficial = `55eacc5d575c349dc4641a73b9c80e330352fa1e0032c128d73f40d15e115c78` · `verify_recon_seed20261113` = `6acfe2570454a488ee761292897b0cf839181a328957d9135570f1e7f8c2f349` · clean-room: clang `004b6801e15adc81496ccab7efd54d568a3266e288fc231a966fd4df6a94d0b7`, gcc-O0 `56bd8a168fafeef6651041d0fcfca3af9271014af143fa2e59a1b0c0d3755a3f`, gcc-O2 `f7824da6c8c3e3ea7eb1d0b2cc84b36fb18ae9914862fa17df2bc25f32efd5cd` · corpus 20261113 `8333b744…` · oráculo 20261113 `e031d3ed…`.

### 11.7 Verificación caja negra end-to-end (binario real, no solo mmap)  [2026-11-12]
Subconjunto determinístico (seed 20261113) de 250 nombres únicos imprimibles del corpus (sin `/` ni crudos; `.`/`..` excluidos), creados como archivos vacíos en un tmpfs limpio (`work/bb2/`): `LC_ALL=C ls -A -v` produce exactamente la secuencia predicha por la reconstrucción con desempate strcmp (contrato de los wrappers `sort=version` @ 0x5170/0x51b0/0x5268/0x5330). Resultado: 250/250 nombres, secuencias idénticas byte a byte. Evidencia diagnóstica (mismo host, mismo binario); no sellada. El binario real ejecutado fue `/usr/bin/ls` nuevamente (sha256 verificado dentro y fuera de bwrap).

## 12. Resguardo de Fase 2/3/4 y cierre documental (2026-11-12, update-6)

### 12.1 Fase 1 — paquete público publicado  [2026-11-12]
Repositorio público: https://github.com/LexLuthorPrimero/rxre-cleanroom (commit 2aa102d, rama master)
Contenido: src/filenvercmp.c, harness/verify2.c, oracle/{cases_seed20261112.txt, matrix_native.txt, cases_seed20261113.txt, matrix_native_20261113.txt}, INDEX.md, PROTOCOL.md, OUTREACH.md, LICENSE, SHA256SUMS. HEAD reproducido con sha256sum -c.
IMPORTANTE: la verificación por terceros sigue **NOT_EXECUTED**; el paquete está preparado para ser refutado; el autor no declara PASS.

### 12.2 Fase 2 — encuesta de objetivo (reconstrucción completa)
Candidato principal: **/usr/bin/wc** — sha256 81d614595c717be908fce809713702efd35ce5a56f5ab7cbc497d1a61eb1a38f · BuildID 07a56ef5bcfd9b400c0dc0441530607b3c7d65f8 · 61.448 B · stripped · dinámico · 72 funciones identificables por objdump. Riesgo: ruta multibyte y locale; sin símbolos; complejidad media-alta. Alcance recomendado: reconstrucción semántica completa por hitos sellados (wc counting loop → lineas → bytes → multibyte) — **no iniciado**; requeriría su propia cadena sellada (corpus seed 20261114 sellado antes del oráculo).
Alternativas descartadas/aplazadas: dirname/basename (demasiado triviales), file (coherencia, demasiado grande), sort -V (arseguria, depende de infraestructura de comparación no resuelta).

### 12.3 Pre-registro de criterios de cierre del motor (antes de verlo)
El "motor" solo puede declararse en esas condiciones: (1) ≥1 binario reconstruido E2E con cero divergencias en su corpus sellado; (2) SEGUNDA generación independiente también a cero; (3) verificador humano/tercero autónomo confirmado o refutado por escrito (dictamen propio, no del autor); (4) al menos un consumidor demo o uso externo documentado. Hasta entonces: OPEN.

### 12.4 Métricas soberanas (revisión escrita semanal)
- réplicas externas confirmadas (nº, nombre público, fecha) 
- binarios con cero divergencias verificadas por terceros (nº)
- hallazgos refutados/corregidos desde la publicación (nº, con hashes)
- ratio documentos narrativos nuevos / verificaciones de terceros (objetivo: 0)
- blocked items cerrados vs abiertos (ky ora PUERTA cond.3: PENDING_EXTERNAL_REVIEWER)

### 12.5 Verificación de integridad vigente (solo lectura) — tools/rxre/verify_integrity.sh
Ejecutada 2026-11-12: fallos=0; suites 7/7 re-ejecutadas rc=0; informe: AGENTS_ESTADO_GENERADO.md.

## 13. Fase 2 hito 1 — /usr/bin/wc: corpus y oráculo sellados; modelo 0 divergencias (LC_ALL=C, salida por defecto)  [2026-11-12]
- Binario: /usr/bin/wc — sha256 81d614595c717be908fce809713702efd35ce5a56f5ab7cbc497d1a61eb1a38f · BuildID 07a56ef5bcfd9b400c0dc0441530607b3c7d65f8 · 61.448 B · stripped · dinámico. .text 0xc40–0x9092; vía unibyte (ctype locale C) vs vía multibyte (mbrtowc/iswspace/wcwidth) identificadas en disasm.
- Corpus sellado (seal-before-reveal; records SEAL_WC.txt): seed 20261114 (4899) sha256 4a2b85bb…; seed 20261115 (4914) bb21a816… — ambos ANTES del oráculo.
- Oráculos nativos (LC_ALL=C): 20261114 sha256 20842467…; 20261115 sha256 72cfcecd… (0 CRASH).
- Modelo wc_recon.c: 0 divergencias en ambas generaciones selladas (+ 20.000 contenidos aleatorios diagnósticos, 0 divergencias).
- NOT_EXECUTED: port 1:1 del disasm; flags (-c -m -l -w -L y -L max-line); domain multibyte/locale; milestone 2ª generación E2E; terceros; PASS.

## 14. Fase 2 hito 2 — wc con flags {-c,-l,-w}: 0 divergencias (seed 20261116)  [2026-11-12]
- Corpus seed 20261116: 11.872 casos (1.484 contenidos × 8 conjuntos de flags) — sellado ANTES del oráculo (SEAL_WC.txt).
- Oráculo nativo (LC_ALL=C, stdin): sha256 adc83227df98ccb304d1574252778628be5e0d776d91b00cf51422ead99f1df0 · 0 CRASH.
- Modelo ampliado (salida GNU orden fijo L W B): 11872/11872, exit=0.
- Dominio NO cubierto: -m, -L (max-line, wcwidth), multibyte, locale, formato alineado a columnas, --files0-from, port 1:1 del disasm.

## 15. Fase 2 hito 3 — wc con -L completo: 0 divergencias (seed 20261117)  [2026-11-12]
- Corpus seed 20261117: 13.072 casos (817 contenidos × 16 conjuntos de flags {default,-l,-w,-c,-L,+combinaciones}) — sellado ANTES del oráculo.
- Oráculo nativo (LC_ALL=C): de2fc092adf8ca47aa0c915bc86c2a7e086d4cf3cbecb82ca76b3e8bb865b6df · 0 CRASH.
- Semántica -L verificada empíricamente: {\f,\r} = reset de columna (ancho 0, sin línea); tab→8; printable=1; otros=0; max por posición.
- Modelo: 13072/13072 · exit=0 · fuzz diagnóstico -L: 0/30000 · sin regresiones (20261114/15/16 verdes).

## 16. wc hito 4 (intermedio) — validación oráculo↔oráculo de --files0-from  [2026-11-12]
Resultado: 4899/4899 (20261114) y 4914/4914 (20261115) contenidos idénticos entre `wc FILE` directo y `wc --files0-from=manifest` (un archivo por caso, LC_ALL=C). El modo --files0-from enruta al mismo contador de archivos por caso (evidencia adicional de que la vía argv→file-count y --files0-from→file-count convergen en el mismo resultado).
NOT_EXECUTED: extensión de la reconstrucción para --files0-from (multi-file arg loop, formato de salida con múltiples filas); milestone 4 E2E completo.

## 17. Fase 2 hito 5 — bytes altos/multibyte: seed 20261118; defecto real corregido  [2026-11-12]
- Corpus seed 20261118: 1.184 — gen_wc_high_cases.py: structured + random con bytes >= 0x80 y UTF-8; sellado ANTES del oráculo (91e6dbbf…).
- 2 oráculos (LC_ALL=C / es_AR.utf8): 706/1184 difieren (locale importa para bytes altos; es lo esperado).
- Probe binario: separador en LC_ALL=C = {09,0a,0b,0c,0d,20,a0}; en es_AR.utf8 = {09,0a,0b,0c,0d,20}.
- DEFECTO REAL: modelo omitía 0xa0 en LC_ALL=C → 755 mismatches; corregido → 1184/1184 C-locale + sin regresiones.
- UTF-8 (es_AR.utf8): 706 mismatches residuales — fuera de alcance del modelo ASCII fijo; pendiente UTF-8 (2ª vía).
- Lección: el corpus ASCII-only de los hitos 1–3 ocultó el defecto (igual que random_diff 20.000 pasaba sobre la clase .1.10) — el corpus debe tocar TODOS los ejes del dominio.

## 18. Nota importante sobre hitos 1–3 ("0/0")
Los corpus 20261114–17 no ejercitaban bytes >= 0x80 → el defecto en 0xa0 quedó latente; los hitos 1–3 NO son evidencia de que LC_ALL=C esté completamente cubierto. Hito 5 corrigió y selló esa clase.

## 18. Auditoría byte a byte (LC_ALL=C): verificación COMPLETA de closes de clase  [2026-11-12]
- Probe binario 'B<b>B\n' para los 256 bytes: width 0 = {controles 0x00-0x1f menos 09,0a,0c,0d? — excepto 07(=tab) context-dependiente}, {0x7f-0xff}; width 1 = exactamente {0x20-0x7e}; TAB(0x09) avanza a siguiente múltiplo de 8 (0x08 celdas desde col valor B='0'); {0x0a\n,0x0c\f,0x0d\r} = reset/end-of-line (no suman celdas).
- Reconciliado con el modelo: 0/13.072 resueltos para hito 3 antes; ahora clase -L además cerrada por probe directo contra el binario real.
- Clases LC_ALL=C COMPLETAS (por probe binario): word-separators = {09,0a,0b,0c,0d,20,a0} (audit hito 5); -L width = {1 en 20-7e; 0 resto; TAB→mult8; {0a,0c,0d} reset} (audit hito 6); line end = {0a} (0a=línea, 0c/0d=reset, necesario para ambos).
- IMPORTANTE: audit binaria cubre clasificado POR BYTES; la integración con el lazo de lectura de wc (con el locale **ciudades runtime** de wc desde ctype) no se ha portado explícitamente (milestone NOT_EXECUTED).

## 19. Fase 2 hito 7 — wc -m (chars) en LC_ALL=C: byte-paridad verificada contra oráculo  [2026-11-12]
- Corpus seed 20261119: 4.926 casos — sellado ANTES del oráculo verificación (sha256 5dbc2dfe…).
- Verificación oráculo directa: wc -m == wc -c en 4.926/4.926 casos del seed 20261119; en corpora anteriores: 35.941/35.941.
- Conclusión: en LC_ALL=C (MB_CUR_MAX == 1), el contador de caracteres colapsa al de bytes — es verificable y lo verificamos; no se afirma en es_AR.utf8 ni multibyte.
- Milestone cierre: clase -m cerrada POR OBSERVACIÓN en el dominio LC_ALL=C ASCII.
- NOT_EXECUTED: multibyte/locale -m; port 1:1 del disasm; -m vs -c (parcial multibyte) en es_AR.utf8.

## 20. Fase 2 hito 8 — UTF-8/multibyte: 0 divergencias en ambas variantes (seed 20261120)  [2026-11-12]
- Corpus seed 20261120: 1.184 casos — same Alphabet/structure as 20261118 seed but different seed — sellado ANTES del oráculo (4aa43467…).
- Oráculos sellados (después): matrix_highutf8_C.txt (LC_ALL=C) y matrix_highutf8.txt (es_AR.utf8) — sanity: 706 de 1184 difieren entre locales.
- Reconstrucción: 1184/1184 en UTF-8 (verify_wc_utf8 sin overrides → LANG=es_AR.utf8) Y 1184/1184 en LC_ALL=C.
- DEFECTO CORREGIDO: wc_oracle.py usaba os.environ.get('LC_ALL','C') (fallback siempre LC_ALL=C); corregido explícitamente.
- MODELO UTF-8: UTF-8 decoder inline (1-4 bytes), espacios Unicode (25 codepoints incl. NBSP, U+2028/9, U+00A0, U+202F, etc.).
- UTF-8 modelizado independiente de ctype runtime; LET-8 cover es_AR.utf8 y C. -m sigue pendiente para UTF-8.

## 21. Fase 2 hito 10 — extensión del paquete público de verificación  [2026-11-12]
- Publicado f3c6f7 en https://github.com/LexLuthorPrimero/rxre-cleanroom — el repo público ahora contiene DOS hitos reproducibles: filenvercmp + wc.
- wc milestone: verificación parametrizada con modo forzado (C|utf8) para eliminar la dependencia del locale del entorno en la verificación de terceros.
- El paquete incluye: INDEX.md top-level actualizado, wc/ con 18 archivos (corpus+matrices selladas, SEAL_WC.txt self-contenued, INDEX manifesto), SHA256SUMS raíz y wc/SHA256SUMS locales.
- 35.000+ casos sellados verificados in-loc, 0 divergencias en ambas locales.
- El riesgo de locales en verificación de terceros está mitigado con el flag explícito.
