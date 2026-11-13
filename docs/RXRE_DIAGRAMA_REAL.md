# RXRE — DIAGRAMA REAL (basado en código, no en especificación)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ALMA                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Criterios de cierre evaluables (funciones, no booleanos)            │  │
│  │  • EVIDENCIA_CADA_CASILLA   • SIN_HECHOS_SIN_ARTEFACTO              │  │
│  │  • IDEMPOTENCIA             • REPRODUCTIBILIDAD                      │  │
│  │  • LAS_7_V3                 • FALSIFICACION_ASOCIADA                 │  │
│  │  • NO_INVENTAR                                                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  orienta (define/orienta)                                                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ETER (hub async · NO media sync)                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  3 MODOS FALLO   │  │  WRITE-AHEAD     │  │  ESTADISTICAS (contadas) │  │
│  │  • CAIDA_PROCESO │  │  1. id_unico     │  │  • aceptados             │  │
│  │  • SATURACION    │  │  2. idempotencia │  │  • despachados           │  │
│  │  • REINICIO      │  │  3. fsync        │  │  • descartados_saturacion│  │
│  │                  │  │  4. confirmacion │  │  • duplicados_idem       │  │
│  │  cola acotada    │  │  5. idempotencia │  │  • fsync_realizados      │  │
│  │  descarte contado│  │                  │  │  • persistidos           │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
│  §22 #1 PROPUESTA: clasificación eventos críticos                          │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ despacha eventos (async, no bloquea productor)
                                 ▼
                    ┌────────────────────────┐
                    │    CONSUMIDORES        │  (genéricos: MENTE, FUEGO, TIERRA, etc.)
                    └────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
                    CAPAS TRANSVERSALES (observan/registran todo)
════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                           AIRE                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  class Traza                                                         │  │
│  │  • obs(evento) — registra traza completa                             │  │
│  │  • span(contexto) — context manager para spans anidados             │  │
│  │  • get() — devuelve lista completa de eventos                        │  │
│  │  Reconstruida (faltaba; AttributeError corregido)                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  Capa transversal · observa la traza completa                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           TIERRA  (grafo de evidencia)                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  SCHEMA CLAIM: id · statement · object_hash · scope · epistemic_state │  │
│  │              evidence_refs · derivation_refs · contradiction_refs     │  │
│  │              falsification_test · unresolved_obligations · version    │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  EVIDENCE: append-only · DELETE/UPDATE prohibido por TRIGGER         │  │
│  │  3 CAPAS HASH: integridad | autenticidad | validez_semantica (separadas)│  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  6 ESTADOS: PROVEN | PARTIAL | NOT_DETERMINED | PROVEN_ABSENT       │  │
│  │             | DEFERRED | INVALIDATED (NO automático)                │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  CONCURRENCIA POR OPERACIÓN (no global):                            │  │
│  │  • actualizar_estado → optimistic (version + row_count)             │  │
│  │  • aportar evidencia  → append, sin lock sobre claim                │  │
│  │  • reevaluar          → pessimistic (locked_by + expires, por claim)│  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  CONTRADICCIÓN = registro (no estado) → reevaluación documentada    │  │
│  │  REEVALUACIÓN → INVALIDATED | REVERTED | PARTIAL                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  §22 #2 PROPUESTA: severidad contradicción                                 │
└─────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
                    TRES PLANOS DE ACCIÓN SÍNCRONOS (en planos.py)
════════════════════════════════════════════════════════════════════════════════

    ┌─────────────────┐      SYNC DIRECTO       ┌─────────────────┐
    │     MENTE       │ ◄─────────────────────► │     CUERPO      │
    │  (Hipotesis/    │     hash verificado     │  (medir /       │
    │   Libro)        │     EN PUNTO DE USO     │   verificar_    │
    │                 │                         │   en_uso)       │
    │ • preguntar()   │                         │                 │
    │ • observar()    │                         │                 │
    │ • decidir()     │                         │                 │
    │ • sin_resolver()│                         │                 │
    │ [v3] falsificacion│                       │                 │
    │   explicita     │                         │                 │
    └────────┬────────┘                         └────────┬────────┘
             │                                            │
             │          SYNC DIRECTO                      │
             │◄──────────────────────────────────────────►│
             │                                            ▼
             │                                 ┌─────────────────┐
             │                                 │     FUEGO       │
             │                                 │  (transformar/  │
             │                                 │   rollback)     │
             │                                 │                 │
             │                                 │ • aplicar()     │
             │                                 │ • rollback()    │
             │                                 │ • alcance_      │
             │                                 │   rollback()    │
             │                                 │                 │
             │                                 │ [v3] R12:       │
             │                                 │ rollback POR    │
             │                                 │ DISPOSITIVO     │
             │                                 │ (global proh.)  │
             │                                 └─────────────────┘
             │
             │  §22 #6 PROPUESTA: protocolo sync MENTE/CUERPO/FUEGO (KPN)
             │
             ▼

════════════════════════════════════════════════════════════════════════════════
                    COMPONENTES INDEPENDIENTES
════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGUA                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Aprendizaje: proposito · procedencia (OBLIGATORIA) · regla          │  │
│  │              reverificar() · confianza                                │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  [v3] revalidar al recuperar (no confiar en lo persistido)           │  │
│  │  • revalidar() → ejecuta reverificar() AHORA, no devuelve cache      │  │
│  │  • recuperar() == revalidar()                                        │  │
│  │  • reinicio → vivo se pierde, disco sobrevive, vuelve NOT_DETERMINED │  │
│  │  Estados: PROVEN | PROVEN_ABSENT | NOT_DETERMINED (no "falso")       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  §22 #5 PROPUESTA: frontera AGUA / TIERRA                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           ROUTER                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Busca CAPACIDADES, no nombres de herramientas                        │  │
│  │  • binary.functions        → (Rizin, Ghidra, Capstone)               │  │
│  │  • source.semantic_search  → (Coccinelle, Tree-sitter)               │  │
│  │  • runtime.trace           → (GDB, LLDB, Frida, perf)                │  │
│  │  • formal.check            → (Z3, CBMC)                              │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  Productor: nombre · capacidades[] · disponible · ejecutar() · honesto│  │
│  │  resolver(capacidad) → {elegido, estado, candidatos}                 │  │
│  │  invocar() → propaga estado: [] + honesto = PROVEN_ABSENT            │  │
│  │                          error/ausente = NOT_DETERMINED              │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  §22 #4 PROPUESTA: selección backend por scoring compuesto                │
└─────────────────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════════════════
                                    PUERTA
════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────┐
│                           PUERTA                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  AUDIT A-F → STATE=DELIVERED → REVISIÓN INDEPENDIENTE                │  │
│  │                           │                                          │  │
│  │                   ┌─────────┴─────────┐                              │  │
│  │                   ▼                   ▼                              │  │
│  │              CONTESTED             ACCEPTED                          │  │
│  │                   │                    │                              │  │
│  │            vuelve a CHALLENGED    ETAPA 1                            │  │
│  │                                      (bloqueada aquí)                │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  4 CONDICIONES EVALUADAS (no string manual):                        │  │
│  │  1. artefactos_integros          (hash SHA-256 verificado)           │  │
│  │  2. cero_refutaciones_criticas   (pendientes = 0)                    │  │
│  │  3. revisor_sin_participacion    (revisor ∉ participaciones)         │  │
│  │  4. autoridad_aceptacion_nombrada (autoridad ≠ None)                 │  │
│  ├──────────────────────────────────────────────────────────────────────┤  │
│  │  ESTADO ACTUAL: CONTESTED                                           │  │
│  │  • cond 1-2: CUMPLEN (artefactos OK, 0 refutaciones)                │  │
│  │  • cond 3: PENDIENTE (revisor formal no registrado en audit.db)     │  │
│  │  • cond 4: DECLARADA (lucas, ingeniero científico, 2026-10-19)      │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  §22 #3 PROPUESTA: designación autoridad                                   │
│  §22 #7 PROPUESTA: métricas A/B                                           │
└─────────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════
                              RESUMEN ESTADOS REALES
════════════════════════════════════════════════════════════════════════════════

COMPONENTE        │ ESTADO       │ EVIDENCIA
──────────────────┼──────────────┼────────────────────────────────────────────
ALMA              │ PROVEN       │ 7 criterios evaluables; test: evaluar_cierre()
ETER              │ PROVEN       │ 3 modos fallo; write-ahead; 55 PASS tests
AIRE              │ PROVEN       │ class Traza reconstruida; tests PASS
TIERRA            │ PROVEN       │ 6 estados; 3 capas hash; concurrencia; 35 PASS
MENTE (planos.py) │ PROVEN       │ Libro/Hipotesis; falsificación explícita
CUERPO (planos.py)│ PROVEN       │ medir/verificar_en_uso; hash punto de uso
FUEGO (planos.py) │ PROVEN       │ rollback por dispositivo; R12 prohibe global
AGUA              │ PARTIAL      │ revalidar implementado; frontera TIERRA §22#5
ROUTER            │ PARTIAL      │ resolver/invocar OK; scoring §22#4 pendiente
PUERTA            │ CONTESTED    │ 4/4 cond. evaluadas; cond.3 pendiente (tercero)
──────────────────┼──────────────┼────────────────────────────────────────────
7 CORRECCIONES V3 │ VERIFICADAS  │ 55 PASS v3 + 35 PASS contratos + 7/7 mutación

PRUEBAS:
  test_arquitectura_v3_02_v3.py        → 55 PASS, 0 FAIL
  test_arquitectura_v3_01_contracts.py → 35 PASS, 0 FAIL  
  test_arquitectura_v3_03_mutacion.py  → 7/7 DISCRIMINA (90 PASS control)

BASES DE DATOS:
  • rxre.sqlite3        → claims/evidence/falsifications/contradictions (vacías, tablas creadas)
  • .rxre/audit.db      → claims históricas + EV-VERIFICACION-V3-001 + EV-AUTORIDAD-LUCAS-001
  • ETER journal        → SQLite WAL + fsync
  • AGUA aprendizajes   → SQLite propio

ARCHIVOS CLAVE (no modificados por subagentes):
  • tools/rxre/arquitectura/ (9 archivos + __init__ + planos + schemas + mundo_real)
  • core/store.py         → CHECK 6 estados (INVALIDATED línea 372)
  • docs/PUERTA_CORR7.md  → gate con declaración autoridad
  • AUDIT_FINAL.md        → 219 líneas, apéndices subagentes
  • TRABAJO_EJECUTADO.md  → log detallado
  • CONSOLIDADO_EJECUTADO.md → resumen
  • CONSOLIDADA V3.MD     → especificación de referencia (intacta)
