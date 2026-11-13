#!/usr/bin/env python3
"""RXRE-MISSION-223 — Generalización controlada (segunda propiedad observacional).

Propiedad: archivo_contiene_texto (subcadena en archivo completo).
Artefacto: audit/strace/glxinfo_trace_20261019_005110.txt (hash registrado 9554b575...; ref res_real_001).
Contrato: evaluación independiente; puente (221/222) NO amplia MUTUALLY_EXCLUSIVE.
No modifica DB, machine, zonas protegidas; no activa op:claim.
"""
import sys, sqlite3, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.evidence_conflict_bridge import evaluar_par_con_evidencia

ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
FALLOS = []

def ok(cond, label, det=""):
    if cond:
        print("  [PASS] %s %s" % (label, det))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, det))

def ev(claim):
    return verificar_propiedad_artefacto(
        ART, claim.get("verificacion"),
        evidencia_refs=claim.get("evidencia_refs", ["res_real_001"]),
        resolver_refs=lambda cid: cid == "res_real_001")

print("=== 223: segunda propiedad observacional ===")

# 1. Evidencia real satisface propiedad (texto presente en archivo completo)
r = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}}})
ok(r["resultado"] == "SUPPORTED", "C1 SUPPORTED (texto en archivo)", r["resultado"])
ok(r["integridad_evidencia"]["hash_coincide"] is True, "C1b hash coincide")
ok(r["procedencia"] == ["res_real_001"], "C1c referencia resuelta")

# 2. Evidencia real refuta propiedad (texto ausente)
r = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "nonexistent_string_223"}}})
ok(r["resultado"] == "REFUTED", "C2 REFUTED (texto ausente)", r["resultado"])
ok(r["integridad_evidencia"]["hash_coincide"] is True, "C2b integridad verificada")

# 3. Evidencia insuficiente (referencia no resoluble)
r = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}}, "evidencia_refs": ["res_ficticio_223"]})
ok(r["resultado"] == "INSUFFICIENT", "C3 INSUFFICIENT (ref inexistente)", r["resultado"])
ok("res_ficticio_223" in r.get("referencias_faltantes", []), "C3b referencia faltante registrada")

# 4. Artefacto correcto con alcance/alcance semantico distinto (scope del claim no altera propiedad, pero puente debe ser INDETERMINATE si se compara con linea_igual)
# Aquí verificamos que la propiedad evaluada sobre el archivo real es SUPPORTED independientemente del scope del claim.
claim_prop = {"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "renderD128"}}, "scope": "kernel", "evidencia_refs": ["res_real_001"]}
r = ev(claim_prop)
ok(r["resultado"] == "SUPPORTED", "C4 propiedad independiente de scope (archivo real)", r["resultado"])
# Ahora verificar que el puente con linea_igual y archivo_contiene_texto NO genera CONFLICT (semanticas incompatibles)
r_puente = evaluar_par_con_evidencia(
    {"claim_id":"c_linea","scope":"runtime","verificacion":{"tipo":"linea_igual","parametro":{"linea":396,"texto_esperado":"3284613 access(\"/dev/dri/renderD128\", F_OK) = 0"}},"evidencia_refs":["res_real_001"]},
    {"claim_id":"c_arch","scope":"runtime","verificacion":{"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}},"evidencia_refs":["res_real_001"]},
    ev)
ok(r_puente["clasificacion"] == "INDETERMINATE", "C4b puente con propiedades distintas -> INDETERMINATE", r_puente["clasificacion"])
ok(r_puente["relacion_semantica"]["estado"] == "UNDEFINED", "C4c relacion UNDEFINED (semanticas distintas)")

# 5. Hash/procedencia incompatible (archivo distinto con misma referencia operativa)
with open("/tmp/rxre_223_otro.txt", "w") as f:
    f.write("contenido completamente distinto sin texto esperado\n")
def ev_otro(claim):
    if claim.get("evidencia_refs") == ["res_real_001"]:
        return verificar_propiedad_artefacto(
            "/tmp/rxre_223_otro.txt", claim.get("verificacion"),
            evidencia_refs=["res_real_001"], resolver_refs=lambda cid: cid == "res_real_001")
    return ev(claim)
r = ev_otro({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "amdgpu"}}, "evidencia_refs": ["res_real_001"]})
ok(r["resultado"] == "INSUFFICIENT", "C5 INSUFFICIENT (hash no coincide)", r["resultado"])
ok(r["integridad_evidencia"]["hash_coincide"] is False, "C5b hash_coincide False")

# 6. Entrada malformada (parametro sin texto_esperado; texto_esperado no str; tipo desconocido)
r = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {}}})
ok(r["resultado"] == "INSUFFICIENT", "C6a parametro incompleto -> INSUFFICIENT", r["resultado"])
r = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": 999}}})
ok(r["resultado"] == "INSUFFICIENT", "C6b texto_esperado int -> INSUFFICIENT", r["resultado"])

# 7. Determinismo (repetición idéntica)
r1 = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "renderD128"}}})
r2 = ev({"verificacion": {"tipo": "archivo_contiene_texto", "parametro": {"texto_esperado": "renderD128"}}})
ok(r1 == r2, "C7 determinismo (misma entrada -> mismo dict)")
ok(r1["resultado"] == "SUPPORTED", "C7b resultado consistente")

# 8. Comparación con linea_igual: la nueva propiedad NO debe ser considerada MUTUALLY_EXCLUSIVE
#    (ya cubierto C4b, refuerzo)

# 9. Ausencia de escrituras operativas
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
antes = tuple(c.execute("SELECT COUNT(*) FROM findings").fetchone())
c.close()
for _ in range(3):
    ev({"verificacion": {"tipo":"archivo_contiene_texto","parametro":{"texto_esperado":"amdgpu"}}})
c = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
despues = tuple(c.execute("SELECT COUNT(*) FROM findings").fetchone())
c.close()
ok(antes == despues, "C9 sin escrituras DB", "%s == %s" % (antes, despues))

# Limpieza
os.remove("/tmp/rxre_223_otro.txt")

print("\n=== RESUMEN 223 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("223 OK")
