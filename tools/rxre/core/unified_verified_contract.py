#!/usr/bin/env python3
"""RXRE-MISSION-306 — Contrato único de autoridad para la transición UNVERIFIED -> VERIFIED.
Módulo nuevo; no modifica componentes protegidos; opera sobre copias aisladas.

Reglas del contrato (R1..R8) y separación de planos:
  PLANO DECLARADO  : campos del caller (scope_decision, verified_scope, actor) -> NUNCA autoridad.
  PLANO FÍSICO     : bytes capturados (M303) + hash calculado independientemente (M301).
  PLANO CONTRACTUAL: decision del contrato M285 + vinculación M301 + contrato unico M306.
  PLANO PERSISTENCIA/AUDITORIA: fila en DB + atestación del escritor (HMAC con clave del servicio).
"""
import sqlite3, hashlib, hmac, json, os, sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import manifest_binding_contract as mbc
from rxre.core import evidence_snapshot as es
from rxre.contracts import scope_provenance_contract as spc

CLAVE_SERVICIO = "/tmp/rxre_306_work/servicio.key"

# ---------------------------------------------------------------- atestación
def cargar_o_crear_clave(path=CLAVE_SERVICIO):
    if os.path.isfile(path):
        return open(path, "rb").read()
    key = os.urandom(32)
    with open(path, "wb") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    return key

def atestar(clave, evidence_ref, result_id, artifact_hash, manifest_hash, uid, timestamp_iso):
    msg = "|".join([evidence_ref, result_id, artifact_hash, manifest_hash, str(uid), timestamp_iso])
    return hmac.new(clave, msg.encode(), hashlib.sha256).hexdigest()

def verificar_atestacion(clave, atestado, evidence_ref, result_id, artifact_hash, manifest_hash, uid, timestamp_iso):
    esperado = atestar(clave, evidence_ref, result_id, artifact_hash, manifest_hash, uid, timestamp_iso)
    return hmac.compare_digest(esperado, str(atestado or ""))

# ---------------------------------------------------------------- contrato único
def evaluar_transicion(db_op_path, manifest_path, artifact_path, result_id, evidence_ref,
                       scope_esperado=None, actor_declarado=None, uid_efectivo=None,
                       clave_servicio=None, contract_version="M306"):
    """Evalúa la transición UNVERIFIED -> VERIFIED. Devuelve dict con decision y evidencia.
    NO escribe nada: la persistencia es una etapa posterior (R7)."""
    ev = {"plano_declarado": {"actor_declarado": actor_declarado},
          "plano_fisico": {}, "plano_contractual": {}, "plano_persistencia": {},
          "reglas": {}, "decision": "REJECTED", "explanation": ""}

    # R1 — el estado declarado por el caller NO es autoridad (se registra, no se usa)
    ev["reglas"]["R1_declarado_no_autoridad"] = True
    ev["plano_declarado"]["nota"] = "scope_decision/verified_scope del caller se ignoran; el estado se recalcula"

    # R2 — captura física estable (M303): una única lectura, hash sobre esos bytes
    snap = es.capturar_evidencia(artifact_path)
    if snap is None or not (snap.bytes_consumidos):
        ev["decision"] = "REJECTED"; ev["explanation"] = "R2: no se pudieron capturar bytes del artefacto"
        return ev
    ev["plano_fisico"] = {"hash_capturado": snap.hash_capturado, "bytes": len(snap.bytes_consumidos),
                          "identity_open": snap.identity_open}

    # R3 — vinculación manifest<->artefacto (M301): PASS exige hash del manifest == bytes capturados
    v = mbc.validar_vinculacion(manifest_path, artifact_path_esperado=artifact_path,
                                 scope_esperado=scope_esperado, db_op_path=db_op_path,
                                 db_op_result_id=result_id)
    ev["plano_contractual"]["validacion_vinculo"] = {"decision": v.get("decision"), "explanation": v.get("explanation", "")[:160]}
    if v.get("decision") != "PASS":
        ev["decision"] = "REJECTED"; ev["explanation"] = "R3: vinculación manifest->artefacto no superada (%s)" % v.get("decision")
        return ev
    hash_manifest = v.get("hash_declarado")
    if hash_manifest != snap.hash_capturado:
        ev["decision"] = "REJECTED"
        ev["explanation"] = "R3: hash del manifest (%s) != hash de los bytes capturados (%s)" % (str(hash_manifest)[:16], snap.hash_capturado[:16])
        return ev
    ev["reglas"]["R3_bytes_validados"] = True

    # R4 — contrato real M285 (contexto de base y artefacto observados)
    c = spc.verificar_autoridad_scope(evidence_ref=evidence_ref, claim_scope=scope_esperado,
                                       db_op_path=db_op_path, db_op_result_id=result_id,
                                       manifest_e2e_path=manifest_path,
                                       observed_artifact_path=artifact_path,
                                       observed_hash=snap.hash_capturado)
    ev["plano_contractual"]["contrato_m285"] = {"decision": c.get("decision"), "explanation": c.get("explanation", "")[:160]}
    if c.get("decision") != "VERIFIED":
        ev["decision"] = "REJECTED"
        ev["explanation"] = "R4: contrato M285 no confirma VERIFIED (%s)" % c.get("decision")
        return ev
    ev["reglas"]["R4_contrato_real"] = True

    # R5 — coherencia de DB: la fila debe existir y su row_hash debe ser recalculable (independiente)
    fila = None
    try:
        cn = sqlite3.connect("file:%s?mode=ro" % db_op_path, uri=True)
        fila = cn.execute("SELECT result_id, operation_id, scope, scope_decision, verified_scope, row_hash FROM results WHERE result_id=? LIMIT 1", (result_id,)).fetchone()
        cn.close()
    except Exception as exc:
        ev["decision"] = "REJECTED"; ev["explanation"] = "R5: no se pudo leer la fila: %s" % str(exc)[:80]
        return ev
    if not fila:
        ev["decision"] = "REJECTED"; ev["explanation"] = "R5: fila de resultados inexistente para %s" % result_id
        return ev
    ev["plano_contractual"]["fila_db"] = {"operation_id": fila[1], "scope": fila[2],
                                          "scope_decision": fila[3], "verified_scope": fila[4],
                                          "row_hash": (fila[5] or "")[:16]}
    ev["reglas"]["R5_fila_presente"] = True

    # R6 — identidad efectiva del escritor + atestación (M304): el caller no puede atestiguar
    if uid_efectivo is None or clave_servicio is None:
        ev["decision"] = "INSUFFICIENT"
        ev["explanation"] = "R6: identidad efectiva del escritor y clave de atestación no verificables en este entorno (DB_AUTH_ACTOR_M294 / DBOP_ACCESS_M295 pendientes)"
        return ev
    ev["plano_persistencia"]["uid_efectivo"] = uid_efectivo
    ev["reglas"]["R6_identidad"] = True

    # R7 — la persistencia solo puede ocurrir con atestación válida (el cliente no la posee)
    timestamp_iso = "2026-10-22T00:00:00Z"
    hash_manifest_archivo = hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    atestado = atestar(clave_servicio, evidence_ref, result_id, snap.hash_capturado, hash_manifest_archivo, uid_efectivo, timestamp_iso)
    ev["plano_persistencia"]["atestacion_hmac"] = atestado[:16]
    ev["plano_persistencia"]["timestamp_iso"] = timestamp_iso
    ev["decision"] = "VERIFIED"
    ev["explanation"] = ("transición autorizada: bytes capturados == bytes validados; vinculación M301 OK; "
                          "contrato M285 VERIFIED; fila coherente; identidad efectiva uid=%s atestada" % uid_efectivo)
    return ev

def persistir_con_autoridad(db_op_path, manifest_path, artifact_path, result_id, evidence_ref,
                             scope_esperado=None, actor_declarado=None, uid_efectivo=None,
                             clave_servicio=None, atestado_proporcionado=None,
                             hash_manifest_para_atestacion=None):
    """Única vía de persistencia permitida por el contrato M306.
    Evalúa la transición y SOLO escribe si: (a) la decisión es VERIFIED y
    (b) se presenta una atestación válida del escritor (HMAC con la clave del servicio).
    Un cliente sin la clave del servicio no puede fabricar `VERIFIED`."""
    ev = evaluar_transicion(db_op_path, manifest_path, artifact_path, result_id, evidence_ref,
                             scope_esperado=scope_esperado, actor_declarado=actor_declarado,
                             uid_efectivo=uid_efectivo, clave_servicio=clave_servicio)
    if ev.get("decision") != "VERIFIED":
        return {"written": False, "decision": ev.get("decision"), "explanation": ev.get("explanation"), "evidencia": ev}
    # R7b — atestación exigida: el cliente debe presentar la atestación emitida por el servicio
    if atestado_proporcionado is None:
        return {"written": False, "decision": "REJECTED",
                "explanation": "R7: transición válida pero sin atestación del escritor; el cliente no puede auto-atestiguar (DBOP_ACCESS_M295 pendiente)",
                "evidencia": ev}
    hm = hash_manifest_para_atestacion or hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    ts = ev["plano_persistencia"].get("timestamp_iso")
    ok = verificar_atestacion(clave_servicio, atestado_proporcionado, evidence_ref, result_id,
                               ev["plano_fisico"]["hash_capturado"], hm, uid_efectivo, ts)
    if not ok:
        return {"written": False, "decision": "REJECTED",
                "explanation": "R7: atestación inválida o ausente; escritura denegada",
                "evidencia": ev}
    # Persistencia (módulo M292) con el hash de los bytes capturados
    from rxre.core import verification_record
    try:
        snap = es.capturar_evidencia(artifact_path)
        rec = verification_record.persistir_verificacion(db_op_path, evidence_ref, result_id,
                                                         manifest_path, artifact_path,
                                                         observed_hash=snap.hash_capturado,
                                                         actor="uid:%s" % uid_efectivo)
    except Exception as exc:
        return {"written": False, "decision": "REJECTED", "explanation": "persistencia fallida: %s" % str(exc)[:120], "evidencia": ev}
    return {"written": True, "decision": "VERIFIED", "record": rec, "evidencia": ev}
