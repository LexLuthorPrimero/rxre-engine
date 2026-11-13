#!/usr/bin/env python3
"""RXRE-MISSION-226 — Lógica de verdad vs completitud probatoria.

Corrige la tabla de verdad de composicion: REFUTED domina INSUFFICIENT
cuando la comparabilidad esta demostrada (misma evidencia verificada + alcance).
No modifica zonas protegidas ni DB operativa.
"""
import sys, sqlite3, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_verification_composition import componer_verificaciones

FALLOS=[]
def ok(c,l,d=""): 
    if c: print("  [PASS] %s %s"%(l,d))
    else: FALLOS.append(l); print("  [FAIL] %s %s"%(l,d))

# Datos sintéticos que simulan los 9 casos de la tabla de verdad
# Usar resultados mínimos con hash y referencia verificable para comparabilidad
HASH = "9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2"

S = {"resultado":"SUPPORTED","integridad_evidencia":{"hash_sha256":HASH},"procedencia":["res_real_001"],"motivo":"ok"}
R = {"resultado":"REFUTED","integridad_evidencia":{"hash_sha256":HASH},"procedencia":["res_real_001"],"motivo":"no coincide"}
I = {"resultado":"INSUFFICIENT","integridad_evidencia":{"hash_sha256":None},"referencias_faltantes":["res_inexistente_226"],"motivo":"evidencia insuficiente"}

print("=== 226: tabla de verdad con REFUTED > INSUFFICIENT ===")

# 9 combinaciones
casos = [
    ("S/S", [S,S], "SUPPORTED"),
    ("S/R", [S,R], "REFUTED"),
    ("S/I", [S,I], "INSUFFICIENT"),
    ("R/S", [R,S], "REFUTED"),
    ("R/R", [R,R], "REFUTED"),
    ("R/I", [R,I], "REFUTED"),   # clave 226: refutacion valida no oculta insuficiencia
    ("I/S", [I,S], "INSUFFICIENT"),
    ("I/R", [I,R], "REFUTED"),   # clave 226
    ("I/I", [I,I], "INSUFFICIENT"),
]
for label, evs, esperado in casos:
    r = componer_verificaciones(evs, ["runtime","runtime"])
    ok(r["estado_compuesto"] == esperado, label, "%s (%s)" % (r["estado_compuesto"], r.get("comparabilidad")))

# Orden invertido de cada par asimétrico (confirmar determinismo lógico)
inversos = [([S,R],"REFUTED"),([R,S],"REFUTED"),([S,I],"INSUFFICIENT"),([I,S],"INSUFFICIENT"),([R,I],"REFUTED"),([I,R],"REFUTED")]
for evs, esperado in inversos:
    r = componer_verificaciones(evs, ["runtime","runtime"])
    # Determinismo de agregación (orden independiente para conjuncion conmutativa)
    ok(r["estado_compuesto"] == esperado, "invertido %s" % ("/".join(e["resultado"][0] for e in evs)), r["estado_compuesto"])

# Etiqueta REFUSED rechazada
ok(componer_verificaciones([{"resultado":"REFUSED","integridad_evidencia":{"hash_sha256":HASH},"motivo":"x"}], ["runtime"])["estado_compuesto"] == "INDETERMINATE", "REFUSED rechazada -> INDETERMINATE")

# Incompatibilidad de artefacto (hash distinto) con REFUTED presente
other = {"resultado":"REFUTED","integridad_evidencia":{"hash_sha256":"deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"},"procedencia":["res_real_001"],"motivo":"otro"}
ok(componer_verificaciones([R, other], ["runtime","runtime"])["estado_compuesto"] == "INDETERMINATE", "hash distinto con REFUTED -> INDETERMINATE")

# Incompatibilidad de alcance con REFUTED presente
ok(componer_verificaciones([R, R], ["runtime","boot"])["estado_compuesto"] == "INDETERMINATE", "alcance distinto con REFUTED -> INDETERMINATE")

# Evidencia insuficiente con referencia no resoluble (INSUFFICIENT proveniente)
ok(componer_verificaciones([I, I], ["runtime","runtime"])["estado_compuesto"] == "INSUFFICIENT", "I/I -> INSUFFICIENT")

# Procedencia conservada y orden determinista
r1 = componer_verificaciones([S, R], ["runtime","runtime"])
r2 = componer_verificaciones([R, S], ["runtime","runtime"])
ok(r1["estado_compuesto"] == r2["estado_compuesto"] == "REFUTED", "procedencia determinista (orden)")
ok("res_real_001" in str(r1.get("referencias_utilizadas",[])), "procedencia conservada")

# Entrada malformada (resultado desconocido)
ok(componer_verificaciones([{"resultado":"MALFORMADO","integridad_evidencia":{"hash_sha256":HASH},"motivo":"x"}], ["runtime"])["estado_compuesto"] == "INDETERMINATE", "malformado -> INDETERMINATE")

# Sin escrituras operativas
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
antes = c.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
c.close()
for _ in range(3): componer_verificaciones([S,S],["r","r"])
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
despues = c.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
c.close()
ok(antes == despues, "sin escrituras DB", "%d == %d" % (antes, despues))

# Regresion 224 (compositor sin cambios en integridad)
from rxre.contracts.evidence_verification_composition import componer_verificaciones as c224
ok(c224([S,S],["r","r"])["estado_compuesto"] == "SUPPORTED", "regresion 224")

# Regresion 225 (table preserved; R+I now REFUTED, previously INSUFFICIENT - documented)
ok(c224([R,I],["r","r"])["estado_compuesto"] == "REFUTED", "regresion 225 -> correcion 226 aplicada")

print("\n=== RESUMEN 226 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS: raise SystemExit(1)
print("226 OK")
