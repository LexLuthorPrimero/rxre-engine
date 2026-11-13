# QUICKSTART — `rxre-engine` en 15 minutos

Material para un revisor externo que llega frío al repositorio. Si algo aquí se
contradice con el código, el código gana (y por favor, abre un issue con el
síntoma).

## Qué es esto (y qué no)

Es un motor experimental de ingeniería inversa asistido por IA. Lo único que el
repositorio **puede demostrar hoy** son dos reconstrucciones acotadas con evidencia
diferencial sellada:

- `filenvercmp` sobre `/usr/bin/ls` (GNU coreutils), `filenvercmp` = función de
  comparación de `ls -v`. **34.145 × 2** casos (dos generaciones) + challenge
  corpus (hito 13/13b, 3.100 + 141 = 3.241) + invariancia de locale + i18n
  black-box. **0 divergencias** vs el oráculo nativo sellado.
- `wc` (`-c`, `-l`, `-w`, `-m`, `-L`, `--files0-from`) sobre GNU coreutils, 11
  corpora, `LC_ALL=C` y `es_AR.utf8`. **0 divergencias**.

No es un producto, no es un desensamblador general, no autoriza acceso a hardware
(sin `/dev/mem`, `sysfs`, `debugfs`, UMR, root, `sudo`), y no afirma verificación
por terceros (`NOT_EXECUTED`; PUERTA condición 3 en `PENDING_EXTERNAL_REVIEWER`).

## Verificación en un comando

```sh
sh evidence/r3/verify.sh
```

Esperado al final: `VERIFY: all steps passed` (66 passed, 2 skipped en clon
público — los 2 skips son tests que requieren la DB privada del autor, no
distribuida; ver `test_replay_mision.py`). Requisitos: Linux x86_64, `gcc`,
`python3` (≥3.10), `pytest`, GNU coreutils cuyos binarios coincidan con los
SHA-256 sellados en `evidence/r3/verify.sh` (falla cerrada si no). Si tu `ls` o
tu `wc` difieren, la verificación del *oráculo* no es válida — no es un error del
script, es el gate funcionando.

## Mapa de lectura (en orden)

1. `README.md` — posición honesta y matriz de hitos.
2. `evidence/r3/EXPEDIENTE_R3.md` — cadena completa de sellado, evidencia y
   cierre; **leer §11 en adelante y los updates 6–8** (las secciones §4–§5 son
   históricas y están marcadas `SUPERSEDED`).
3. `docs/RXRE_LIMITACIONES.md` — qué no está demostrado.
4. `docs/RXRE_PROCEDENCIA.md` — de dónde sale cada número.
5. `GLOSSARY.md` — siglas (ACRE, EDICT, AASE, TIERRA, ÉTER…).
6. `docs/RXRE_CHANGELOG.md` — quién autorizó qué (y qué **no** está autorizado).

## Los seis estados epistémicos (imprescindible)

`PROVEN` (cadena completa EVIDENCE → VALIDATION) · `PARTIAL` (con limitaciones,
nunca oculto) · `BLOCKED` (precondición o autorización ausente) · `INSUFFICIENT` ·
`NOT_DETERMINED` (ausencia de evidencia ≠ falsedad) · `DEFERRED`. Una afirmación
`PASS`/`VALID` solo significa lo que la evidencia anexa demuestra — nunca una
capacidad general.

## Lo que **no** está en el repositorio (y por qué)

- La DB de operaciones (`rxre.sqlite3`), los artefactos del host privado del
  autor y capturas de hardware (sin ellos no puedes ejecutar los 2 replay tests).
- El código C11 del bus ÉTER-WAL (M1266): aparece como **historial sellado** en
  `docs/RXRE_CHANGELOG.md` y `evidence/r3/records/plan_sections.txt`
  (A1-DIGEST PASS scratch; A2 PARTIAL; power-loss `NOT_VERIFIED`; **Gate 2 /
  EXP-01…15: NO AUTORIZADOS**). No está publicado; no hay binario que auditar aquí.
- Ninguna herramienta de ejecución remota ni credencial. Nada se ejecuta sin tu
  invocación explícita.

## Si quieres probar que esto no es teatro

Corre el verificador en un clon **limpio** y en una máquina distinta (hoy
sigue siendo el mismo host/UID — eso es exactamente lo que falta para cerrar la
puerta). O genera un corpus adversarial nuevo contra `filenvercmp` (mira
`evidence/r3/challenge_cr_20261126/gen_challenge_cr.py`) y manda el resultado vía
issue. Un contraejemplo real vale más que diez auditorías amables.

## Límites duros (no negociables)

Sin `MMIO`, `/dev/mem`, `sysfs`, `debugfs`, UMR, root, `sudo`, `--auto`,
`op:claim`. Sin publicación automática. Sin afirmar capacidad general a partir
de dominios acotados. La independencia física sigue siendo `E2E-039 BLOCKED` y
ningún test interno la sustituye.
