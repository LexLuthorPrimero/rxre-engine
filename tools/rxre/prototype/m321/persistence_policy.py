#!/usr/bin/env python3
"""RXRE-M321 — POLÍTICA DE PERSISTENCIA AISLADA (Cierre experimental del BYPASS).
No reemplaza DB_AUTH_ACTOR_M294 / DBOP_ACCESS_M295; no declara VERIFIED producción.
NUEVO NO PROTEGIDO — viene con clave de prueba (CLAVE_SERVICIO temporal / arnés).
"""
import os, sqlite3, hashlib, hmac, json, time, secrets

DB_REGISTRY_DEFAULT = "/tmp/rxre_321_registry.sqlite3"
CLAVE_SERVICIO = "/tmp/rxre_321_service.key"

def _clave():
    if not os.path.isfile(CLAVE_SERVICIO):
        k = secrets.token_bytes(32)
        with open(CLAVE_SERVICIO, "wb") as f: f.write(k)
        os.chmod(CLAVE_SERVICIO, 0o600)
    return open(CLAVE_SERVICIO, "rb").read()

def _inig(schema_path=DB_REGISTRY_DEFAULT):
    if not os.path.isfile(schema_path):
        con = sqlite3.connect(schema_path)
        con.execute("CREATE TABLE m321_verified_registry (result_id TEXT PRIMARY KEY, artifact_hash TEXT, manifest_hash TEXT, evidence_ref TEXT, contract_decision TEXT, auth_nonce TEXT, actor_label TEXT, timestamp_iso TEXT, attestation TEXT, provenance TEXT)")
        con.execute("CREATE TABLE m321_nonces (nonce TEXT PRIMARY KEY, result_id TEXT, timestamp_iso TEXT)")
        con.execute("CREATE TABLE m321_audit (event TEXT, timestamp_iso TEXT, result_id TEXT, detail TEXT)")
        con.commit(); con.close()

def atestacion(clave, evidence_ref, result_id, artifact_hash, manifest_hash, uid_efectivo, timestamp_iso):
    msg = "|".join([evidence_ref or "", result_id, artifact_hash or "", manifest_hash or "", str(uid_efectivo or ""), timestamp_iso or ""])
    return hmac.new(clave, msg.encode(), hashlib.sha256).hexdigest()

def persistir(db_path, manifest_path, artifact_path, result_id, scope_esperado,
              actor_declarado, uid_efectivo, auth, evidence_ref=None,
              clave_servicio_path=CLAVE_SERVICIO, operation_id=None, contract_db_path=None):
    """Política única de persistencia verificable (prototipo M321)."""
    _inig(db_path)
    clave = _clave()
    # 1. Verificar que la autorización de prueba es válida (M316/M317)
    from rxre.prototype.m316 import authority
    _op = operation_id or (auth.get("payload", {}) or {}).get("operation_id")
    _mh = hashlib.sha256(open(manifest_path,"rb").read()).hexdigest() if os.path.isfile(manifest_path) else ""
    auth_result = authority.verify_authorization(auth, _op, scope_esperado, _mh)
    # Nota: la verificación de autorización es necesaria pero no suficiente (IDENTIDAD NO REAL)
    if auth_result.get("decision") not in ("PROVISIONAL_AUTHORITY_PROTOTYPE",):
        return {"persisted": False, "recognized": False, "reason": "R6_AUTH_INSUFFICIENT: autorización de prueba no válida: %s" % auth_result.get("explanation", ""), "authority_scope": "TEST_PROTOTYPE", "db_path": db_path}
    # 2. Capturar evidencia (M303)
    try:
        from rxre.core import evidence_snapshot as es
        snap = es.validar_y_capturar(manifest_path, artifact_path, scope_esperado=scope_esperado, db_op_path=(contract_db_path or db_path), db_op_result_id=result_id)
    except Exception as exc:
        snap = None
        snap_info = {"decision": "INSUFFICIENT", "explanation": "R2 evidencia no capturada: %s" % str(exc)[:80]}
    if snap is None or not (snap.bytes_consumidos):
        return {"persisted": False, "recognized": False, "reason": "R2_EVIDENCE_INCOMPLETE", "authority_scope": "TEST_PROTOTYPE", "db_path": db_path}
    # 3. Verificar contrato M306 (solo lectura; si requiere DB_OP real, podrá ser INSUFFICIENT)
    try:
        from rxre.core.unified_verified_contract import evaluar_transicion
        contract_ev = evaluar_transicion((contract_db_path or db_path), manifest_path, artifact_path, result_id, evidence_ref or result_id,
                                          scope_esperado=scope_esperado, actor_declarado=actor_declarado,
                                          uid_efectivo=uid_efectivo, clave_servicio=clave_servicio_path if os.path.isfile(clave_servicio_path) else None)
    except Exception as exc:
        contract_ev = {"decision": "INSUFFICIENT", "explanation": "R4_CONTRACT_INSUFFICIENT_NO_DBOP_AUTHORITY: %s" % str(exc)[:80]}
    # 4. Si contrato dice VERIFIED (requiere DB_OP + autor real + clave servicio), permitir escritura en registro
    #    De lo contrario, rechazar (no escribir en registro como VERIFICADO)
    if contract_ev.get("decision") not in ("VERIFIED",):
        # No escribir como VERIFICADO — solo registrar que se rechazó (para auditoría del prototipo)
        con = sqlite3.connect(db_path)
        con.execute("INSERT INTO m321_audit (event, timestamp_iso, result_id, detail) VALUES (?,?,?,?)",
                    ("REJECTED_NON_VERIFIED", time.strftime("%Y-%m-%dT%H:%M:%SZ"), result_id,
                     "contract_decision=%s auth_decision=%s" % (contract_ev.get("decision"), auth_result.get("decision"))))
        con.commit(); con.close()
        return {"persisted": False, "recognized": False, "reason": "R4_REJECTED: contrato M306 no confirma VERIFIED (%s)" % contract_ev.get("decision"), "authority_scope": "TEST_PROTOTYPE", "db_path": db_path, "contract_decision": contract_ev.get("decision")}
    # 5. Escribir registro con atestación (R7 analog) — solo aquí se permite VERIFIED en registro
    #    Este registro está fuera de DB_OP / results / results_legacy; es el registro aislado del prototipo
    artifact_hash = hashlib.sha256(open(artifact_path, "rb").read()).hexdigest()
    manifest_hash = hashlib.sha256(open(manifest_path, "rb").read()).hexdigest()
    attestation = atestacion(clave, evidence_ref or result_id, result_id, artifact_hash, manifest_hash, uid_efectivo or 0,"2026-10-22T00:00:00Z")
    nonce = auth.get("payload", {}).get("nonce", "")
    # Reutilización: nonce debe ser único en registro
    con = sqlite3.connect(db_path)
    existing_nonce = con.execute("SELECT 1 FROM m321_nonces WHERE nonce=?", (nonce,)).fetchone()
    if existing_nonce:
        con.execute("INSERT INTO m321_audit (event, timestamp_iso, result_id, detail) VALUES (?,?,?,?)",
                    ("REJECTED_REPLAY", time.strftime("%Y-%m-%dT%H:%M:%SZ"), result_id, "nonce reutilizado"))
        con.commit(); con.close()
        return {"persisted": False, "recognized": False, "reason": "REJECTED: nonce reutilizado (replay)", "authority_scope": "TEST_PROTOTYPE", "db_path": db_path}
    con.execute("INSERT INTO m321_nonces (nonce, result_id, timestamp_iso) VALUES (?,?,?)",
                (nonce, result_id, time.strftime("%Y-%m-%dT%H:%M:%SZ")))
    # Insertar registro con atestación
    con.execute("INSERT INTO m321_verified_registry (result_id, artifact_hash, manifest_hash, evidence_ref, contract_decision, auth_nonce, actor_label, timestamp_iso, attestation, provenance) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (result_id, artifact_hash, manifest_hash, evidence_ref or result_id,
                 contract_ev.get("decision"), nonce, actor_declarado or "unknown", time.strftime("%Y-%m-%dT%H:%M:%SZ"), attestation, "TEST_PROTOTYPE_M321_ISOLATED"))
    # Auditoría
    con.execute("INSERT INTO m321_audit (event, timestamp_iso, result_id, detail) VALUES (?,?,?,?)",
                ("PERSISTED", time.strftime("%Y-%m-%dT%H:%M:%SZ"), result_id,
                 "authority=%s contract=%s evidence_hash=%s..." % (auth_result.get("decision"), contract_ev.get("decision"), (snap.hash_capturado or "")[:16])))
    con.commit(); con.close()
    return {"persisted": True, "recognized": True, "reason": "VERIFICADO_POR_PROTOTIPO_M321 (TEST_PROTOTYPE_ISOLATED)", "authority_scope": "TEST_PROTOTYPE_M321", "db_path": db_path,
            "attestation": attestation[:32], "contract_decision": contract_ev.get("decision")}

def reconocer(db_path, result_id):
    """Verifica si un result_id está reconocido por el prototipo (no por DB_OP directo)."""
    if not os.path.isfile(db_path):
        return {"recognized": False, "reason": "DB_REGISTRY_NO_EXISTE"}
    con = sqlite3.connect(db_path)
    row = con.execute("SELECT * FROM m321_verified_registry WHERE result_id=?", (result_id,)).fetchone()
    if not row:
        return {"recognized": False, "reason": "NO_INGRESADO_EN_REGISTRO_PROTOTIPO; podría ser BYPASS_PROVEN en DB_OP (results/results_legacy)"}
    # Recomputar la atestación sobre los campos almacenados (detecta alteración)
    cols = ["result_id","artifact_hash","manifest_hash","evidence_ref","contract_decision",
            "auth_nonce","actor_label","timestamp_iso","attestation","provenance"]
    rec = dict(zip(cols, row))
    attestation = rec.get("attestation") or ""
    if not attestation.strip():
        return {"recognized": False, "reason": "ATTESTACION_AUSENTE: registro alterado o incompleto", "record": rec}
    uid_part = (rec.get("actor_label") or "").split("|")[0].replace("uid:", "") or "0"
    esperada = atestacion(_clave(), rec.get("evidence_ref"), rec.get("result_id"),
                           rec.get("artifact_hash"), rec.get("manifest_hash"),
                           uid_part, rec.get("timestamp_iso"))
    if not hmac.compare_digest(esperada, str(attestation)):
        return {"recognized": False, "reason": "ATTESTACION_INVALIDA: registro alterado (hash/manifest/actor/timestamp modificados)", "record": rec}
    if rec.get("contract_decision") != "VERIFIED":
        return {"recognized": False, "reason": "CONTRACT_DECISION_NOT_VERIFIED: %s" % rec.get("contract_decision"), "record": rec}
    # Recomprueba nonce único
    nonce = row[5] if len(row) > 5 else None
    if nonce:
        dup = con.execute("SELECT 1 FROM m321_nonces WHERE nonce=? AND result_id!=?", (nonce, result_id)).fetchone()
        if dup:
            return {"recognized": False, "reason": "REPLAY_DETECTADO: nonce reutilizado", "record": row}
    return {"recognized": True, "reason": "RECONOCIDO_POR_PROTOTIPO_M321_ATESTADO: contract=%s authority_scope=TEST_PROTOTYPE_M321" % rec.get("contract_decision"),
            "record": {"result_id": rec.get("result_id"), "contract_decision": rec.get("contract_decision"), "attestation": attestation[:32], "provenance": rec.get("provenance")}}

def bypass_detected(db_path, result_id):
    """Detecta si un result_id existe en DB_OP/directo con VERIFIED pero NO en registro prototipo."""
    # Solo para análisis; no modifica DB_OP
    return {"note": "DB_OP no se consulta directamente (solo lectura prohibida); análisis sobre DB_DISCARD y DB_REGISTRY solo.", "bypass_possible": True, "reason": "DB_OP results/results_legacy pueden contener VERIFIED sin registro m321"}
