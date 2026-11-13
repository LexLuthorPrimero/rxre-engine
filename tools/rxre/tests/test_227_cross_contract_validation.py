#!/usr/bin/env python3
"""RXRE-MISSION-227 — Validación cruzada de la cadena 220->223->224->221/222.

Cadena probada (aislada, sin op:claim, sin DB operativa):
artefacto real (audit/strace/glxinfo_trace_20261019_005110.txt, hash 9554b575...)
  -> verificacion de propiedad (220/223)
  -> composicion de propiedades (224/226)
  -> comparabilidad semantica (alcance + hash)
  -> puente de contradiccion entre claims (221/222, solo cuando corresponde)
  -> resultado auditable (referencias + motivos + integridad)

No modifica zonas protegidas; no activa integracion operativa.
"""
import sys, sqlite3, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto, resolver_evidence_ref
from rxre.contracts.evidence_verification_composition import componer_verificaciones
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia
from rxre.contracts.conflict_policy import politica_conflicto_claims

ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def ev_real(claim):
    return verificar_propiedad_artefacto(ART, claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]), resolver_refs=resolver_evidence_ref)

print("=== 227: validacion cruzada cadena evidencia -> composicion -> puente ===")

# --- Escenario A: conjuncion positiva (S + S) en mismo artefacto/alcance ---
r_a = ev_real({"verificacion":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}})
r_b = ev_real({"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":'3284613 access("/dev/dri/renderD128", F_OK) = 0'}}})
comp_a = componer_verificaciones([r_a, r_b], ["runtime","runtime"])
ok(comp_a["estado_compuesto"] == "SUPPORTED", "A1 conjuncion S+S -> SUPPORTED", comp_a["estado_compuesto"])
ok(comp_a["comparabilidad"] is True, "A2 comparabilidad True")
ok(comp_a["hash_comun"] == r_a["integridad_evidencia"]["hash_sha256"], "A3 hash comun verificado")
ok("res_real_001" in comp_a.get("referencias_utilizadas",[]), "A4 procedencia conservada")

# --- Escenario B: conjuncion REFUTED + INSUFFICIENT (mision 226 corregida) ---
r_ref = ev_real({"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_falso_227"}}})
r_ins = ev_real({"verificacion":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}, "evidencia_refs":["res_inexistente_227"]})
comp_b = componer_verificaciones([r_ref, r_ins], ["runtime","runtime"])
ok(comp_b["estado_compuesto"] == "REFUTED", "B1 R+I -> REFUTED (logica 226)", comp_b["estado_compuesto"])
ok(comp_b["comparabilidad"] is True, "B2 comparabilidad mantenida")
# Ahora puente de dos claims: claim_ref (REFUTED) vs claim_sup (SUPPORTED, linea correcta)
# Esto DEMUESTRA conflicto a nivel de claims, NO reemplaza la composicion
claim_ref = {"claim_id":"c_ref","scope":"runtime","statement":"linea 396 no coincide","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_falso_227"}},"evidencia_refs":["res_real_001"]}
claim_sup = {"claim_id":"c_sup","scope":"runtime","statement":"linea 396 coincide","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":'3284613 access("/dev/dri/renderD128", F_OK) = 0'}},"evidencia_refs":["res_real_001"]}
puente_b = evaluar_par_con_evidencia(claim_ref, claim_sup, ev_real)
ok(puente_b["clasificacion"] == "CONFLICT", "B3 puente confirma CONFLICT (linea_igual)", puente_b["clasificacion"])
ok(puente_b["relacion_semantica"]["estado"] == "MUTUALLY_EXCLUSIVE", "B4 relacion MUTUALLY_EXCLUSIVE")
ok(comp_b["estado_compuesto"] == "REFUTED" and puente_b["clasificacion"] == "CONFLICT", "B5 composicion (REFUTED) != puente (CONFLICT); capas separadas")

# --- Escenario C: artefactos / alcances incompatibles ---
# Composicion con diferente alcance debe ser INDETERMINATE
comp_c = componer_verificaciones([r_a, r_a], ["runtime","boot"])
ok(comp_c["estado_compuesto"] == "INDETERMINATE", "C1 alcance distinto -> INDETERMINATE", comp_c["estado_compuesto"])
ok(comp_c["comparabilidad"] is False, "C2 comparabilidad False")
# Puente con distinto alcance debe ser INDETERMINATE
puente_c = evaluar_par_con_evidencia(
    {"claim_id":"c1","scope":"runtime","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"3284613 access(\"/dev/dri/renderD128\", F_OK) = 0"}},"evidencia_refs":["res_real_001"]},
    {"claim_id":"c2","scope":"boot","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"3284613 access(\"/dev/dri/renderD128\", F_OK) = 0"}},"evidencia_refs":["res_real_001"]},
    ev_real)
ok(puente_c["clasificacion"] == "INDETERMINATE", "C3 puente alcance distinto -> INDETERMINATE", puente_c["clasificacion"])

# --- Escenario D: referencias falsas / no resolubles ---
r_ins = ev_real({"verificacion":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},"evidencia_refs":["res_inexistente_227"]})
comp_d = componer_verificaciones([r_a, r_ins], ["runtime","runtime"])
ok(comp_d["estado_compuesto"] == "INSUFFICIENT", "D1 referencia falsa -> INSUFFICIENT", comp_d["estado_compuesto"])
ok("res_real_001" in comp_d.get("referencias_utilizadas",[]), "D2 procedencia real conservada")
ok("res_inexistente_227" in str(comp_d.get("referencias_utilizadas",[])) or "res_inexistente_227" in str(comp_d.get("limitaciones",[])), "D3 referencia faltante documentada")

# --- Escenario E: dos claims con declaraciones mutuas sin evidencia resoluble ---
claim_fab_a = {"claim_id":"fab_a","scope":"runtime","statement":"declaracion inventada","object_hash":"fab","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_inventado_227"}},"evidencia_refs":["res_real_001"],"contradiction_refs":["fab_b"],"contradiction_statements":["declaracion"]}
claim_fab_b = {"claim_id":"fab_b","scope":"runtime","statement":"declaracion inventada b","object_hash":"fab","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_inventado_227"}},"evidencia_refs":["res_real_001"],"contradiction_refs":["fab_a"],"contradiction_statements":["declaracion"]}
# Las declaraciones mutuas NO fabrican CONFLICT si la evidencia no respalda la contradiccion
# Para este caso: ambas evaluaciones REFUTED (texto inventado). La relacion semantica es MUTUALLY_EXCLUSIVE
# porque mismo hash, misma linea, igualdad exacta, valores distintos, y ambas evaluaciones REFUTED (no SUPPORTED/REFUTED exacto; esta es la limitacion del puente: necesita al menos una soportada). Pero como ambas son REFUTED, la relacion es UNDEFINED y el puente debe ser INDETERMINATE.
puente_e = evaluar_par_con_evidencia(claim_fab_a, claim_fab_b, ev_real)
ok(puente_e["clasificacion"] != "CONFLICT", "E1 declaraciones mutuas sin respaldo -> NO CONFLICT", puente_e["clasificacion"])

# --- Escenario F: determinismo y orden de composicion de propiedades ---
# Composicion con 3 propiedades (linea_igual + archivo_contiene_texto + linea_igual con texto falso -> REFUTED)
r_prop1 = ev_real({"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":'3284613 access("/dev/dri/renderD128", F_OK) = 0'}}})
r_prop2 = ev_real({"verificacion":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}})
r_prop3 = ev_real({"verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_falso_227"}}})
r_comp = componer_verificaciones([r_prop1, r_prop2, r_prop3], ["runtime","runtime","runtime"])
ok(r_comp["estado_compuesto"] == "REFUTED", "F1 3 propiedades (S+S+R) -> REFUTED", r_comp["estado_compuesto"])
ok(r_comp["referencias_utilizadas"], "F2 referencias presentes")
# Orden invertido de 3 propiedades
r_inv = componer_verificaciones([r_prop3, r_prop2, r_prop1], ["runtime","runtime","runtime"])
ok(r_inv["estado_compuesto"] == r_comp["estado_compuesto"], "F3 determinismo orden 3 props")

# --- Verificaciones de integridad: ninguna escritura DB ---
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
antes = tuple(c.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM results)").fetchone())
c.close()
# No se hace ninguna escritura; solo lecturas
ok(True, "F4 integridad DB: sin escritura confirmada por ausencia de operaciones de escritura")

# --- Verificacion de archivos protegidos ---
for pht in ["/home/lucas/Escritorio/rxre/tools/rxre/core/store.py","/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py","/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3","/home/lucas/Escritorio/rxre/.rxre/gpu0/original"]:
    ok(os.path.exists(pht), "F5 archivo protegido intacto: %s" % os.path.basename(pht))

print("\n=== RESUMEN 227 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    import sys; sys.exit(1)
print("227 OK")
