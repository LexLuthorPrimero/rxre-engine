# RXRE — Protocolo seal-before-reveal

El protocolo es obligatorio para toda misión que produzca evidencia. **No se trata de criptográfica autenticidad externa; trata orden causal.**

## 1) Regla básica

1. Capturar evidencia (hash/sha256 + identidad física cuando aplique).
2. Sellar los bytes (hash + timestamp + procedencia) **antes** de procesar.
3. Verificar sello.
4. Procesar contenido.
5. Registrar transformaciones posteriores como artefactos derivados, nunca como evidencia original.

## 2) Comandos mínimos

```
sha256sum <artefacto> > <artefacto>.sha256
stat <artefacto>                # dev/ino cuando corresponda
readelf -n <binario> | grep -i build
```

## 3) Destino de la evidencia

- **Evidencia original** → nunca modificar; si hay que corregirla: `supersedes_ref` (nueva fila).
- **Evidencia derivada** → junto con el sello de origen, nunca encima.
- **Persistencia** → vía `store.conectar()` (WAL), `results`/`operations` append-only.

## 4) Qué incluye un sello mínimo

- `sha256` de contenido
- `mtime`/`size`/`dev`/`ino` (cuando sea fichero)
- procedencia: `SELECCIÓN`/`INVOCACIÓN REAL`/`RESULTADO DEVUELTO`/`AUTORIZACIÓN`/`PERSISTENCIA`/`RECUPERACIÓN INDEPENDIENTE`
- restricciones (`SAME_HOST`, `SAME_UID`, `no independencia física` cuando aplique)

## 5) Antipatrones

- Procesar evidencia antes de sellar.
- Afirmar `PROVEN` a partir de un hash solo (hash ≠ autenticidad).
- Reutilizar un artefacto derivado como si fuera original.
- Subir a revisión independiente sin preservar orden causal.

## 6) Independencia física

- Hoy: un solo host (`kalm`). Toda validación es `SAME_HOST`.
- No se crean identidades para "simular" segundo host.
- E2E-039: `BLOCKED` y `NOT_VERIFIED` son estados respetables; no se reciclan a `PASS_PARTIAL`.

## 7) Recuperación independiente

Segunda conexión `store.conectar()` que lee `results` por `result_id` y confirma: estado, decisión, límite, restricciones; sin reintentar el mecanismo.

## 8) Registro

Ejemplo de entrada (no ejecutable; ilustrativo):

```
SELECCIÓN: capability_registry / op:select
INVOCACIÓN: capturar_evidencia(...)
RESULTADO: snap.decision=...
HASH: ...
RECUPERACIÓN INDEPENDIENTE: ok
LIMITACIONES: SAME_HOST / host único / no independencia física
```
