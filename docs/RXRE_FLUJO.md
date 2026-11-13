# RXRE — Flujo mínimo de uso

## 0) Lo que hace hoy y lo que no

RXRE **no** es un producto de ingeniería inversa utilizable por terceros hoy. Es un marco de misión + evidencia + método. Lo que existe y funciona: sellos, índices, índices de credibilidad, gates de fidelidad (rechaza funciones fuera de dominio). Lo que no existe: `rxre reconstruct` como comando público estable.

## 1) Requisitos hoy

- Linux; host x86_64 (validado en `kalm`)
- Python ≥3.11; herramientas de sistema: `readelf`, `objdump`, `stat`, `sha256sum`, `cmp`
- `ripgrep`, `find`, `ls`
- (GPU) Vulkan/RADV Polaris12 para misiones SPIR-V — **no requerido para leer/documento**

## 2) Primer paso — leer

```
cat RXRE_IDENTIDAD.md
cat RXRE_ESTADO.md
cat RXRE_ESENCIA.md
cat AGENTS.md | sed -n '1,60p'
```

## 3) Dependencias / entorno

```
which python3 objdump readelf stat cmp sha256sum
python3 --version
python3 -c "import ctypes; print('ctypes ok')"
```

## 4) Validación local (ligera, no destructiva)

```
wc -l RXRE_PLAN_MAESTRO.md          # 12.835 esperado
ls tests | wc -l                     # 198 archivos
sha256sum RXRE_IDENTIDAD.md         # cce22881…
sha256sum AGENTS.md                 # 25d57344…
```

## 5) Flujo de una capacidad (método)

EVIDENCE → SEMANTICS → SCHEMA → TEST → IMPLEMENTATION → VALIDATION

1. Identificar objeto real (binary/function/registro) y sellar hash+identidad.
2. Formular hipótesis y pruebas discriminantes.
3. Persistir en `operations`/`results` con `row_hash` (nunca UPDATE; solo INSERT/OR IGNORE).
4. Recuperar con conexión destino independiente; verificar igualdad.
5. Documentar limitaciones sin ocultarlas.
6. Solo entonces: dictamen acotado.

## 6) Salida esperada

- Veredicto siempre modesto: `PROVEN` solo captura de integridad; `PARTIAL` para claims acotadas; `NOT_DETERMINED` para ausencia de evidencia; `REJECTED`/`NOT_VERIFIED` cuando sea aplicable.
- Ninguna integración en producción sin autorización explícita.
