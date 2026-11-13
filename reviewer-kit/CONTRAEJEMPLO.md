# Plantilla — reporte de contraejemplo (`RE-VERIFICACION`)

Un contraejemplo sin minimizar no es accionable; uno minimizado decide el hito.

## Identidad

- Fecha (UTC):
- Commit del clon (`git log --oneline -1`):
- ¿Clon, o zip del release? (si zip: SHA-256 del zip):
- Reportero (nombre o seudónimo):
- Hashes entorno: `sha256sum /usr/bin/ls /usr/bin/wc`, `gcc --version`, `locale`

## Afirmación impugnada

Cita exacta del README / EXPEDIENTE / hito que consideras incorrecto.

## Pasos para reproducir (mínimos)

1. ...
2. ...
3. ...

## Esperado vs observado

| Caso de entrada | Esperado (oráculo nativo / sello) | Observado (reconstrucción / tu host) |
|---|---|---|
| `...` | `...` | `...` |

## Minimización

- Entrada más pequeña que produce la divergencia (par de nombres, byte sequence,
  línea de corpus — pega aquí el contenido):
- Tamaño: … bytes / … entradas
- ¿Es determinista? (repetir 3 veces): sí / no

## Impacto

- ¿Invalida el hito entero o una celda? (cita la tabla de hitos afectada):
- ¿Afecta a otra familia de pruebas? (wc o filenvercmp, locale, i18n):

## Qué no afirmes

- No afirmes corrupción del sello sin verificar `sha256sum` de los artefactos.
- No afirmes un bug general: limita al caso reproducido.
- No ejecutes ni pidas ejecución de nada fuera de este repositorio.

Adjuntar: salida completa de `sh evidence/r3/verify.sh` (o extracto), y —si aplica—
tu corpus mínimo en un único archivo `case.txt`.
