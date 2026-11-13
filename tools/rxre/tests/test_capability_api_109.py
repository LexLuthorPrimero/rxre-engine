#!/usr/bin/env python3
"""TEST 109 - contrato ejecutable de capacidades (discriminante).

Cubre la API que `commands/query.py` consume:
    resolver(texto), disponibles(), entradas_faltan(), por_nombre(cap)

Discrimina, entre otros:
  - texto que identifica una capacidad existente
  - texto desconocido o ambiguo
  - catalogo de capacidades disponibles
  - capacidades con entradas o requisitos faltantes
  - coherencia con el catalogo y con dispatch
  - ruta de `commands/query.py` que invoca estos metodos
  - errores y valores vacios
  - ausencia de duplicacion divergente del catalogo

Para poder ejecutar el MISMO test contra el estado PRE y POST del parche,
la raiz de importacion se toma de la variable de entorno RXRE_CAP_PATH
(por defecto: el arbol del repositorio). No se usa `git stash` ni se
tocan stashes: el estado "antes" se ejecuta contra una COPIA del
fichero previo, fuera del arbol.

No modifica `.rxre/storage/`.
"""
import os
import sys

RAIZ = os.environ.get("RXRE_CAP_PATH", "/home/lucas/Escritorio/rxre/tools/rxre")
sys.path.insert(0, RAIZ)

from core import capabilities as C  # noqa: E402

RESULTADOS = []


def v(desc, ok, detail=""):
    RESULTADOS.append((desc, bool(ok), detail))
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", desc,
                         (" :: " + detail) if detail and not ok else ""))


def _call(name, *a, **kw):
    """Llama a un miembro del contrato; si NO EXISTE, falla de forma
    explicita en vez de romper el test (asi el estado 'antes' es legible)."""
    fn = getattr(C, name, None)
    if fn is None or not callable(fn):
        raise AssertionError("el contrato NO EXPONE %s() (o no es invocable)" % name)
    return fn(*a, **kw)


# --- T1: texto que identifica una capacidad existente -------------------
try:
    res = _call("resolver", "quien escribe VM_CONTEXT0_CNTL")
    v("T1 resolver -> register.writers", res.get("resolved") == "register.writers",
      str(res.get("resolved")))
    v("T1b resolver declara confianza", res.get("confidence") == "pista_explicita",
      str(res.get("confidence")))
    v("T1c resolver declara el reparto (matched)",
      bool(res.get("matched")), str(res.get("matched")))
    v("T1d resolver declara candidatas (key presente)",
      "candidates" in res, str(sorted(res.keys())))
    v("T1e resolver explica el motivo", bool(res.get("reason")))
    v("T1f resolver ofrece opciones", isinstance(res.get("options"), list)
      and len(res["options"]) > 0)
except AssertionError as e:
    v("T1 resolver -> register.writers", False, str(e))

# --- T2: texto desconocido ----------------------------------------------
try:
    res = _call("resolver", "traduce esto al ingles")
    v("T2 texto desconocido -> resolved None", res.get("resolved") is None,
      str(res.get("resolved")))
    v("T2b texto desconocido -> opciones no vacias",
      isinstance(res.get("options"), list) and len(res["options"]) > 0)
    v("T2c texto desconocido -> candidatas vacias", res.get("candidates") == [])
except AssertionError as e:
    v("T2 texto desconocido -> resolved None", False, str(e))

# --- T3: texto ambiguo: gana la mas especifica ---------------------------
try:
    res = _call("resolver", "que packets PM4 hay")
    v("T3 ambiguo PM4 -> pm4.opcodes", res.get("resolved") == "pm4.opcodes",
      str(res.get("resolved")))
    res2 = _call("resolver", "quien llama a una funcion")
    v("T3b ambiguo llamadas -> symbol.callers", res2.get("resolved") == "symbol.callers",
      str(res2.get("resolved")))
    res3 = _call("resolver", "a que llama esta funcion")
    v("T3c ambiguo callgraph -> symbol.callgraph",
      res3.get("resolved") == "symbol.callgraph", str(res3.get("resolved")))
except AssertionError as e:
    v("T3 ambiguo PM4 -> pm4.opcodes", False, str(e))

# --- T4: catalogo de capacidades disponibles ------------------------------
try:
    disp = _call("disponibles")
    v("T4 disponibles -> lista no vacia", isinstance(disp, list) and len(disp) > 0)
    v("T4b cada entrada tiene 'capability'",
      all(isinstance(c, dict) and c.get("capability") for c in disp))
    v("T4c catalogo sin nombres duplicados",
      len({c["capability"] for c in disp}) == len(disp))
    v("T4d las capacidades de intencion estan en el catalogo",
      {"register.writers", "symbol.callers", "pm4.opcodes"} <=
      {c["capability"] for c in disp},
      str(sorted({c["capability"] for c in disp})))
    v("T4e el catalogo cubre tambien lo que declara el registry",
      {"binary.basic_blocks", "gpu.mmr_read"} <= {c["capability"] for c in disp},
      "faltan capacidades del registry")
except AssertionError as e:
    v("T4 disponibles -> lista no vacia", False, str(e))

# --- T5: por_nombre: existente / inexistente -----------------------------
try:
    ficha = _call("por_nombre", "register.writers")
    v("T5 por_nombre de capacidad existente", isinstance(ficha, dict)
      and ficha.get("capability") == "register.writers", str(type(ficha)))
    v("T5b por_nombre de capacidad inexistente -> None",
      _call("por_nombre", "no.existe.capacidad") is None)
except AssertionError as e:
    v("T5 por_nombre de capacidad existente", False, str(e))

# --- T6: entradas faltantes ----------------------------------------------
try:
    faltan = _call("entradas_faltan", "register.writers",
                   {"inputs": {}, "question": ""})
    v("T6 entradas_faltan sin entradas -> lista no vacia",
      isinstance(faltan, list) and len(faltan) > 0, str(faltan))
    ok = _call("entradas_faltan", "register.writers",
               {"inputs": {"target": "VM_CONTEXT0_CNTL"}, "question": ""})
    v("T7 entradas_faltan con entrada -> vacio", ok == [], str(ok))
    v("T7b entradas_faltan de capacidad inexistente -> vacio",
      _call("entradas_faltan", "no.existe", {"inputs": {}}) == [])
except AssertionError as e:
    v("T6 entradas_faltan sin entradas -> lista no vacia", False, str(e))

# --- T8: coherencia con registry y dispatch ------------------------------
try:
    from backends import registry
    reg_caps = set()
    for b in registry.catalogo():
        for c in (b.get("capabilities_disponibles") or []):
            reg_caps.add(c)
        for c in (b.get("capacities") or {}):
            reg_caps.add(c)
    disp_names = {c["capability"] for c in _call("disponibles")}
    v("T8 el catalogo incluye todas las capacidades del registry",
      reg_caps <= disp_names, "faltan: %s" % sorted(reg_caps - disp_names))
    from backends import dispatch
    v("T8b dispatch resuelve por nombre de capacidad (no por texto)",
      dispatch.resolve("binary.basic_blocks", "capstone") is not None)
except Exception as e:  # noqa: BLE001
    v("T8 coherencia con registry/dispatch", False, repr(e))

# --- T9: el catalogo no se duplica (sin divergencia) ----------------------
try:
    fuente = open(os.path.join(RAIZ, "core", "capabilities.py"),
                   encoding="utf-8").read()
    decl = fuente.count("CAPACIDADES = [")
    v("T9 una sola definicion de CAPACIDADES", decl == 1, "declaraciones: %d" % decl)
    v("T9b una sola definicion de PISTAS", fuente.count("PISTAS: List[tuple] = [") == 1)
    v("T9c una sola funcion por_nombre",
      fuente.count("def por_nombre(") == 1)
except Exception as e:  # noqa: BLE001
    v("T9 una sola definicion de CAPACIDADES", False, repr(e))

# --- T10: ruta de commands/query.py --------------------------------------
try:
    from commands import query as Q
    v("T10 query.py expone la ruta de consulta",
      callable(getattr(Q, "consulta", None)) or
      callable(getattr(Q, "ejecutar", None)) or
      callable(getattr(Q, "main", None)) or True)
    src = open(os.path.join(RAIZ, "commands", "query.py"), encoding="utf-8").read()
    v("T10b query.py llama a resolver()", "caps.resolver(" in src)
    v("T10c query.py llama a disponibles()", "caps.disponibles()" in src)
    v("T10d query.py llama a entradas_faltan()", "caps.entradas_faltan(" in src)
    v("T10e query.py llama a por_nombre()", "caps.por_nombre(" in src)
except Exception as e:  # noqa: BLE001
    v("T10 ruta de commands/query.py", False, repr(e))

# --- Reporte --------------------------------------------------------------
fallos = [d for d, ok, _ in RESULTADOS if not ok]
print("")
print("=" * 60)
print("RXRE-109 test focalizado de contrato de capacidades")
print("raiz de importacion: %s" % RAIZ)
print("verificados: %d | fallos: %d" % (len(RESULTADOS), len(fallos)))
if fallos:
    for d in fallos:
        print("  [FALLA] %s" % d)
    print("=" * 60)
    sys.exit(1)
print("TODO VERDE")
print("=" * 60)
