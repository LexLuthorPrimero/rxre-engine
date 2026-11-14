# QUICKSTART — `rxre-engine` en 15 minutos

Material para un revisor externo que llega frío al repositorio. Si algo aquí se
contradice con el código, el código gana (y por favor, abre un issue con el
síntoma).

## Qué es esto (y qué no)

Es un motor experimental de ingeniería inversa asistido por IA. Lo único que el
repositorio **puede demostrar hoy** son seis reconstrucciones acotadas con evidencia
diferencial sellada (todas contra los binarios nativos de GNU coreutils 9.10):

- `filenvercmp` sobre `/usr/bin/ls` (`sort=version`). **34.145 × 2** generaciones +
  challenge corpus (hito 13/13b, 3.100 + 141 = 3.241) + invariancia de locale +
  i18n black-box (200 nombres vs `ls -v` nativo). **0 divergencias**.
- `wc` (`-c`, `-l`, `-w`, `-m`, `-L`, `--files0-from` + flags×multibyte), 11 corpora,
  `LC_ALL=C` y `es_AR.utf8`. **0 divergencias**.
- `fold` (`-w` cell width) — 6 regeneraciones selladas (incl. w=1,2,3,4,8).
  **0 divergencias** vs `/usr/bin/fold`.
- `tr -s x` (squeeze de runs de `0x78`) — 2.513 × 2 generaciones. **0 divergencias** vs
  `/usr/bin/tr`.
- `dirname` (padre de directorio acotado) — 1.917 / 1.901 generaciones. **0 divergencias**
  vs `/usr/bin/dirname`.
- `basename` (último componente acotado) — 1.987 / 2.013 generaciones. **0 divergencias**
  vs `/usr/bin/basename`.

No es un producto, no es un descompilador general, no autoriza acceso a hardware
(sin `/dev/mem`, sysfs, debugfs, UMR, root, sudo) y no afirma verificación por
terceros (`NOT_EXECUTED`; PUERTA condición 3 en `PENDING_EXTERNAL_REVIEWER`).

## Verificación en un comando

```sh
sh evidence/r3/verify.sh
```

Esperado al final: `VERIFY: all steps passed` (94 passed, 2 skipped en clon
público; los 2 skips son tests que requieren la DB privada del autor, no
distribuida; ver `test_replay_mision.py`). Requisitos: Linux x86_64, `gcc`,
`sha256sum`, `python3` (≥3.10), `pytest`. `verify.sh` ejecuta 16 etapas; cada
binario nativo se verifica por identidad SHA-256 fail-closed antes de cualquier
usado (`ls`, `wc`, `fold`, `tr`, `dirname`, `basename`).

## Mapa de lectura (en orden)

1. `README.md` — posición honesta y matriz de hitos.
2. `evidence/r3/EXPEDIENTE_R3.md` — cadena completa de sellado, evidencia y
   cierre (en orden cronológico; las secciones §4–§5 están marcadas `SUPERSEDED`).
3. `docs/RXRE_LIMITACIONES.md` — qué no está demostrado.
4. `docs/RXRE_CHANGELOG.md` — quién autorizó qué (y qué `no` lo está).
5. `GLOSSARY.md` — siglas (ACRE, EDICT, AASE, TIERRA, ÉTER…).
6. `docs/RXRE_ESENCIA.md` — esencia del motor.

## Los seis estados epistémicos (imprescindible)

`PROVEN` (cadena completa) · `PARTIAL` (con limitaciones, nunca oculto) ·
`BLOCKED` (precondición o autorización ausente) · `INSUFFICIENT` · `NOT_DETERMINED`
(ausencia de evidencia ≠ falsedad) · `DEFERRED`. Una afirmación `PASS`/`VALID` solo
significa lo que la evidencia anexa demuestra — nunca una capacidad general.

## Lo que **no** está en el repositorio (y por qué)

- La DB de operaciones (`rxre.sqlite3`), los artefactos privados del autor y las
  capturas de hardware (por eso `test_replay_mision.py` tiene 2 skips en clones).
- El código C11 del bus ÉTER-WAL (M1266): aparece como historial sellado en
  `evidence/r3/records/plan_sections.txt` y `docs/RXRE_CHANGELOG.md`; no está
  publicado ni compilable aquí; `Gate 2 / EXP-01…15: NO AUTORIZADOS` por
  especificación interna.
- Ninguna herramienta de ejecución remota ni credencial. Nada se ejecuta sin tu
  invocación explícita.

## Si quieres probar que esto no es teatro

Corre el verificador en un clon **limpio** y en una máquina distinta (toda la
evidencia sigue siendo del mismo host/UID; eso es exactamente lo que falta para
cerrar la puerta). O genera un corpus adversarial contra `fold`/`tr`/`dirname`
(o `wc`, `dirname`, `basename`) y refuta el resultado vía issue. Un contraejemplo verdadero vale más
que diez auditorías amables.

## Límites duros (no negociables)

Sin `MMIO`, `/dev/mem`, `sysfs`, `debugfs`, UMR, root, `sudo`, `--auto`,
`op:claim`. Sin publicación automática. Sin afirmar capacidad general a partir
de dominios acotados. La independencia física sigue siendo `E2E-039 BLOCKED` y
ningún test interno la sustituye.
