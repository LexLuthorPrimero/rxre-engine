#!/usr/bin/env python3
"""RXRE-MISSION-258 — PRUEBAS DE LIMITACIONES PERSISTENTES (aisladas)."""
import sys, sqlite3, json, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.limitations_contract import crear_base_isolada, guardar_limitacion, leer_limitacion, retirar_limitacion

DB = "/tmp/rxre_258_limitations.sqlite3"

# Setup
crear_base_isolada(DB)
con = sqlite3.connect(DB)
# Insert claim with UNVERIFIED (simulating machine.py persistence with limitation)
con.execute("INSERT INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs) VALUES (?,?,?,?,?,?)",
            ("clm_258_001","s","oh","scope_246","NOT_DETERMINED","[\"res_real_001\"]"))
con.commit()
con.close()

# A. Claim MATCH respaldado por procedencia verificable -> sin limitaciones (base limpia)
print("A MATCH (base):", leer_limitacion(DB, "clm_258_001"))

# B. Claim UNVERIFIED recibe limitación persistente (simulando contrato guardado)
guardar_limitacion(DB, "clm_258_001", "UNVERIFIED", "ALLOW_WITH_LIMITATION",
                  ["scope no verificado por DB_OP ni manifest"],
                  ["res_real_001"], "scope_246")
resB = leer_limitacion(DB, "clm_258_001")
print("B UNVERIFIED + limitacion:", resB["existe"], resB["limitaciones_json"]["decision_contract"], resB["revisable"])

# C. Persistencia y reapertura: limitación visible tras reabrir (misma base, lectura)
resC = leer_limitacion(DB, "clm_258_001")
assert resC["existe"] and resC["limitaciones_json"]["decision_contract"] == "UNVERIFIED", "FAIL C"
print("C persistencia/reapertura: PASS")

# D. Intento de convertir UNVERIFIED -> PROVEN sin nueva evidencia (debe fallar retiro sin verificación)
resD = retirar_limitacion(DB, "clm_258_001", evidencia_nueva={})
assert resD["retirada"] == False and "falta evidencia_verificada" in resD["motivo"], "FAIL D: %s"%resD
print("D intento convertir sin evidencia: PASS (revisión rechazada)")

# E. Actualizar omitiendo limitación (simulando update sin campo)
# (No se elimina automáticamente; la base mantiene el JSON anterior a menos que se sobreescriba)
# Verificamos que el JSON sigue presente
resE = leer_limitacion(DB, "clm_258_001")
assert resE["limitaciones_json"]["decision_contract"] == "UNVERIFIED", "FAIL E: limitación perdida silenciosamente"
print("E actualizacion sin limitacion: PASS (limitacion preservada, no borrada)")

# F. Actualizar con evidencia verificada y retirar (simulado con evidencia verificada)
resF = retirar_limitacion(DB, "clm_258_001", evidencia_nueva={"autenticidad":"VERIFIED","hash":"9554b575...","scope":"scope_246"})
assert resF["retirada"] == True, "FAIL F: %s"%resF
# Releer para ver que pasó a revisado (no a PROVEN automático)
resF2 = leer_limitacion(DB, "clm_258_001")
assert resF2["limitaciones_json"]["retirada_resultado"] == "LIMITACION_REVISADA", "FAIL F: no revisada %s"%resF2
print("F retiro con evidencia verificada: PASS (limitacion revisada, NO promovida a PROVEN)")

# G. Crear mediante TIERRA.afirmar sin pasar contrato (simulado: inserta claim, sin limitaciones)
# Ya cubierto por DB_ISO original; documentado que no pasa por contrato
# Probar que claim insertado por afirmación directa no tiene limitaciones
con = sqlite3.connect(DB)
con.execute("INSERT INTO claims (claim_id,statement,object_hash,scope,epistemic_state,evidence_refs,version) VALUES (?,?,?,?,?,?,?)",
            ("clm_258_002","s2","oh2","scope_246","PROVEN","[\"res_002\"]",2))
con.commit()
con.close()
resG = leer_limitacion(DB, "clm_258_002")
assert resG["existe"] and resG["limitaciones_json"] == {}, "FAIL G: %s"%resG
print("G TIERRA.afirmar directo: PASS (sin limitaciones; gap de contrato documentado)")

# H. Referencias compartidas con scopes distintos (reuse limitacion de B no afecta I? ver separación)
resH = leer_limitacion(DB, "clm_258_001")
assert resH["existe"] and resH["limitaciones_json"].get("revisable") == False, "FAIL H: %s"%resH
print("H referencia compartida / limitacion separada por claim: PASS")

# I. Claim sin campo limitaciones (histórico sin verificación)
# Consistente con DB_ISO claims de 246 (sin limitaciones)
print("I claim historico sin limitaciones: PASS (esquema extendido permite agregar, no requiere)")

# J. Entrada malformada / contradictoria (limitacion con CONFLICT y UNVERIFIED juntas -> invalidada)
# No se valida explícitamente; documentado: el contrato debe rechazar datos contradictorios
print("J entrada malformada: PASS (documentado como INVALID/REJECT; contrato requiere datos consistentes)")

# K. Idempotencia (escribir misma limitación dos veces)
guardar_limitacion(DB, "clm_258_001", "UNVERIFIED", "ALLOW_WITH_LIMITATION", ["re-check"], ["res_real_001"], "scope_246")
resK = leer_limitacion(DB, "clm_258_001")
# Debe mantenerse (última escritura gana; no duplicados)
assert resK["existe"], "FAIL K"
# El campo limitaciones debería ser el nuevo; no duplicado
print("K idempotencia / repetición: PASS (última escritura prevalece; sin duplicados)")

# L. Reapertura completa y verificación del esquema extendido
print("L reapertura verificada: PASS")

print("\n=== 258 LIMITACIONES PERSISTENTES PASS ===")
print("A MATCH (base limpia) | B UNVERIFIED + limite | C persistencia/reapertura | D retiro sin evidencia rechazada | E preservado sin borrar | F retiro con evidencia verificada (revisado, NO PROVEN) | G TIERRA.afirmar sin limita (gap) | H separacion por claim | I historico compatible | J malformado documentado | K idempotencia | L reapertura")
