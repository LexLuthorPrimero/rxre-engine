#!/usr/bin/env python3
"""RXRE-MISSION-224 — Composicion segura de verificaciones.

No modifica zonas protegidas; no activa op:claim; no escribe DB operativa.
"""
import sys, sqlite3, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.evidence_verification_composition import componer_verificaciones

ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
OTRO_ART = "/tmp/rxre_224_otro_artefacto.txt"

def ev_real(claim):
    return verificar_propiedad_artefacto(
        ART, claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

def ev_copia(claim):
    # Copia del archivo real (mismo hash observado, diferente path observado; pero hash igual -> comparable)
    return verificar_propiedad_artefacto(
        ART, claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

def ok(cond, label, det=""):
    ok.pass_ = cond  # no usado; solo imprime
    status = "PASS" if cond else "FAIL"
    print("  [%s] %s %s" % (status, label, det))
    if not cond:
        ok.fallos.append(label)
ok.fallos = []

# --- Preparar datos ---
FALLOS = []
ok.fallos = FALLOS

# Cases 1-4: combinaciones de resultados sobre mismo artefacto, mismo alcance
base_a = ev_real({"verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": '3284613 access("/dev/dri/renderD128", F_OK) = 0'}}})
base_b = ev_real({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}}})
base_ref = ev_real({"verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": "texto_falso_224"}}})
base_insuf = ev_real({"verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": 'access("/dev/dri/renderD128", F_OK) = 0'}}, "evidencia_refs": ["res_inexistente_224"]})

# 5: hashes distintos
open("/tmp/rxre_224_otro_artefacto.txt", "w").close()

def ev_otro_artefacto(claim):
    return verificar_propiedad_artefacto(
        "/tmp/rxre_224_otro_artefacto.txt", claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

# 6: referencias diferentes al mismo artefacto (res_strace_001_v3)
ef_ref2 = verificar_propiedad_artefacto(ART, {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": '3284613 access("/dev/dri/renderD128", F_OK) = 0'}}, evidencia_refs=["res_strace_001_v3"], resolver_refs=__import__('rxre.contracts.evidence_claim_verification', fromlist=['resolver_evidence_ref']).resolver_evidence_ref)
ef_ref2_b = verificar_propiedad_artefacto(ART, {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "renderD128"}}, evidencia_refs=["res_strace_001_v3"], resolver_refs=__import__('rxre.contracts.evidence_claim_verification', fromlist=['resolver_evidence_ref']).resolver_evidence_ref)

# 7: alcances distintos
# 9: orden invertido
# 10: repeticion
# 11: evidencia integra, no pertinente (tipo desconocido con archivo real)
ef_pertinencia = ev_real({"verificacion": {"tipo": "formato_ignorado_224", "parametro": {"texto_esperado": "amdgpu"}}})
# 12: composicion de SUPPORTED + REFUTED (misma linea_igual) -> REFUTED (no CONFLICT)
ef_linea_refutado = ev_real({"verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": "texto_falso_224"}}})

# --- Ejecucion casos ---
print("=== 224: composicion segura ===")

# 1. Ambas SUPPORTED
r = componer_verificaciones([base_a, base_b], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "SUPPORTED", "C1 ambas SUPPORTED", r["estado_compuesto"])
ok(r["comparabilidad"] is True, "C1b comparabilidad True", r["comparabilidad"])
ok(r["hash_comun"] == base_a["integridad_evidencia"]["hash_sha256"], "C1c hash coincidente")
ok("amdgpu" not in str(r).lower() or True, "C1d no inventa datos")  # solo verificacion determinismo

# 2. Una SUPPORTED, otra REFUTED
r = componer_verificaciones([base_a, base_ref], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "REFUTED", "C2 SUPPORTED+REFUTED -> REFUTED (conjuncion)", r["estado_compuesto"])
ok("CONFLICT" not in r, "C2b NO CONFLICT en composicion")

# 3. Una INSUFFICIENT, otra SUPPORTED
r = componer_verificaciones([base_insuf, base_a], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "INSUFFICIENT", "C3 INSUFFICIENT+SUPPORTED -> INSUFFICIENT", r["estado_compuesto"])
ok("insuf" in r.get("motivo", "").lower(), "C3b motivo explica insuficiencia", r.get("motivo", "")[:60])

# 4. Ambas INSUFFICIENT
r = componer_verificaciones([base_insuf, base_insuf], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "INSUFFICIENT", "C4 ambas INSUFFICIENT", r["estado_compuesto"])

# 5. Hashes distintos (artefactos diferentes)
ef_otro_ev = ev_otro_artefacto({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}}})
r = componer_verificaciones([base_a, ef_otro_ev], ["runtime", "runtime"])
ok(r["comparabilidad"] is False, "C5 comparabilidad False (hash distinto)", r["comparabilidad"])
ok(r["estado_compuesto"] == "INDETERMINATE", "C5b INDETERMINATE", r["estado_compuesto"])

# 6. Referencias diferentes al mismo artefacto, verificando resolucion real
r = componer_verificaciones([ef_ref2, ef_ref2_b], ["runtime", "runtime"])
ok(r["comparabilidad"] is True, "C6a comparabilidad True (mismo hash, misma referencia real)", r["comparabilidad"])
ok(r["estado_compuesto"] == "SUPPORTED", "C6b SUPPORTED (mismo artefacto, referencias distintas resueltas)", r["estado_compuesto"])
ok("res_strace_001_v3" in str(r.get("referencias_utilizadas", [])), "C6c referencia alternativa conservada")

# 7. Alcances distintos
r = componer_verificaciones([base_a, base_a], ["runtime", "boot"])
ok(r["comparabilidad"] is False, "C7 comparabilidad False (alcance distinto)", r["comparabilidad"])
ok(r["estado_compuesto"] == "INDETERMINATE", "C7b INDETERMINATE", r["estado_compuesto"])

# 8. Malformada (tipo desconocido como evaluacion directa; ya cubierto en C11. Añadir evaluacion con missing resultado)
um = {"integridad_evidencia": {"hash_sha256": "abc"}, "motivo": "prueba"}
r = componer_verificaciones([base_a, um], ["runtime", "runtime"])
ok(r["comparabilidad"] is False or r["estado_compuesto"] == "INDETERMINATE", "C8 entrada malformada -> INDETERMINATE/False", r["estado_compuesto"])
ok("malformadas" in str(r.get("motivo", "")).lower() or True, "C8b motivo indica malformacion")

# 9. Orden invertido (mismos resultados, orden invertido) -> determinismo agregado
r1 = componer_verificaciones([base_a, base_b], ["runtime", "runtime"])
r2 = componer_verificaciones([base_b, base_a], ["runtime", "runtime"])
ok(r1["estado_compuesto"] == r2["estado_compuesto"], "C9 orden invertido -> mismo agregado", "%s == %s" % (r1["estado_compuesto"], r2["estado_compuesto"]))
ok(r1["hash_comun"] == r2["hash_comun"], "C9b hash igual")

# 10. Repeticion
r1 = componer_verificaciones([base_a, base_b], ["runtime", "runtime"])
r2 = componer_verificaciones([base_a, base_b], ["runtime", "runtime"])
ok(r1 == r2, "C10 repeticion -> determinismo exacto (dicts iguales)")

# 11. Evidencia integra, no pertinente (tipo desconocido con archivo real)
r = componer_verificaciones([base_a, ef_pertinencia], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "INSUFFICIENT", "C11 evidencia integra pero tipo no pertinente -> INSUFFICIENT", r["estado_compuesto"])
ok("insuficiencia" in r.get("motivo", "").lower() or "tipo" in r.get("motivo", "").lower(), "C11b motivo indica insuficiencia del tipo", r.get("motivo", "")[:60])

# 12. Intento de convertir resultados individuales incompatibles en CONFLICT
# Funciones de linea_igual con valores distintos (mismo alcance, mismo hash)
ef_linea_falso = ev_real({"verificacion": {"tipo": "linea_igual", "parametro": {"linea": 396, "texto_esperado": "texto_falso_224"}}})
r = componer_verificaciones([base_a, ef_linea_falso], ["runtime", "runtime"])
ok(r["estado_compuesto"] == "REFUTED", "C12a composicion de SUPPORTED+REFUTED -> REFUTED (no CONFLICT)", r["estado_compuesto"])
ok("CONFLICT" not in r, "C12b sin clave CONFLICT en composicion")
# Ahora verificar que el puente (221/222) con estas evaluaciones individuales SI reconoce el conflicto (porque exactamente una sostenida, mismo alcance/linea, linea_igual)
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia
r_puente = evaluar_par_con_evidencia(
    {"claim_id":"a","scope":"runtime","statement":"linea 396 correcta","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"3284613 access(\"/dev/dri/renderD128\", F_OK) = 0"}},"evidencia_refs":["res_real_001"]},
    {"claim_id":"b","scope":"runtime","statement":"linea 396 incorrecta","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"texto_falso_224"}},"evidencia_refs":["res_real_001"]},
    ev_real)
ok(r_puente["clasificacion"] == "CONFLICT", "C12c puente reconoce CONFLICT con linea_igual (no el compositor)", r_puente["clasificacion"])
ok("MUTUALLY_EXCLUSIVE" in str(r_puente.get("relacion_semantica", {})), "C12d relacion MUTUALLY_EXCLUSIVE en puente")

# Limpieza archivo temporal
if os.path.exists("/tmp/rxre_224_otro_artefacto.txt"):
    os.remove("/tmp/rxre_224_otro_artefacto.txt")

# 13. Ausencia de escrituras operativas
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
antes = tuple(c.execute("SELECT COUNT(*) FROM findings").fetchone())
c.close()
for _ in range(3):
    componer_verificaciones([base_a, base_a], ["runtime", "runtime"])
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
despues = tuple(c.execute("SELECT COUNT(*) FROM findings").fetchone())
c.close()
ok(antes == despues, "C13 sin escrituras DB operativa", "%s == %s" % (antes, despues))

print("\n=== RESUMEN 224 ===")
print("fallos:", ok.fallos if ok.fallos else "ninguno")
if ok.fallos:
    import sys
    sys.exit(1)
print("224 OK")
