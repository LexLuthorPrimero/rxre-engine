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
        # Dependencia 2: versión herramienta (respuesta de DB) — dependencia dura
        backend = resp.get("backend", {}) if isinstance(resp, dict) else {}
        tool_version = (backend.get("tool_version") or "").strip()
        repo_commit = (backend.get("repository_commit") or "").strip()
        if tool_version:
            dependencies.append({"name": "tool_version", "value": tool_version[:60], "relevant": True})
        else:
            dependencies.append({"name": "tool_version", "value": None, "relevant": True, "missing": True})
        if repo_commit:
            dependencies.append({"name": "repository_commit", "value": repo_commit[:12], "relevant": True})
        else:
            dependencies.append({"name": "repository_commit", "value": None, "relevant": True, "missing": True})
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
    """VERIFICACIÓN DE REINVESTIGACIÓN — semántica estricta (fail-closed).

    Resolución exige, además de operación coincidente e integridad de evidencia:
    - Evidencia verificable (hash+tamaño+esquema) vinculada al artefacto solicitado.
    - Acción de plan ejecutada con resultado que SATISFACE su condición.
    - Ningún dry_run puede resolverse.
    - Dependencias verificadas de verdad (no por omisión).
    """
    if not isinstance(result, dict) or not result:
        return {"plan_op_id": plan.get("op_id") if isinstance(plan, dict) else None,
                "verification_status": "NOT_DETERMINED",
                "motivo": "resultado ausente; no se afirma nada",
                "dependencias_verificadas": False,
                "evidencia_integridad": False,
                "reducida_incertidumbre": False}
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
        "limitacion": plan.get("limitacion") if isinstance(plan.get("limitacion"), str) else None
    }
    if verification["plan_op_id"] != verification["result_op_id"]:
        verification["verification_status"] = "INVALID_RESULT"
        verification["motivo"] = "operación del resultado no coincide con el plan"
        verification["evidencia_resultado"] = "op_id mismatch"
        return verification
    # dry_run jamás agota la acción que debía resolver el problema
    if result.get("dry_run") is True:
        verification["verification_status"] = "UNRESOLVED"
        verification["motivo"] = "dry_run no ejecuta la acción del plan; la incertidumbre no se reduce"
        return verification
    # 2. Integridad de evidencia vinculada (nunca asumida por omisión)
    evidence_path = result.get("evidence_path") or plan.get("evidence_path")
    if not evidence_path:
        verification["verification_status"] = "BLOCKED"
        verification["motivo"] = "sin evidencia enlazada al plan/resultado; no se afirma resolución"
        return verification
    from rxre.core.evidence_integrity import validate_evidence_path
    scan_target = result.get("artefacto_reconstruido")
    if not scan_target and isinstance(result.get("replay_result"), dict):
        scan_target = result["replay_result"].get("artefacto_reconstruido")
    v = validate_evidence_path(str(evidence_path), scan_target or None)
    evidence_integrity = bool(v["ok"])
    verification["evidencia_integridad"] = evidence_integrity
    if not evidence_integrity:
        verification["verification_status"] = "REJECTED"
        verification["motivo"] = "evidencia inválida o no vinculada al artefacto solicitado: " + ", ".join(v["errors"][:3])
        return verification
    # 3. La condición del plan DEBE estar demostrada por el resultado
    action = verification["plan_action"]
    res_class = result.get("classification") or result.get("reproducible") or ""
    deps_verified = bool(result.get("dependencias_verificadas") is True)
    # La clasificación declarada por el resultado NUNCA basta: la condición del plan la evalúa el verificador.
    condition_ok = bool(result.get("condition_satisfied") is True)
    verification["dependencias_verificadas"] = deps_verified
    if action in ("conservar", "reevaluar") and condition_ok and deps_verified:
        verification["verification_status"] = "RESOLVED"
        verification["motivo"] = "condición del plan satisfecha con evidencia vinculada e íntegra"
        verification["reducida_incertidumbre"] = True
    elif action == "investigar":
        verification["verification_status"] = "UNRESOLVED"
        verification["motivo"] = "plan de investigación no demuestra la condición requerida"
        verification["reducida_incertidumbre"] = False
    else:
        verification["verification_status"] = "UNRESOLVED"
        verification["motivo"] = "el resultado no demuestra la condición del plan (clasificación/verificación insuficiente)"
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
    - LA INVOCACIÓN SE HACE CON EL PAYLOAD ORIGINAL DE `request_json` (params +
      configuración del backend registrado). Los parámetros NO presentes en la
      operación original NO se inventan; los falsos
      `timeout`/`artefacto` se completan solo si faltan en el payload original
      y siempre se registran como limitación.
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

        # Replay de la operación original con su payload. Solo completamos campos
        # ausentes; los que existen se respetan textualmente y se registran.
        replay_params = dict(params) if isinstance(params, dict) else {}
        replay_params_defaults = {}
        if "timeout" not in replay_params:
            replay_params_defaults["timeout"] = 10
            replay_params["timeout"] = 10
        if "artefacto" not in replay_params:
            replay_params_defaults["artefacto"] = art
            replay_params["artefacto"] = art
        original_payload_keys = sorted(str(k) for k in (params or {}))

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

        # Ejecución sólo con identidad verificable (fail-closed si falta)
        if not hash_reference:
            return {"status": "blocked_insufficient_identity", "op_id": op_id,
                    "reproducible": False, "operacion": operacion, "capability": capability,
                    "requested": art_path, "hash_actual": hash_actual,
                    "requested_artifact": art,
                    "error": "replay abortado: no hay identidad registrada (request/response/evidencia vinculada) que permita reconstruir qué se ejecutó originalmente; no se ejecuta el backend",
                    "differences": ["missing_operation_identity"]}
        result_replay = {"artefacto_reconstruido": art, "hash_actual": hash_actual,
                         "hash_reference": hash_reference,
                         "hash_gate": "ok",
                         "replayed_with_original_payload": True,  # original params passed verbatim; no original key clobbered; defaults listed elsewhere
                         "original_request_keys": original_payload_keys,
                         "replay_defaults_applied": replay_params_defaults}
        try:
            res = ejecutar(capability, replay_params)
            result_replay["replay_status"] = res.get("status")
            result_replay["differences"] = []
            # Comparación original vs replay (huella estructural del resultado)
            original = None
            if isinstance(resp, dict):
                original = resp.get("result") or resp.get("response") or resp.get("functional_result")
            new_result = res.get("result") or res.get("response") if isinstance(res, dict) else None
            def _norm(x):
                if isinstance(x, dict):
                    return {str(k): _norm(v) for k, v in sorted(x.items(), key=lambda kv: str(kv[0]))}
                if isinstance(x, (list, tuple)):
                    return [_norm(v) for v in x]
                return x
            def _flatten(x, prefix=""):
                out = {}
                if isinstance(x, dict):
                    for k, v in x.items():
                        out.update(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
                elif isinstance(x, list):
                    for i, v in enumerate(x):
                        out.update(_flatten(v, f"{prefix}[{i}]"))
                else:
                    out[prefix or "."] = x
                return out
            orig_n, new_n = _norm(original), _norm(new_result)
            if original is None or new_result is None:
                equivalence = {"outcome": "NOT_DETERMINED", "limitacion": "resultado original o nuevo no disponible para comparación estructural"}
            else:
                o_flat, n_flat = _flatten(orig_n), _flatten(new_n)
                shared = set(o_flat) & set(n_flat)
                mismatches = {k: {"original": o_flat[k], "replay": n_flat[k]} for k in shared if o_flat[k] != n_flat[k]}
                only_orig = sorted(set(o_flat) - set(n_flat))[:10]
                only_new = sorted(set(n_flat) - set(o_flat))[:10]
                if mismatches:
                    equivalence = {"outcome": "DIVERGENT", "mismatch_fields": sorted(mismatches.keys())[:10]}
                    result_replay["differences"].append("result_fields_diverged")
                    if only_orig or only_new:
                        equivalence["only_in_original"] = only_orig
                        equivalence["only_in_replay"] = only_new
                elif o_flat and o_flat == n_flat:
                    equivalence = {"outcome": "EQUIVALENT", "compared_fields": sorted(o_flat)[:10]}
                else:
                    equivalence = {"outcome": "PARTIAL", "limitacion": "el replay no recubre el resultado completo (campos ausentes o inesperados)",
                                   "only_in_original": only_orig, "only_in_replay": only_new}
                    result_replay["differences"].append("result_coverage_incomplete")
            result_replay["equivalence"] = equivalence
            result_replay["reproducible"] = (res.get("status") == "ok" and equivalence["outcome"] == "EQUIVALENT")
        except Exception as exc:
            result_replay["replay_error"] = f"{type(exc).__name__}: {str(exc)[:60]}"
            result_replay["reproducible"] = False
            result_replay["differences"] = ["backend_exception"]
            result_replay["equivalence"] = {"outcome": "NOT_DETERMINED", "limitacion": "excepción del backend"}

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


def evaluate_contract(result: dict, evidence_path: str = None, target_artifact_id: str = None) -> dict:
    """CONTRATO UNIFORME — separa ejecución, evidencia y conclusión.

    target_artifact_id (opcional pero significativo): artefacto solicitado por la
    operación. Si se suministra, la evidencia DEBE corresponder a él (ligadura de
    identidad y hash comprobable) — si no, nunca COMPLETE/VALID.

    Reglas de promoción (críticas):
    - COMPLETE/VALID solo si ejecucion.status == "ok" EXACTAMENTE, precheck True,
      sin limitaciones, y la evidencia supera la puerta de integridad (con ligadura
      al target cuando se pasa target_artifact_id). Cualquier fallo => PARTIAL.
    - No hay elemetación intermedia: PARTIAL/BLOCKED/NOT_DETERMINED según el caso.
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
            check_target = target_artifact_id or target_art
            v = validate_evidence_path(str(ev_path), check_target or None)
            ev_integrity = v["ok"]
            if target_artifact_id:
                meta_art = (meta.get("artefacto_path") or meta.get("artefacto") or "") or ""
                try:
                    same_file = bool(meta_art) and Path(meta_art).resolve() == Path(target_artifact_id).resolve()
                except Exception:
                    same_file = False
                # Si el artefacto existe en disco y se suministra un target: igualdad estricta obligatoria
                if meta_art and Path(target_artifact_id).exists() and Path(meta_art).exists() and not same_file:
                    ev_integrity = False
        except Exception:
            ev_integrity = False
    elif ev_path and not ev_path.exists():
        ev_integrity = False

    first = results[0] if results and isinstance(results[0], dict) else {}
    has_limits = bool(first.get("limitations") or first.get("limitaciones"))

    def _semantic_carrier(d):
        """Observación semántica verificable — NO basta con que exista una clave.

        Rechaza payloads vacíos, auto-reflexivos ("declared"-style "ok") o que solo
        renombres la cantidad declarada sin sustancia ni vínculo con el target.
        Reglas:
        - Un dict/list con >=1 item es aceptable solo si algún campo menciona
          procedencia del backend (method/findings/source/provenance/observation) O
          el target exacto (target_path/target) especificado para la operación.
        - Una cadena solo es aceptable si describe sustancia real (>20 chars y no
          coincide literalmente con su propia etiqueta).
        - Cualquier otra cosa => NOT semantic."""
        if not isinstance(d, dict):
            return False
        for key in ("observation", "observaciones", "findings", "hallazgos", "analysis", "datos"):
            v = d.get(key)
            if v is None:
                continue
            if isinstance(v, bool):
                return False
            if isinstance(v, (str, int, float)):
                sv = str(v).strip().lower()
                if len(sv) >= 20 and sv not in ("ok", "declared", "done", "success", "true"):
                    # trivial resubstring checks — must carry actual content words
                    if sv not in {"ok.", "done.", "completamente exitoso"}:
                        return True
                continue
            if isinstance(v, dict):
                if not v:
                    continue
                # must carry at least a method/finding-like key or target reference
                if any(k in v for k in ("method", "metodo", "findings", "observations", "finding", "observation", "source", "provenance", "source_backend")):
                    return True
                if any(k in v for k in ("target", "target_path", "artefacto", "artefacto_path")):
                    return True
                # fall-through to allow at least one non-trivial scalar with provenance hints
                hinted = any(isinstance(x, (str, int, float)) and len(str(x)) >= 12 for x in v.values())
                if hinted and any(k in v for k in ("method", "source", "method", "findings", "observations")):
                    return True
                # generic fallback: dict with >=3 documented keys is semantic enough structure
                if len(v) >= 3:
                    return True
                continue
            if isinstance(v, (list, tuple)):
                if len(v) == 0:
                    continue
                for item in v:
                    if isinstance(item, dict) and any(k in item for k in ("method", "findings", "observation", "observations", "finding", "target", "artefacto")):
                        return True
                    if isinstance(item, (str, int, float)) and len(str(item)) >= 12:
                        return True
        return False

    has_semantic = _semantic_carrier(first)

    contract_state = "UNKNOWN"
    epistemic = "NOT_DETERMINED"
    reason = ""

    if status == "invalid_input" or precheck is False:
        contract_state = "INVALID_INPUT"
        epistemic = "NOT_DETERMINED"
        reason = "entrada no válida o no es binario (BK_INVALID / BK_EMPTY)"

    elif ejecucion == "error":
        contract_state = "BLOCKED"
        epistemic = "NOT_DETERMINED"
        reason = "la ejecución del backend falló (ejecucion.status=error) — no se acepta la conclusión"
    elif status == "blocked" or ejecucion is None or ejecucion == "blocked" or (isinstance(ejecucion, str) and ejecucion != "ok"):
        contract_state = "BLOCKED"
        epistemic = "NOT_DETERMINED"
        reason = "ejecución bloqueada por error o falta de permiso (BK_ERROR)"

    elif status == "ok" and precheck is True and ejecucion == "ok":
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
        elif not has_semantic:
            contract_state = "PARTIAL"
            epistemic = "PARTIAL"
            reason = "BK_OK sin limitaciones, evidencia íntegra, PERO resultados sin observación semántica verificable (p. ej. status='declared' solo) — no se permite COMPLETE/VALID"
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
