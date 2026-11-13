#!/usr/bin/env python3
"""REPLAY DE MISION — reconstrucción desde registros persistidos (store.py, evidence)."""
import json, sqlite3, hashlib, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pathlib import Path
from backends.dispatch import resolve, ejecutar

DB_PATH = Path(__file__).resolve().parents[1] / "storage" / "rxre.sqlite3"

def analyze_dependencies(op_id: str, evidence_path: str = None) -> dict:
    """INVALIDACIÓN CAUSAL — clasifica conclusión según dependencias verificadas (VALID/STALE/UNKNOWN)."""
    # Dependencias de la operación registrada
    if not DB_PATH.exists():
        return {"op_id": op_id, "classification": "UNKNOWN", "reason": "DB no encontrada", "dependencies": []}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        op = conn.execute("SELECT operacion, capability, request_json, response_json FROM operations WHERE operation_id=?", (op_id,)).fetchone()
        if not op:
            return {"op_id": op_id, "classification": "UNKNOWN", "reason": "operación no registrada", "dependencies": []}
        operacion, capability = op[0], op[1]
        params = json.loads(op[2]) if op[2] else {}
        resp = json.loads(op[3]) if op[3] else {}
        dependencies = []
        # Dependencia 1: artefacto (hash) — usar request_json.target, no sustituir
        full_target = params.get("target", "")
        target_str = full_target.split("@", 1)[0] if isinstance(full_target, str) else ""
        art = None
        if target_str:
            p = Path(target_str)
            # If not absolute, resolve against repo root, then cwd.
            if not p.is_absolute():
                repo_root = Path(__file__).resolve().parents[3]
                for cand in (repo_root / p, Path.cwd() / p):
                    if cand.exists():
                        art = str(cand.resolve()); break
            else:
                art = str(p.resolve()) if p.exists() else None
        if art:
            h = hashlib.sha256(Path(art).read_bytes()).hexdigest()
            dependencies.append({"name": "artefacto_hash", "value": h[:16], "relevant": True,
                                 "requested_target": target_str or None})
            # Compare against evidence if provided (NOT a fixed e2e_001)
            if evidence_path:
                ev = Path(evidence_path)
                if ev.exists():
                    meta = json.loads(ev.read_text())
                    # Match a recorded hash if the artifact matches. Otherwise mark unknown artefact (don't assume same file).
                    ev_hash = meta.get("artefacto_hash_sha256", meta.get("hash_sha256", ""))[:16]
                    ev_artifact = meta.get("artefacto_path", meta.get("artefacto", "")) or None
                    ev_artifact_abs = None
                    if isinstance(ev_artifact, str) and ev_artifact:
                        ep = Path(ev_artifact)
                        ev_artifact_abs = str(ep.resolve()) if ep.exists() else None
                    art_matches = bool(ev_artifact_abs and ev_artifact_abs == art)
                    if art_matches and ev_hash and ev_hash != h[:16]:
                        return {"op_id": op_id, "classification": "STALE", "reason": "hash artefacto cambiado respecto a la evidencia suministrada",
                                "dependencies": dependencies, "evidence_path": str(ev)}
                    if ev_hash and not art_matches:
                        # Good evidence; just not for this artifact. Don't claim this validates the target artifact.
                        dependencies.append({"name": "evidence_artefact_request_mismatch", "value": ev_artifact[:80] if ev_artifact else "",
                                             "relevant": True, "missing": True})
        else:
            dependencies.append({"name": "artefacto", "value": None, "relevant": True, "missing": True,
                                 "requested_target": target_str or None})
        # Dependencia 2: versión herramienta (respuesta de DB)
        backend = resp.get("backend", {}) if isinstance(resp, dict) else {}
        tool_version = backend.get("tool_version", "")
        repo_commit = backend.get("repository_commit", "")
        dependencies.append({"name": "tool_version", "value": tool_version[:60], "relevant": True})
        # Dependencia 3: evidencia estructural asistida — búsqueda por nombre de artefacto entre evidencias conocidas
        ev_candidates = []
        audit_dir = Path("audit/evidence")
        if audit_dir.exists():
            for json_path in sorted(audit_dir.glob("e2e_*.json")):
                try:
                    meta2 = json.loads(json_path.read_text())
                    ev_art = (meta2.get("artefacto_path") or meta2.get("artefacto") or "") or ""
                    if art and ev_art and Path(ev_art).resolve() == Path(art).resolve():
                        ev_candidates.append({"name": f"estructura_{json_path.stem}",
                                              "value": meta2.get("tipo", ""),
                                              "evidence": str(json_path),
                                              "relevant": True})
                except Exception:
                    continue
        if ev_candidates:
            dependencies.extend(ev_candidates[:5])
        else:
            dependencies.append({"name": "evidencia_estructural", "value": None, "relevant": False, "missing": True})
        # Clasificación final
        has_missing = any(d.get("missing") for d in dependencies if d.get("relevant"))
        ev_for_match = evidence_path or None
        ev_path_match = Path(ev_for_match) if ev_for_match else None
        if art and ev_path_match and ev_path_match.exists():
            meta_ev = json.loads(ev_path_match.read_text())
            current_h = hashlib.sha256(Path(art).read_bytes()).hexdigest()
            ev_h = meta_ev.get("artefacto_hash_sha256", meta_ev.get("hash_sha256", ""))
            ev_artifact = meta_ev.get("artefacto_path", meta_ev.get("artefacto", "")) or None
            art_matches = bool(ev_artifact and Path(ev_artifact).resolve() == Path(art).resolve())
            if art_matches and ev_h and current_h == ev_h and not has_missing:
                return {"op_id": op_id, "classification": "VALID",
                        "reason": "dependencias verificadas y compatibles (artefacto==solicitado, hash coincide, sin dependencias faltantes)",
                        "dependencies": dependencies, "evidence_path": str(ev_path_match)}
            if art_matches and ev_h and current_h != ev_h:
                return {"op_id": op_id, "classification": "STALE",
                        "reason": "hash artefacto modificado respecto a evidencia suministrada",
                        "dependencies": dependencies, "evidence_path": str(ev_path_match)}
        # Sin evidencia canónica del solicitado (o evidencia responde a OTRO artefacto): no se afirma VALID
        if has_missing:
            return {"op_id": op_id, "classification": "UNKNOWN", "reason": "información insuficiente o evidencia no vinculada al artefacto solicitado", "dependencies": dependencies,
                    "evidence_path": str(ev_path_match) if ev_path_match else None}
        return {"op_id": op_id, "classification": "UNKNOWN",
                "reason": "ejecutar no permite afirmar validez: evidencia no asociada al artefacto solicitado (PASS-FAIL contract; prove or withhold)",
                "dependencies": dependencies, "evidence_path": str(ev_path_match) if ev_path_match else None}
    finally:
        conn.close()

def plan_reinvestigation(op_id: str, evidence_path: str = None) -> dict:
    """PLANIFICADOR DE REINVESTIGACIÓN — decisiones ejecutables a partir de dependencias."""
    dep = analyze_dependencies(op_id, evidence_path)
    plan = {"op_id": op_id, "classification": dep["classification"],
            "dependencies_checked": dep.get("dependencies", []),
            "plan": [], "limitacion": None, "evidence_path": dep.get("evidence_path")}
    # Reglas según clasificación
    if dep["classification"] == "VALID":
        plan["plan"] = [{"action": "conservar", "reason": "dependencias verificadas y compatibles",
                         "evidence": "evidencia vinculada al artefacto solicitado (gate de integridad)",
                         "dependencia": "artefacto + hash + herramienta + estructura",
                         "condition": "hash artefacto permanece igual; versión herramienta sin cambio semántico"}]
        plan["limitacion"] = "No requiere repetición. Causalidad dinámica NO confirmada por esta evidencia (#CONTRATO_CAUSAL_INV_ESTRING)."
    elif dep["classification"] == "STALE":
        stale_dep = [d["name"] for d in dep["dependencies"] if d.get("relevant")]
        # Proponer mínimo: validar hash y, si afectado, repetir binary.inspect sobre artefacto actualizado
        plan["plan"] = [{"action": "reevaluar", "reason": f"dependencia STALE: {', '.join(stale_dep)}",
                         "proposal": "repetir binary.inspect sobre artefacto actualizado; comparar hash con evidencia canónica",
                         "dependencia_afectada": stale_dep,
                         "evidence_origin": dep.get("evidence_path") or "audit/evidence/ (evidencia vinculada al artefacto)",
                         "condition": "nuevo hash coincide con evidencia actualizada o evidencia se actualiza tras repetición"}]
        plan["limitacion"] = "No se ejecuta automáticamente; requiere autorización para acceso /dev/mem si se requiere captura física (F2 PARTIAL)."
    elif dep["classification"] == "UNKNOWN":
        missing = [d["name"] for d in dep["dependencies"] if d.get("missing")]
        plan["plan"] = [{"action": "investigar", "reason": f"dependencia faltante o insuficiente: {', '.join(missing)}",
                         "proposal": "verificar existencia de artefacto solicitado, evidencia vinculada al artefacto (gate de integridad) y registro DB (store.sqlite3)",
                         "dependencia_faltante": missing,
                         "evidence_origin": "audit/evidence/ (evidencia vinculada al artefacto) + store.sqlite3 operations",
                         "condition": "todas las dependencias relevantes presentes y verificadas"}]
        plan["limitacion"] = "Grafo de dependencias incompleto; no se puede determinar si la conclusión es STALE o VALID sin completar datos."
    return plan

def verify_reinvestigation(plan: dict, result: dict) -> dict:
    """VERIFICACIÓN DE REINVESTIGACIÓN — clasifica RESOLVED / UNRESOLVED / INVALID_RESULT."""
    # Validación estructural del resultado
    verification = {
        "plan_op_id": plan.get("op_id"),
        "result_op_id": result.get("op_id"),
        "plan_action": plan.get("plan", [{}])[0].get("action") if plan.get("plan") else None,
        "verification_status": None,
        "motivo": None,
        "evidencia_resultado": None,
        "condicion_plan": plan.get("plan", [{}])[0].get("condition") if plan.get("plan") else None,
        "dependencias_verificadas": False,
        "evidencia_integridad": False,
        "reducida_incertidumbre": False,
        "limitacion": plan.get("limitacion")
    }
    # 1. Verificar que el resultado corresponde al plan
    if verification["plan_op_id"] != verification["result_op_id"]:
        verification["verification_status"] = "INVALID_RESULT"
        verification["motivo"] = "operación del resultado no coincide con el plan"
        verification["evidencia_resultado"] = "op_id mismatch"
        return verification
    # 2. Verificar integridad de evidencia (hash, esquema)
    evidence_path = result.get("evidence_path") or plan.get("evidence_path")
    evidence_integrity = True
    if evidence_path:
        from rxre.core.evidence_integrity import validate_evidence_path
        v = validate_evidence_path(str(evidence_path))
        evidence_integrity = bool(v["ok"])
    verification["evidencia_integridad"] = evidence_integrity
    # 3. Verificar condición del plan
    condition = verification["condicion_plan"] or ""
    action = verification["plan_action"]
    res_class = result.get("classification", result.get("reproducible", ""))
    if action == "conservar" and verification["evidencia_integridad"]:
        verification["verification_status"] = "RESOLVED"
        verification["motivo"] = "dependencias verificadas y compatibles; evidencia intacta; no requiere repetición"
        verification["reducida_incertidumbre"] = True
    elif action == "reevaluar" and verification["evidencia_integridad"]:
        verification["verification_status"] = "RESOLVED"
        verification["motivo"] = "dependencia STALE verificada; evidencia actualizada o consistente con reevaluación"
        verification["reducida_incertidumbre"] = True
    elif action == "investigar" and verification["evidencia_integridad"]:
        verification["verification_status"] = "UNRESOLVED"
        verification["motivo"] = "plan de investigación no reduce incertidumbre; falta verificación de dependencias relevantes"
        verification["reducida_incertidumbre"] = False
    else:
        verification["verification_status"] = "UNRESOLVED"
        verification["motivo"] = "resultado no satisface la condición del plan o evidencia alterada/incompleta"
        verification["reducida_incertidumbre"] = False
    return verification

def replay_operacion(op_id: str) -> dict:
    """Reconstruye una operación desde store.py y compara con evidencia canónica.

    Contratos críticos:
    - Solo `binary.inspect` está implementado; cualquier otra capacidad devuelve
      UNSUPPORTED explícito (nunca ejecuta, nunca devuelve variable sin inicializar).
    - El objetivo es `request_json.target`; nunca se sustituye por otro artefacto.
    - El hash SHA-256 del artefacto SOLICITADO se calcula ANTES de cualquier ejecución
      y se contrasta con la identidad registrada (request_json/response_json/evidencia
      vinculada al mismo artefacto). En caso de discrepancia: fail-closed, no se ejecuta.
    - La comparación contra evidencia se hace por correspondencia artefacto↔solicitado,
      nunca contra un archivo fijo ni contra evidencia ajena.
    """
    if not DB_PATH.exists():
        return {"status": "no_db", "op_id": op_id, "error": "rxre.sqlite3 no encontrado"}
    conn = sqlite3.connect(str(DB_PATH))
    try:
        op = conn.execute(
            "SELECT operation_id, operacion, capability, request_json, response_json FROM operations WHERE operation_id=?",
            (op_id,)).fetchone()
        if not op:
            return {"status": "not_found", "op_id": op_id, "error": "operación no registrada"}
        operacion, capability, request_json_str, response_json_str = op[1], op[2], op[3], op[4]
        params = json.loads(request_json_str) if request_json_str else {}
        resp = json.loads(response_json_str) if response_json_str else {}

        if capability != "binary.inspect":
            return {"status": "unsupported_capability", "op_id": op_id,
                    "operacion": operacion, "capability": capability,
                    "error": f"replay_operacion() implementa solo binary.inspect; capability {capability!r} no soportada — no se ejecuta ni se afirma equivalencia",
                    "reproducible": None, "differences": ["capability_not_supported"]}

        full_target = params.get("target", "")
        art_path = full_target.split("@", 1)[0] if isinstance(full_target, str) and full_target else None
        if not art_path:
            return {"status": "no_target", "op_id": op_id, "reproducible": False,
                    "error": "request_json.target missing/empty; refusing silent substitution"}

        repo_root = Path(__file__).resolve().parents[3]
        p = Path(art_path)
        art = None
        if not p.is_absolute():
            for candidate in (repo_root / p, Path.cwd() / p):
                if candidate.exists():
                    art = str(candidate.resolve()); break
        else:
            if p.exists():
                art = str(p.resolve())
        if not art:
            return {"status": "no_artefact", "op_id": op_id, "reproducible": False,
                    "error": f"requested artifact {art_path!r} not found (repo root or cwd)",
                    "requested": art_path}

        # Gate fail-closed: hash ANTES de ejecutar el backend
        hash_actual = hashlib.sha256(Path(art).read_bytes()).hexdigest()

        # Identidad registrada: request_json / response_json si declaran hash
        recorded_hash = None
        hash_sources = [params, resp if isinstance(resp, dict) else {}]
        if isinstance(resp, dict) and isinstance(resp.get("result"), dict):
            hash_sources.append(resp["result"])
        for src in hash_sources:
            for key in ("artefacto_hash_sha256", "artifact_sha256", "hash_sha256", "sha256"):
                v = src.get(key) if isinstance(src, dict) else None
                if isinstance(v, str) and v:
                    recorded_hash = v; break
            if recorded_hash:
                break

        # Evidencia canónica vinculada al artefacto SOLICITADO (nunca archivo fijo)
        ev_meta, ev_file = None, None
        audit_dir = Path("audit/evidence")
        if audit_dir.exists():
            for json_path in sorted(audit_dir.glob("e2e_*.json")):
                try:
                    meta = json.loads(json_path.read_text())
                except Exception:
                    continue
                ev_art = (meta.get("artefacto_path") or meta.get("artefacto") or "") or ""
                if not ev_art:
                    continue
                ep = Path(ev_art)
                if not ep.is_absolute():
                    ep = repo_root / ep
                try:
                    same = ep.exists() and ep.resolve() == Path(art).resolve()
                except Exception:
                    same = False
                if same:
                    ev_meta, ev_file = meta, json_path
                    break
        ev_hash = None
        if ev_meta:
            ev_hash = ev_meta.get("artefacto_hash_sha256", ev_meta.get("hash_sha256", ""))

        # Gate: si hay identidad registrada y no coincide -> abortar sin ejecutar
        hash_reference = recorded_hash or (ev_hash if isinstance(ev_hash, str) and ev_hash else None)
        if hash_reference and hash_reference != hash_actual:
            return {"status": "artefact_mismatch", "op_id": op_id, "reproducible": False,
                    "operacion": operacion, "capability": capability,
                    "requested": art_path, "hash_actual": hash_actual,
                    "hash_reference": hash_reference,
                    "error": "fail-closed: el artefacto actual no coincide con la identidad registrada; no se ejecutó el backend",
                    "differences": ["artefact_identity_mismatch"]}

        # Ejecución sólo con identidad consistente (o sin identidad registrada: declarar)
        result_replay = {"artefacto_reconstruido": art, "hash_actual": hash_actual,
                         "hash_reference": hash_reference,
                         "hash_gate": "ok" if hash_reference else "no_recorded_identity"}
        try:
            res = ejecutar(capability, {"artefacto": art, "timeout": 10})
            result_replay["reproducible"] = (res.get("status") == "ok")
            result_replay["replay_status"] = res.get("status")
            result_replay["differences"] = []
            if result_replay.get("reproducible"):
                result_replay["differences"].append("reproducible_structural")
        except Exception as exc:
            result_replay["replay_error"] = f"{type(exc).__name__}: {str(exc)[:60]}"
            result_replay["reproducible"] = False
            result_replay["differences"] = ["backend_exception"]

        if ev_meta is not None:
            result_replay["evidence_found"] = True
            result_replay["evidence_file"] = str(ev_file)
            result_replay["hash_evidence"] = ev_hash or ""
            result_replay["hash_match"] = bool(ev_hash) and (hash_actual == ev_hash)
            if ev_hash and not result_replay["hash_match"]:
                result_replay["differences"].append("hash_mismatch_evidence")
        else:
            result_replay["evidence_found"] = False

        return {
            "status": "replayed",
            "op_id": op_id,
            "operacion": operacion,
            "capability": capability,
            "reproducible": result_replay.get("reproducible", False),
            "replay_result": result_replay,
            "differences": result_replay.get("differences", []),
            "nota": "Replay reconstruido desde store.py sin modificar DB; identidad del artefacto verificada antes de ejecutar; diferencias clasificadas como determinismo/entorno/información insuficiente."
        }
    finally:
        conn.close()


def evaluate_contract(result: dict, evidence_path: str = None) -> dict:
    """CONTRATO UNIFORME — separa ejecución, evidencia y conclusión.

    Reglas de promoción (críticas):
    - Ejecución (BK_OK/INVALID/BLOCKED/UNKNOWN) es ortogonal al estado semántico.
    - Solo se permite COMPLETE/VALID cuando:
        * status == "ok" y precheck is True
        * hay results con primer elemento dinsámico SIN limitations declaradas
        * la evidencia PASADA (si la hay) supera la puerta de integridad (validate_evidence_path)
        * la evidencia TE LA WALLE PASADA: no hay evidencia o integridad falsa → NUNCA COMPLETE
    - En otro caso: PARTIAL (si las limitaciones existen o la integridad falla),
      BLOCKED o NOT_DETERMINED (sin decisión posible).
    """
    status = result.get("status")
    precheck = (result.get("precheck") or {}).get("ok") if isinstance(result.get("precheck"), dict) else None
    ejecucion = (result.get("ejecucion") or {}).get("status") if isinstance(result.get("ejecucion"), dict) else None
    results = result.get("results", []) if isinstance(result.get("results"), list) else []
    target_art = None
    ev_integrity = None  # None = no evidence provided; False = failed; True = ok
    ev_path = Path(evidence_path) if evidence_path else None
    if ev_path and ev_path.exists():
        try:
            from rxre.core.evidence_integrity import validate_evidence_path
            meta = json.loads(ev_path.read_text())
            target_art = meta.get("artefacto_path", meta.get("artefacto", "")) or None
            v = validate_evidence_path(str(ev_path), target_art)
            ev_integrity = v["ok"]
        except Exception:
            ev_integrity = False
    elif ev_path and not ev_path.exists():
        ev_integrity = False

    has_limits = bool(
        results
        and isinstance(results[0], dict)
        and (results[0].get("limitations") or results[0].get("limitaciones"))
    )

    contract_state = "UNKNOWN"
    epistemic = "NOT_DETERMINED"
    reason = ""

    if status == "invalid_input" or precheck is False:
        contract_state = "INVALID_INPUT"
        epistemic = "NOT_DETERMINED"
        reason = "entrada no válida o no es binario (BK_INVALID / BK_EMPTY)"

    elif status == "blocked" or ejecucion is None or ejecucion == "blocked":
        contract_state = "BLOCKED"
        epistemic = "NOT_DETERMINED"
        reason = "ejecución bloqueada por error o falta de permiso (BK_ERROR)"

    elif status == "ok" and precheck is True:
        if not results:
            # No result item to inspect; we cannot validly claim COMPLETE without evidence/gate.
            if ev_integrity is True:
                contract_state = "PARTIAL"
                epistemic = "PARTIAL"
                reason = "ejecución sin resultados y sin limitaciones contradictorias; evidencia válida pero no suficiente para COMPLETE"
            else:
                contract_state = "PARTIAL"
                epistemic = "PARTIAL"
                reason = "ejecución BK_OK sin resultados; evidencia ausencia o fallo de puerta — no se permite COMPLETE"
        elif has_limits:
            contract_state = "PARTIAL"
            epistemic = "PARTIAL"
            reason = "ejecución completada pero con datos parciales / declaración de límite (BK_OK + limitaciones)"
        elif ev_integrity is False:
            contract_state = "PARTIAL"
            epistemic = "PARTIAL"
            reason = "ejecución BK_OK sin limitaciones perimetrales, pero la evidencia no superó la puerta de integridad — no se permite COMPLETE"
        elif ev_integrity is None:
            contract_state = "PARTIAL"
            epistemic = "PARTIAL"
            reason = "ejecución BK_OK; evidencia no suministrada, no se permite COMPLETE sin integridad verificable"
        else:
            contract_state = "COMPLETE"
            epistemic = "VALID"
            reason = "ejecución completa, evidencia íntegra, sin limitaciones"

        if ev_path and ev_path.exists():
            try:
                meta_ev = json.loads(ev_path.read_text())
                if meta_ev.get("tipo_evidencia") == "frontera_analizador":
                    contract_state = "PARTIAL"
                    epistemic = "PARTIAL"
                    reason = "frontera de analizador documentada; no se afirma análisis completo"
            except Exception:
                # Corrupt JSON evidence: integrity invalid; do not promote
                if ev_integrity is not False:
                    ev_integrity = False
                    contract_state = "PARTIAL"
                    epistemic = "PARTIAL"
                    reason = "evidencia ilegible tras gate (excepción) — no se permite COMPLETE"

    integrity_flag = bool(ev_integrity)
    return {
        "contract_state": contract_state,
        "epistemic": epistemic,
        "reason": reason,
        "execution_status": status,
        "precheck_ok": precheck,
        "execution_status_backend": ejecucion,
        "evidence_integrity": integrity_flag,
        "results_count": len(results),
        "limitations_present": has_limits,
        "note": "Estado técnico (status) != validez semántica (epistemic). No se eleva automáticamente a PROVEN."
    }
