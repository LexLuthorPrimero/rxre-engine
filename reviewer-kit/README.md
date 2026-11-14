# Reviewer kit — `rxre-engine`

Material para un revisor **externo e independiente** que quiera ejecutar por sí
mismo la cadena de verificación publicada. Ninguna de estas páginas sustituye tu
dictamen; solo te dan los pasos y los límites.

| Archivo | Para qué |
|---|---|
| `REVIEWER_GUIDE.md` | Verificación paso a paso desde clon fresco (≈15 min) y registro de entorno |
| `CONTRAEJEMPLO.md` | Plantilla de reporte de contraejemplo (issue) con minimización y hashes |

## Reglas de juego

1. **Verás lo que verás**: si tu ` /usr/bin/ls` o `/usr/bin/wc` no coinciden con
   los SHA-256 sellados, la puerta de identidad falla *a propósito* (fail-closed).
   No es un error del script; es la garantía de que el diferencial se hace contra
   el oráculo real.
2. **Los fallos de integridad cuentan como hallazgo válido.** Si un sello no
   coincide, repórtalo: significa corrupción del paquete, no "malinterpretación".
3. **Nada se promete fuera de los dominios sellados.** filenvercmp, wc, fold, tr, dirname y basename — solo. Una afirmación sobre otro binario requiere otra cadena, no este repo.
4. Este kit **no autoriza** acceso a hardware, red o binarios fuera de lo
   documentado, ni constituye certificación pública: la puerta (`PUERTA`,
   condición 3) se abre con tu dictamen escrito, no con documentación.

## Cómo reportar

- Asunto del issue: `RE-VERIFICACION: <entorno> — <PASS|FAIL|libro>`.
- Adjunta: entorno (uname, gcc, coreutils, locale), commit exacto, salida de
  `sh evidence/r3/verify.sh`, y — si algo diverge — el contraejemplo minimizado
  según `CONTRAEJEMPLO.md`.
- El issue #1 de `rxre-cleanroom` y este repositorio reciben los reportes
  técnicos; el estado de la puerta visible solo en `docs/RXRE_CHANGELOG.md`.

MIT (código) · CC0 (textos del kit) · sin garantía
