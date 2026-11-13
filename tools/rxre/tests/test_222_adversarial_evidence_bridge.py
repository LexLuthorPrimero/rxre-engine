#!/usr/bin/env python3
"""RXRE-MISSION-222 — Pruebas adversariales del puente de conflictos (221).

Objetivo: REFUTAR el contrato, no acumular pruebas positivas.
Cada ataque altera UNA sola precondición de MUTUALLY_EXCLUSIVE.
Evidencia: artefacto real audit/strace/glxinfo_trace_20261019_005110.txt
(ref res_real_001). Fixtures sintéticas: fixture_222_*.
"""
import sys, os, sqlite3
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia

ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
OTRO_ART = "/tmp/rxre_222_otro_artefacto.txt"
FALLOS = []
LINEA_REAL = '3284613 access("/dev/dri/renderD128", F_OK) = 0'

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def ev_real(claim):
    return verificar_propiedad_artefacto(
        ART, claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

# --- Base: par que SI cumple todas las precondiciones (CONFLICT de referencia) ---
BASE_A = {
    "claim_id": "fixture_222_a", "scope": "runtime", "object_hash": "fixture_222_obj",
    "verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": LINEA_REAL}},
    "evidencia_refs": ["res_real_001"],
}
BASE_B = {
    "claim_id": "fixture_222_b", "scope": "runtime", "object_hash": "fixture_222_obj",
    "verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": '3284613 openat("/dev/dri/renderD128", O_RDONLY) = 3'}},
    "evidencia_refs": ["res_real_001"],
}

print("=== 222: ataques al puente de conflictos ===")

# 0. Línea base: CONFLICT esperado (todas las precondiciones cumplidas)
r = evaluar_par_con_evidencia(BASE_A, BASE_B, ev_real)
ok(r["clasificacion"] == "CONFLICT", "A0 base -> CONFLICT (referencia)",
   r["clasificacion"])
ok(r["relacion_semantica"]["estado"] == "MUTUALLY_EXCLUSIVE", "A0 relacion MUTUALLY_EXCLUSIVE")
ok(r["evaluaciones"]["a"]["resultado"] == "SUPPORTED" and r["evaluaciones"]["b"]["resultado"] == "REFUTED",
   "A0 evaluaciones SUPPORTED/REFUTED")

# 1. Mismo texto y alcance, hash diferente (artefacto distinto)
with open(OTRO_ART, "w", encoding="utf-8") as f:
    f.write("contenido distinto\n")
def ev_otro(claim):
    if claim.get("claim_id") == "fixture_222_b":
        return verificar_propiedad_artefacto(OTRO_ART, claim.get("verificacion"),
                                             evidencia_refs=["res_real_001"],
                                             resolver_refs=lambda cid: cid == "res_real_001")
    return ev_real(claim)
r = evaluar_par_con_evidencia(BASE_A, dict(BASE_B, claim_id="fixture_222_b"), ev_otro)
ok(r["clasificacion"] != "CONFLICT", "A1 hash distinto -> NO CONFLICT", r["clasificacion"])

# 2. Mismo hash y texto, alcance diferente
r = evaluar_par_con_evidencia(BASE_A, dict(BASE_B, scope="boot"), ev_real)
ok(r["clasificacion"] != "CONFLICT", "A2 alcance distinto -> NO CONFLICT", r["clasificacion"])

# 2b. ALCANCE AUSENTE (None) en ambos -> no debe fabricar CONFLICT
r = evaluar_par_con_evidencia(dict(BASE_A, scope=None), dict(BASE_B, scope=None), ev_real)
ok(r["clasificacion"] != "CONFLICT", "A2b alcance ausente -> NO CONFLICT", r["clasificacion"])

# 2c. ALCANCE VACIO ("") en ambos
r = evaluar_par_con_evidencia(dict(BASE_A, scope=""), dict(BASE_B, scope=""), ev_real)
ok(r["clasificacion"] != "CONFLICT", "A2c alcance vacio -> NO CONFLICT", r["clasificacion"])

# 3. Referencias malformadas / inexistentes
r = evaluar_par_con_evidencia(dict(BASE_A, evidencia_refs=["res_inexistente_222"]), BASE_B, ev_real)
ok(r["clasificacion"] != "CONFLICT", "A3 ref inexistente -> NO CONFLICT", r["clasificacion"])

# 3b. Referencias duplicadas en el par
r = evaluar_pair = evaluar_par_con_evidencia(
    dict(BASE_A, evidencia_refs=["res_real_001", "res_real_001"]),
    dict(BASE_B, evidencia_refs=["res_real_001", "res_real_001"]), ev_real)
ok(r["clasificacion"] == "CONFLICT", "A3b refs duplicadas -> CONFLICT (no alteran)", r["clasificacion"])

# 4. Evidencia valida para A e insuficiente para B (B no declara procedencia)
r = evaluar_par_con_evidencia(BASE_A, dict(BASE_B, evidencia_refs=[]), ev_real)
ok(r["clasificacion"] != "CONFLICT", "A4 evidencia insuficiente en B -> NO CONFLICT", r["clasificacion"])
ok(r["capa"] == "evidencia", "A4b capa = evidencia", r["capa"])

# 5. Simetria A/B
r_ab = evaluar_par_con_evidencia(BASE_A, BASE_B, ev_real)
r_ba = evaluar_par_con_evidencia(BASE_B, BASE_A, ev_real)
ok(r_ab["clasificacion"] == r_ba["clasificacion"], "A5 simetria de clasificacion",
   "%s == %s" % (r_ab["clasificacion"], r_ba["clasificacion"]))
ok(r_ab["relacion_semantica"]["estado"] == r_ba["relacion_semantica"]["estado"],
   "A5b simetria de relacion semantica")

# 6. Tipos ambiguos: linea como string
try:
    r = evaluar_par_con_evidencia(
        dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": {"linea": "396", "texto_esperado": LINEA_REAL}}),
        BASE_B, ev_real)
    ok(r["clasificacion"] != "CONFLICT", "A6 linea como string -> NO CONFLICT (sin crash)", r["clasificacion"])
except Exception as e:
    ok(False, "A6 linea como string -> NO CONFLICT (sin crash)", "EXCEPCION: %s" % e)

# 6b. texto_esperado no string
try:
    r = evaluar_par_con_evidencia(
        dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": 12345}}),
        BASE_B, ev_real)
    ok(r["clasificacion"] != "CONFLICT", "A6b texto no string -> NO CONFLICT (sin crash)", r["clasificacion"])
except Exception as e:
    ok(False, "A6b texto no string -> NO CONFLICT (sin crash)", "EXCEPCION: %s" % e)

# 6c. 'verificacion' con tipo incorrecto (string) -> no debe crashear
try:
    r = evaluar_par_con_evidencia(dict(BASE_A, verificacion="linea_igual"), BASE_B, ev_real)
    ok(r["clasificacion"] != "CONFLICT", "A6c verificacion no-dict -> NO CONFLICT (sin crash)", r["clasificacion"])
except Exception as e:
    ok(False, "A6c verificacion no-dict -> NO CONFLICT (sin crash)", "EXCEPCION: %s" % e)

# 6d. 'parametro' no dict
try:
    r = evaluar_par_con_evidencia(
        dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": "396"}), BASE_B, ev_real)
    ok(r["clasificacion"] != "CONFLICT", "A6d parametro no-dict -> NO CONFLICT (sin crash)", r["clasificacion"])
except Exception as e:
    ok(False, "A6d parametro no-dict -> NO CONFLICT (sin crash)", "EXCEPCION: %s" % e)

# 7. Linea fuera de rango
r = evaluar_par_con_evidencia(
    dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": {"linea": 99999, "texto_esperado": "x"}}),
    BASE_B, ev_real)
ok(r["clasificacion"] != "CONFLICT", "A7 linea fuera de rango -> NO CONFLICT", r["clasificacion"])

# 8. Final de linea / codificacion: texto con \r\n
#    Contrato (mision 222, defecto D5): una contradiccion ENTRE las afirmaciones
#    exige que exactamente una se sostenga sobre la evidencia observada. Aqui la
#    afirmacion con CRLF y la afirmacion openat son AMBAS refutadas: el desacuerdo
#    es de cada una con la evidencia, no entre ellas -> INDETERMINATE.
r = evaluar_par_con_evidencia(
    dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": LINEA_REAL + "\r\n"}}),
    BASE_B, ev_real)
ok(r["clasificacion"] == "INDETERMINATE", "A8 CRLF mismatching -> INDETERMINATE (ambas refutadas)", r["clasificacion"])
ok(r["relacion_semantica"]["estado"] == "UNDEFINED", "A8b relacion no demostrable", r["relacion_semantica"]["estado"])
ok(r["evaluaciones"]["a"]["resultado"] == "REFUTED" and r["evaluaciones"]["b"]["resultado"] == "REFUTED",
   "A8c ambas refutadas")
ok(r["capa"] == "relacion_semantica", "A8d capa = relacion_semantica", r["capa"])

# 8b. Dos afirmaciones refutadas (misma linea, valores distintos, ninguno real)
r = evaluar_par_con_evidencia(
    dict(BASE_A, verificacion={"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": "texto_falso_1"}}),
    dict(BASE_B, verificacion={"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": "texto_falso_2"}}),
    ev_real)
ok(r["clasificacion"] == "INDETERMINATE", "A8e dos refutadas -> INDETERMINATE (no son contradictorias)", r["clasificacion"])
ok("REFUTED" in r["motivo"], "A8f motivo explicito sobre refutaciones", r["motivo"][:90])

# 9. Evidencia integra pero de otro artefacto (ya cubierto A1) + variante path distinto mismo contenido
import shutil
COPIA = "/tmp/rxre_222_copia_identica.txt"
shutil.copyfile(ART, COPIA)
def ev_copia(claim):
    if claim.get("claim_id") == "fixture_222_b":
        return verificar_propiedad_artefacto(COPIA, claim.get("verificacion"),
                                             evidencia_refs=["res_real_001"],
                                             resolver_refs=lambda cid: cid == "res_real_001")
    return ev_real(claim)
r = evaluar_par_con_evidencia(BASE_A, BASE_B, ev_copia)
ok(r["clasificacion"] == "CONFLICT", "A9 copia byte-identica (mismo hash) -> CONFLICT", r["clasificacion"])

# 10. Declaraciones de contradiccion que NO corresponden al par -> el puente no debe usarlas
r = evaluar_par_con_evidencia(
    dict(BASE_A, contradiction_refs=["fixture_222_ajeno"], contradiction_statements=["declaracion ajena"]),
    dict(BASE_B, contradiction_refs=["fixture_222_ajeno2"], contradiction_statements=["declaracion ajena2"]),
    ev_real)
ok(r["clasificacion"] in ("CONFLICT", "INDETERMINATE"), "A10 declaraciones ajenas -> no fabrica semantica", r["clasificacion"])
ok(r["relacion_semantica"]["estado"] in ("MUTUALLY_EXCLUSIVE", "UNDEFINED"), "A10b relacion coherente",
   r["relacion_semantica"]["estado"])

# 11. Determinismo
rs = [evaluar_par_con_evidencia(BASE_A, BASE_B, ev_real) for _ in range(3)]
ok(rs[0] == rs[1] == rs[2], "A11 determinismo (3 repeticiones identicas)")

# 12. Variacion de un solo campo desde un CONFLICT valido
variaciones = [
    ("scope distinto", dict(BASE_B, scope="otro")),
    ("tipo de verificacion subcadena", dict(BASE_B, verificacion={"tipo": "linea_contiene", "parametro": {"linea": 396, "texto_esperado": "F_OK) = 0"}})),
    ("linea distinta", dict(BASE_B, verificacion={"tipo": "linea_igual", "parametro": {"linea": 397, "texto_esperado": "3284613 openat(AT_FDCWD, \"/usr/share/libdrm/amdgpu.ids\", O_RDONLY) = 7"}})),
    ("valor identico", dict(BASE_B, verificacion=BASE_A["verificacion"])),
    ("ref inexistente", dict(BASE_B, evidencia_refs=["res_no_existe_222"])),
]
for etiqueta, mutado in variaciones:
    r = evaluar_par_con_evidencia(BASE_A, mutado, ev_real)
    ok(r["clasificacion"] != "CONFLICT", "A12 variacion '%s' -> NO CONFLICT" % etiqueta, r["clasificacion"])

# 14. Auditar precondiciones de todo CONFLICT: referencias resueltas, integridad de hash,
#     misma linea/alcance/semantica, evaluaciones SUPPORTED/REFUTED, determinismo.
def auditar_conflict(r, label):
    ok(r["clasificacion"] == "CONFLICT", "AUDIT-CONFLICT %s clasificacion" % label, r.get("clasificacion"))
    ok(r["relacion_semantica"]["estado"] == "MUTUALLY_EXCLUSIVE", "AUDIT-CONFLICT %s relacion" % label)
    ok(r["evaluaciones"]["a"]["resultado"] in ("SUPPORTED","REFUTED") and r["evaluaciones"]["b"]["resultado"] in ("SUPPORTED","REFUTED"),
       "AUDIT-CONFLICT %s evaluaciones verificadas" % label)
    # Referencias resolubles: ninguna faltante en evaluaciones
    falt_a = r["evaluaciones"]["a"].get("referencias_faltantes", [])
    falt_b = r["evaluaciones"]["b"].get("referencias_faltantes", [])
    ok(len(falt_a) == 0 and len(falt_b) == 0, "AUDIT-CONFLICT %s sin referencias faltantes (a=%s,b=%s)" % (label, falt_a, falt_b))
    # Hash coincidente con registro operativo para el par comparado
    hash_a = (r["evaluaciones"]["a"].get("integridad_evidencia") or {}).get("hash_coincide")
    hash_b = (r["evaluaciones"]["b"].get("integridad_evidencia") or {}).get("hash_coincide")
    ok(hash_a is True and hash_b is True, "AUDIT-CONFLICT %s hash_coincide (a=%s,b=%s)" % (label, hash_a, hash_b))

# Audit de todos los casos que deben ser CONFLICT (exactamente una sostenida)
for label, pair in [("A0", (BASE_A, BASE_B)),
                    ("A3b", (dict(BASE_A, evidencia_refs=["res_real_001","res_real_001"]), dict(BASE_B, evidencia_refs=["res_real_001","res_real_001"]))),
                    ("A9", (BASE_A, BASE_B))]:
    ev = ev_copia if label=="A9" else ev_real
    rr = evaluar_par_con_evidencia(pair[0], pair[1], ev)
    auditar_conflict(rr, label)

# 13. Ausencia de escrituras operativas
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
antes = tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM results)").fetchone())
c.close()
evaluar_par_con_evidencia(BASE_A, BASE_B, ev_real)
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
despues = tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM results)").fetchone())
c.close()
ok(antes == despues, "A13 sin escrituras en DB operativa", "%s == %s" % (antes, despues))

for f in (OTRO_ART, COPIA):
    if os.path.exists(f):
        os.remove(f)

print("\n=== RESUMEN 222 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("222 OK")
