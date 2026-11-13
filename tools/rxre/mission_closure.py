#!/usr/bin/env python3
"""RXRE-200 — Contrato operativo de criterios y cierre de misión.

Vertical slice mínimo, compatible con store.py existente, sin modificar
zonas protegidas. Usa conectar() para DB operativa o temporal.

Contrato:
- Un criterio debe existir para intentar cierre.
- Requerido (required=1) + epistemic=PROVEN debe pasar verificación.
- Evidencia debe ser PROVEN con procedencia verificable (provenance no vacío).
- PARTIAL / NOT_DETERMINED rechazan cierre automático.
- Idempotente a nivel DB (WHERE status='PENDING') y audit.
- No escribe estados históricos.
- Registra en audit_log la decisión.
"""
from __future__ import annotations
import sqlite3, json, os, sys, time
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store as S
import hashlib as _hashlib
try:
    from rxre.verifier import promotion as _authority  # noqa: E402
except Exception:  # fail-closed: sin autoridad -> cierre terminante bloqueado
    _authority = None
DB = os.environ.get("RXRE_DB")



def _parse_evidence_ids(raw) -> list:
    """Normaliza `mission_criteria.evidence_ids`.

    Acepta: lista ya parseada, JSON de lista, o JSON doble-codificado
    (valor historico posible si alguien hizo json.dumps() sobre el JSON).
    Devuelve siempre una lista de identificadores; nunca un string.
    """
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        ids = list(raw)
    else:
        try:
            ids = json.loads(raw)
        except Exception:
            return []
        if isinstance(ids, str):
            try:
                ids = json.loads(ids)
            except Exception:
                return []
    if not isinstance(ids, list):
        return []
    return [str(x) for x in ids]


def _check_evidence_provenance(c: sqlite3.Connection, evidence_ids_json: str) -> bool:
    ids = _parse_evidence_ids(evidence_ids_json)
    if not ids:
        return False
    for fid in ids:
        row = c.execute(
            "SELECT epistemic, provenance FROM findings WHERE finding_id=?", (fid,)
        ).fetchone()
        if row is None:
            return False
        epistemic, provenance = row
        if epistemic != "PROVEN":
            return False
        try:
            prov = json.loads(provenance or "{}")
            if not prov or not isinstance(prov, dict) or not any(prov.get(k) for k in ("producer", "tool", "command", "device", "repository")):
                return False
        except Exception:
            return False
    return True


def close_mission(mission_id: str, db_path: str = None, conn=None,
                  verification_result: dict = None,
                  investigation_id: str = "",
                  artifact_sha256: str = "",
                  target_file: str = "",
                  domain: str = "") -> dict:
    """Cierra una mision si sus criterios obligatorios se cumplen.

    `conn`: conexion ya abierta (uso desde el flujo operativo de machine.py).
             Si se pasa, no se cierra (la cierra quien la abrio).
    """
    c_externa = conn is not None
    c = conn if c_externa else S.conectar(db_path or DB)
    try:
        # 1. Misión debe existir
        mission = S.obtener_mision(c, mission_id)
        if mission is None:
            return {"status": "REJECTED", "mission_id": mission_id,
                    "reason": "Mission not found", "idempotent": False, "audit": False}

        # Idempotencia: ya COMPLETED -> no alterar, devolver justificación existente
        if mission["status"] == "COMPLETED":
            audit_row = c.execute(
                "SELECT details FROM audit_log WHERE action='mission_closed' AND entity_id=? ORDER BY created_at DESC LIMIT 1",
                (mission_id,)
            ).fetchone()
            return {"status": "ALREADY_COMPLETED", "mission_id": mission_id,
                    "reason": "Mission already completed; no duplicate transition",
                    "audit_exists": audit_row is not None,
                    "audit_details": audit_row[0] if audit_row else None,
                    "idempotent": True}

        # --- Autoridad epistemológica central (R7/R3) ---
        _sha = artifact_sha256 or investigation_id or ""
        if not _sha:
            _sha = _hashlib.sha256(mission_id.encode()).hexdigest()
        if verification_result is not None and _authority is not None:
            try:
                _vr = verification_result if isinstance(verification_result, dict) else vars(verification_result)
                _rec = _authority.register_dictamen(
                    _vr, investigation_id=investigation_id or mission_id,
                    artifact_sha256=_sha, target_file=target_file or "comp.spv",
                    domain=domain or "unspecified")
                _authority.attach_verification_result(_rec, _vr)
            except Exception:
                pass
        _auth_m = None
        if _authority is not None:
            try:
                _auth_m = _authority.authorize_and_consume(
                    investigation_id=investigation_id or mission_id,
                    artifact_sha256=_sha,
                    target_file=target_file or "comp.spv",
                    domain=domain or "",
                    consumer="R3",
                    operation_id=f"R3_{mission_id}_close",
                    action="close_mission",
                    idempotent=True)
            except Exception:
                _auth_m = None
        AUTHORIZED = bool(_auth_m and (_auth_m.get("record") or {}).get("accepted"))
        if not AUTHORIZED:
            return {"status": "PENDING_VERDICT", "mission_id": mission_id,
                    "reason": "cierre administrativo bloqueado: autoridad epistemologica no autoriza la promocion (falta dictamen vinculado o consumo rechazado); no se declara COMPLETED",
                    "idempotent": False, "audit": False,
                    "gate": {"dictamen_id": ((_auth_m or {}).get("record") or {}).get("dictamen_id"),
                              "decision": ((_auth_m or {}).get("record") or {}).get("decision"),
                              "consumption_id": (_auth_m or {}).get("consumption_id")}}

        # 2. Debe haber criterios (contrato: criterio ausente != satisfecho)
        criterios = S.obtener_criterios_mision(c, mission_id)
        if not criterios:
            return {"status": "REJECTED", "mission_id": mission_id,
                    "reason": "No criteria defined (absent criterion != satisfied)",
                    "idempotent": False, "audit": False}

        # 3. Verificación de criterios existentes (reutiliza lógica actual)
        verif = S.verificar_criterios_mision(c, mission_id)

        # 4. Requisito: todos los criterios required=1 con epistemic=PROVEN deben pasar
        required_criteria = [cr for cr in criterios if cr.get("required") == 1]
        # Solo los criteria requeridos que son PROVEN deben ser PASS; los demás se ignoran para cierre automático
        required_proven = [cr for cr in required_criteria if cr.get("epistemic") == "PROVEN"]
        if not required_proven:
            # Si no hay criterios PROVEN requeridos, no autorizamos cierre automático (diseño defensivo)
            return {"status": "REJECTED", "mission_id": mission_id,
                    "reason": "No required PROVEN criterion defined for automatic close",
                    "idempotent": False, "audit": False}

        # Mapear resultados por criterion_id (verificar_criterios_mision mantiene orden)
        resultados = verif.get("resultados", [])
        # Assumes same order; build dict by index
        resultado_by_crit = {}
        for idx, cr in enumerate(criterios):
            if idx < len(resultados):
                resultado_by_crit[cr["criterion_id"]] = resultados[idx]

        failures = []
        for cr in required_criteria:
            cid = cr["criterion_id"]
            res = resultado_by_crit.get(cid)
            if res is None or res.get("status") != "PASS":
                failures.append({"criterion_id": cid,
                                 "status": res.get("status") if res else "MISSING",
                                 "epistemic": cr.get("epistemic"),
                                 "reason": res.get("reason") if res else "No verification result"})
                continue
            # 5. Procedencia verificable para evidencia del criterio que pasó
            evidence_ids = _parse_evidence_ids(cr.get("evidence_ids"))
            if not evidence_ids:
                failures.append({"criterion_id": cid, "status": "FAIL",
                                 "reason": "Criterion passed without linked evidence"})
            elif not _check_evidence_provenance(c, cr.get("evidence_ids")):
                failures.append({"criterion_id": cid, "status": "FAIL",
                                 "reason": "Evidence provenance invalid or missing"})

        if failures:
            return {"status": "REJECTED", "mission_id": mission_id,
                    "reason": "Required criteria not satisfied or evidence provenance invalid",
                    "failures": failures,
                    "idempotent": False, "audit": False}

        # Defensive: at least one required PROVEN criterion must exist
        if not any(cr.get("epistemic") == "PROVEN" for cr in required_criteria):
            return {"status": "REJECTED", "mission_id": mission_id,
                    "reason": "No required PROVEN criterion defined for automatic close",
                    "idempotent": False, "audit": False}

        # 6. Transición atómica (idempotente a nivel DB: solo si PENDING)
        # En conexion externa usamos SAVEPOINT: un fallo no debe descartar
        # otras escrituras pendientes del mismo flujo operativo.
        sp = "rxre_close_sp"
        if c_externa:
            c.execute("SAVEPOINT " + sp)
        try:
            cur = c.execute(
                "UPDATE missions SET status='COMPLETED', completed_at=datetime('now') WHERE mission_id=? AND status='PENDING'",
                (mission_id,)
            )
            if cur.rowcount == 0:
                # Ya estaba COMPLETED (race) o no PENDING; regresar ALREADY_COMPLETED sin duplicar audit
                if c_externa:
                    c.execute("ROLLBACK TO " + sp)
                    c.execute("RELEASE " + sp)
                else:
                    c.rollback()
                return {"status": "ALREADY_COMPLETED", "mission_id": mission_id,
                        "reason": "Mission already completed (race or concurrent)",
                        "idempotent": True, "audit": False}

            # 7. Registro auditable de la decisión (mecanismo existente audit_log)
            justification = {
                "close_type": "automatic_criteria_satisfied",
                "required_criteria_verified": len(required_criteria),
                "evidence_provenance_checked": True,
                "criteria_status": {cr["criterion_id"]: "PASS" for cr in required_criteria},
                "verificacion_resultados": verif.get("resultados", [])
            }
            c.execute(
                "INSERT INTO audit_log (action, entity_type, entity_id, actor, details, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("mission_closed", "mission", mission_id, "system", json.dumps(justification))
            )
            c.commit()
            if c_externa:
                c.execute("RELEASE " + sp)
        except sqlite3.Error as exc:
            # Atomicidad: si el registro auditable falla, la transición tampoco se persiste
            if c_externa:
                c.execute("ROLLBACK TO " + sp)
                c.execute("RELEASE " + sp)
            else:
                c.rollback()
            return {"status": "ERROR", "mission_id": mission_id,
                    "reason": f"Transition aborted, no terminal state persisted: {exc}",
                    "idempotent": False, "audit": False}

        return {"status": "COMPLETED", "mission_id": mission_id,
                "reason": "All required criteria satisfied with verifiable provenance",
                "justification": justification,
                "idempotent": True, "audit": True}
    finally:
        if not c_externa:
            c.close()
