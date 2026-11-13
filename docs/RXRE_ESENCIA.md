# RXRE — Esencia

**Qué es RXRE** (identidad oficial, 2026-11-12): un proyecto de investigación y autoría de método para la ingeniería inversa asistida por IA. Su contribución primaria es un método reproducible por terceros, con rigor epistémico y rechazo explícito de resultados no demostrados. Su motor es una línea de desarrollo experimental cuya eficacia se mide por reconstrucciones semánticas de binarios reales, con cero divergencias y verificación autónoma por terceros, sin intervención del autor original.

Ver `RXRE_IDENTIDAD.md` para la declaración íntegra y firmada (sha256 `cce22881…`).

## Qué leer primero

1. `RXRE_IDENTIDAD.md` — identidad oficial (2026-11-12)
2. `RXRE_ESTADO.md` — estado real y verificado hoy
3. `AGENTS.md` — reglas de gobernanza del agente (intactas)
4. `README.md` — estado de publicación y evidencia
5. `RXRE_PLAN_MAESTRO.md` — historial completo; append-only, ~12.835 líneas

## Qué NO es

- No es un motor de reconstrucción semántica probado end-to-end en producción.
- No tiene capacidades comerciales declaradas.
- No autoriza acceso a hardware sin privilegios (ver `AGENTS.md` §5).
- No reemplaza ni modifica los controles ejecutables (`core/store.py`, contratos protegidos, DB).

## Recordatorios obligatorios

- `PROVEN` nunca automático. `PARTIAL` ≠ `PROVEN`. `REJECTED` es output de primera clase.
- Verificar independencia física: hoy solo un host (`kalm`); E2E-039 — independencia de segundo host **BLOCKED**.
- `/tmp` es efímero; los sellos y artefactos críticos deben promoverse a `store/` (pendiente).
- `op:claim`, `--auto`, `sudo`: **no usados**. `autonomous_loop=False`; `max_iter` acotado.
- Evidencia subyacente de `filevercmp` (R3): **OPEN — NOT_PASS** (791 / 34.145 divergencias).

## Terminología mínima

| Término | Significado |
|---|---|
| `PROVEN` | Evidencia completa, sellada, verificable, sin limitaciones ocultas |
| `PARTIAL` | Evidencia parcial con limitaciones documentadas explícitamente |
| `NOT_DETERMINED` | Sin evidencia suficiente; no se declara éxito ni fracaso por ausencia |
| `BLOCKED` | Precondición ausente / autorización denegada / entorno no disponible |
| `PASS` | Sólo para captura de integridad (hash + identidad física) o claim evaluada con `evidence_refs` verificables |

## Estado actual

Ver `RXRE_ESTADO.md` para el detalle completo y verificado. En una línea: **método consolidado en UX mínima, motor embrionario; ninguna capacidad integrada en producción; GPU validado solo vía Vulkan/SPIR-V; `filevercmp` reproduce parcial (OPEN); independencia física bloqueada (1 host).**
