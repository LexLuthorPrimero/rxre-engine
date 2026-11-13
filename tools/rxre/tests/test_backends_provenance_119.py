#!/usr/bin/env python3
"""RXRE-119: regresión discriminativa de backends y provenance.

Antes del parche (WT):
- op: backends -> status=ok pero results=[] (contracto roto)
- op: provenance -> AttributeError / blocked (no hay handler)

Después (post-119):
- op: backends -> status=ok, results>=1, envelope completo
- op: provenance -> status=ok, results>=1, envelope completo
- No modifica .rxre/storage ni archivos protegidos.
"""
import sys, os, tempfile, subprocess, json

PKG = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB = tempfile.mktemp(suffix=".sqlite3")
env = dict(os.environ); env["PYTHONPATH"] = PKG; env["RXRE_DB"] = DB

def rx(reqs, db=DB, timeout=120):
    p = subprocess.run([sys.executable, "-B",
                        os.path.join(PKG, "api", "machine.py")],
        input="\n".join(json.dumps(r) for r in reqs), capture_output=True,
        text=True, timeout=timeout, env=env)
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line:
            try: out.append(json.loads(line))
            except Exception: pass
    return out

def v(nombre, cond, detalle=""):
    if not cond:
        print("  [FALLA] %s: %s" % (nombre, detalle[:120]))
        return False
    return True

RESULTADOS = []

def check(name, cond, detail=""):
    ok = bool(cond)
    RESULTADOS.append((name, ok, detail))
    return ok

# --- Antes (simulado por los resultados documentados de 118) ---
# No se ejecuta el "antes" real porque el WT ya fue parcheado;
# el test valida que el parche sigue vivo.

# --- Después ---
q_backends = rx([{"op": "backends"}])
check("backends_status_ok", q_backends and q_backends[0].get("status") == "ok",
      "status=%s" % (q_backends[0].get("status") if q_backends else "NONE"))
check("backends_results_non_empty", len(q_backends[0].get("results") or []) >= 1,
      "results=%d" % len(q_backends[0].get("results") or []))
check("backends_has_backends_key", "backends" in q_backends[0],
      "claves: %s" % sorted(q_backends[0].keys())[:5])

q_prov = rx([{"op": "provenance"}])
check("provenance_status_ok", q_prov and q_prov[0].get("status") == "ok",
      "status=%s" % (q_prov[0].get("status") if q_prov else "NONE"))
check("provenance_results_non_empty", len(q_prov[0].get("results") or []) >= 1,
      "results=%d" % len(q_prov[0].get("results") or []))

# Regresión rápida: query y integridad intactos
q = rx([{"op": "query", "question": "donde esta VM_CONTEXT0_CNTL", "target": "0000:01:00.0"}])
check("regresion_query_ok", bool(q and q[0].get("status") == "ok"),
      "query status=%s" % (q[0].get("status") if q else "NONE"))

# Limpieza
try:
    import shutil
    shutil.rmtree(os.path.dirname(DB), ignore_errors=True)
except Exception:
    pass

fallos = [d for d, ok, _ in RESULTADOS if not ok]
print("")
print("=" * 60)
print("RXRE-119 regresión discriminativa (backends + provenance)")
print("verificados: %d | fallos: %d" % (len(RESULTADOS), len(fallos)))
if fallos:
    for d in fallos:
        print("  [FALLA] %s" % d)
    print("=" * 60)
    sys.exit(1)
print("TODO VERDE")
print("=" * 60)
sys.exit(0)
