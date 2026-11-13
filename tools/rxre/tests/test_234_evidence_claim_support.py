#!/usr/bin/env python3
"""RXRE-MISSION-234 — Prueba discriminante de respaldo evidencia-claim.
Reutiliza contracts.evidence_claim_verification (220/223/226), DB operativa (res_real_001).
No modifica zonas protegidas ni DB operativa (solo lectura).
"""
import sys, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto


REAL_ART = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
REF_OK = "res_real_001"  # exists in .rxre/storage/rxre.sqlite3; hash 9554b575...
FALLOS = []

def ok(cond, label, det=""):
    (print("  [PASS] %s %s" % (label, det)) if cond else (FALLOS.append(label), print("  [FAIL] %s %s" % (label, det))))

print("=== 234: respaldo evidencia-claim (discriminante) ===")

# --- A. SUPPORTED: linea_contiene (subcadena) en linea 396 ---
res_a = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"linea_contiene", "parametro":{"linea":396, "texto_esperado":"access(\"/dev/dri/renderD128\", F_OK) = 0"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_a["resultado"]=="SUPPORTED", "A SUPPORTED: linea_contiene subcadena", res_a["resultado"])
ok(res_a["integridad_evidencia"]["hash_coincide"] is True, "A integridad hash coincide")
ok("res_real_001" in str(res_a.get("procedencia",[])), "A procedencia res_real_001 verificada")

# --- A2. REFUTED exacto: linea_igual con texto que NO coincide exactamente (tiene prefijo de timestamp) ---
res_a2 = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"linea_igual", "parametro":{"linea":396, "texto_esperado":"access(\"/dev/dri/renderD128\", F_OK) = 0"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_a2["resultado"]=="REFUTED", "A2 REFUTED: linea_igual exacta no coincide (linea tiene prefijo)", res_a2["resultado"])

# --- B. REFUTED: misma linea, texto incorrecto ---
res_b = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"linea_igual", "parametro":{"linea":396, "texto_esperado":"texto_falso_234"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_b["resultado"]=="REFUTED", "B REFUTED: linea pres presente pero texto no coincide", res_b["resultado"])
ok("refutada" in res_b.get("motivo",""), "B motivo indica refutacion")

# --- C. INSUFFICIENT: propiedad no examinada por verificador (tipo desconocido) ---
res_c = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"propiedad_semantica_general", "parametro":{"tema":"driver"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_c["resultado"]=="INSUFFICIENT", "C INSUFFICIENT: tipo no implementado", res_c["resultado"])
ok("no implementado" in res_c.get("motivo",""), "C limita clase acotada")

# --- D. Alcance incompatible: mismo artefacto / hash, pero contexto de claim distinto ---
# El verificador NO compara scope; la comparabilidad pertenece al puente/composicion (226).
# Documentamos que resultado es igual (SUPPORTED para A) pero NO comparable sin mismo alcance.
res_d = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"archivo_contiene_texto", "parametro":{"texto_esperado":"amdgpu"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_d["resultado"]=="SUPPORTED", "D propiedad soportada (archivo_contiene_texto)", res_d["resultado"])
ok(res_d["integridad_evidencia"]["hash_coincide"]==True, "D integridad OK")
# Alcance no verificado por esta capa; se documenta como limite de comparabilidad.
print("     NOTA D: resultado es SUPPORTED para el artefacto, pero comparabilidad con claim de alcance distinto requiere contrato 226 (mismo hash + mismo scope).")

# --- E. INSUFFICIENT / REFUTED: contenido no demuestra afirmacion ---
res_e = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"archivo_contiene_texto", "parametro":{"texto_esperado":"texto_inexistente_234_abc"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_e["resultado"]=="REFUTED", "E REFUTED: texto no presente en archivo observado", res_e["resultado"])
ok(res_e["integridad_evidencia"]["hash_coincide"]==True, "E integridad intacta (artefacto real no alterado)")

# --- F. INSUFFICIENT por referencia falsa / hash no coincidente ---
# Usamos referencia existente pero archivo alterado (simulado: no se persiste, solo lectura)
# El verificador compara hash registrado en DB con archivo observado; si no coincide, INSUFFICIENT.
ALT_ART = "/tmp/artefacto_alterado_234.txt"
with open(ALT_ART, "w") as fh:
    fh.write("modificado\n")
res_f = verificar_propiedad_artefacto(
    ALT_ART,  # archivo modificado
    claim_propiedad={"tipo":"linea_contiene", "parametro":{"linea":1,"texto_esperado":"modificado"}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_f["resultado"]=="INSUFFICIENT", "F INSUFFICIENT: hash registrado (res_real_001) no coincide con archivo observado", res_f["resultado"])
ok("hash registrado operativamente" in str(res_f.get("motivo","")) or "no coincide" in str(res_f.get("motivo","")), "F motivo menciona desajuste de integridad")

# --- Regresiones directas ---
# Segundo observable property (223) verificado real con archivo conteniendo texto
res_223 = verificar_propiedad_artefacto(
    REAL_ART,
    claim_propiedad={"tipo":"archivo_contiene_texto", "parametro":{"texto_esperado":"access("}},
    evidencia_refs=[REF_OK], resolver_refs=lambda r: r==REF_OK)
ok(res_223["resultado"]=="SUPPORTED", "223 regresion: segunda propiedad verificada con evidencia real", res_223["resultado"])

# Verificar que DB operativa no fue modificada (solo lectura de results)
import sqlite3
op = sqlite3.connect("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3")
rows_op = op.execute("SELECT (SELECT COUNT(*) FROM findings),(SELECT COUNT(*) FROM research),(SELECT COUNT(*) FROM missions)").fetchone()
op.close()
ok(rows_op==(1,0,0), "DB operativa sin modificaciones por lectura", str(rows_op))
for p in ("/home/lucas/Escritorio/rxre/tools/rxre/core/store.py",
          "/home/lucas/Escritorio/rxre/tools/rxre/core/evidence_integrity.py"):
    ok(os.path.exists(p), "zona protegida presente")

print("\n=== RESUMEN 234 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS: sys.exit(1)
print("234 OK")
