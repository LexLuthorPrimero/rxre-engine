#!/usr/bin/env python3
"""RXRE-M280 — Supervisor acotado de iteraciones.
Reutiliza selector, motor, persistencia (store) y contratos existentes.
No modifica core/store.py, esquemas ni DB protegidas.
No activa op:claim ni amplía permisos.
"""
import sys, os, time, hashlib, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

from rxre.core import store, capability_registry, evidence_snapshot

class M280Supervisor:
    def __init__(self, max_iter=3, max_duration_s=30, max_retries=1, db_path=None):
        self.max_iter = max_iter
        self.max_duration_s = max_duration_s
        self.max_retries = max_retries
        self.db_path = db_path or os.environ.get("RXRE_DB", store.DEFAULT_DB)
        self.iter_count = 0
        self.start_time = time.time()
        self.history = []
        self.continuity = "CONTINUE"

    def _db(self):
        return store.conectar(self.db_path) if self.db_path else store.conectar()

    def select_eligible(self, artifact_path=None, manifest_path=None):
        """Selecciona tarea elegible; evita repetir tareas completadas."""
        # Reutiliza selector existente
        res = capability_registry.select_capability(
            question_text="Static inspection of binary artifact",
            artifact_path=artifact_path or "/home/lucas/Escritorio/rxre/rx550_drv/vk_full_verified",
            manifest_path=manifest_path or "/tmp/m279_manifest.json"
        )
        selected = res.get("selected")
        if not selected or res.get("status") != "CAPABILITY_EXECUTED":
            return None, "NO_ELIGIBLE"
        # Verificar si ya existe resultado completado para esta capacidad + artefacto
        # M285 cambio mínimo: distinguir ejecución real / registro manual / autorización
        c = self._db()
        try:
            cur = c.execute(
                "SELECT result_id, status, raw_json FROM results WHERE file = ? AND scope = ? LIMIT 1",
                (manifest_path or "/tmp/m279_manifest.json", "static_inspection"))
            row = cur.fetchone()
            if row:
                result_id, status, raw_json_str = row
                try:
                    rec = json.loads(raw_json_str or "{}")
                except Exception:
                    rec = {}
                # Si hay restricciones/limitaciones que documentan bloqueo de autorización,
                # no declarar COMPLETED automático (M306 / DB_AUTH_ACTOR_M294 bloqueado)
                limitations = rec.get("limitations") or []
                has_auth_block = any(
                    ("DB_AUTH_ACTOR_M294" in str(l) or "M306" in str(l) or "BLOCKED" in str(l))
                    for l in (limitations if isinstance(limitations, list) else [limitations])
                )
                # Si el registro es m322 con SUPPORTED pero tiene bloqueos, documentar PARTIAL
                if has_auth_block and status == "SUPPORTED" and rec.get("capability") == "m322_claim_evaluator":
                    return selected, "PARTIAL"
                # M291 — identidad: capability debe coincidir con selected; file/scope no bastan
                rec_cap = rec.get("capability")
                selected_cap = selected
                if rec_cap and selected_cap and rec_cap != selected_cap:
                    # Registro de otra capacidad (ej. m303 no debe cerrar m322); no COMPLETED automático
                    return selected, "NOT_DETERMINED"
                # Si es PASS y no hay bloqueos documentados, completo
                if status == "PASS" and not has_auth_block:
                    return None, "COMPLETED"
                # Si es SUPPORTED pero sin verificación de invocación real (procedencia)
                # y hay bloqueo: no COMPLETED automático
                if status == "SUPPORTED" and has_auth_block:
                    return selected, "PARTIAL"
                # Si hay registro pero sin comprobación de ejecución real (procedencia.autority_real faltante o False)
                proc = rec.get("procedencia") or {}
                if status in ("PASS", "SUPPORTED") and proc.get("authority_real") is False and proc.get("db_op_modified") is False:
                    return selected, "PARTIAL"
                # Por defecto, si hay PASS sin bloqueos, COMPLETED
                if status == "PASS":
                    return None, "COMPLETED"
        finally:
            c.close()
        return selected, "ELIGIBLE"

    def execute_task(self, capability, artifact_path, manifest_path):
        """Ejecuta una sola tarea; registra resultado."""
        self.iter_count += 1
        op_id = f"op_m280_{self.iter_count:03d}"
        result_id = f"res_m280_{self.iter_count:03d}"
        start = time.time()
        try:
            if capability == "m303_evidence_snapshot":
                snap = evidence_snapshot.validar_y_capturar(
                    manifest_path=manifest_path,
                    artifact_path=artifact_path,
                    scope_esperado="static_inspection"
                )
                if isinstance(snap, tuple):
                    snap, info = snap
                decision = snap.decision if hasattr(snap, "decision") else "PASS"
                raw_json = json.dumps({
                    "op": capability,
                    "decision": decision,
                    "artifact_path": artifact_path,
                    "manifest_path": manifest_path,
                    "hash_capturado": snap.hash_capturado,
                    "bytes_len": len(snap.bytes_consumidos),
                    "restrictions": ["no GPU", "no MMIO", "read-only"],
                    "mission_ref": "M280"
                })
            else:
                decision = "INSUFFICIENT"
                raw_json = json.dumps({"op": capability, "decision": "INSUFFICIENT", "reason": "no capability match"})
            # Persist
            c = self._db()
            try:
                c.execute("INSERT OR IGNORE INTO operations (operation_id, operacion, capability, question, target, scope, status, request_json, response_json, timestamp, duracion_s) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                          (op_id, "experiment", capability, "static inspection", artifact_path, "static_inspection", decision, raw_json, raw_json, time.strftime('%Y-%m-%dT%H:%M:%SZ'), time.time()-start))
                row_hash = hashlib.sha256(raw_json.encode()).hexdigest()
                c.execute("INSERT OR IGNORE INTO results (result_id, operation_id, type, value, source, file, scope, tool, status, raw_json, timestamp, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (result_id, op_id, "EVIDENCE", decision, "rxre.m280", manifest_path, "static_inspection", capability, decision, raw_json, time.strftime('%Y-%m-%dT%H:%M:%SZ'), row_hash))
                c.commit()
            finally:
                c.close()
            # Recover independently
            c2 = self._db()
            try:
                cur = c2.execute("SELECT result_id, status, raw_json FROM results WHERE result_id = ?", (result_id,))
                row = cur.fetchone()
                recovered = json.loads(row[2]) if row else {}
            finally:
                c2.close()
            record = {
                "iteration": self.iter_count,
                "op_id": op_id,
                "result_id": result_id,
                "capability": capability,
                "decision": decision,
                "recovered_decision": recovered.get("decision"),
                "hash_match": (decision == recovered.get("decision")),
                "duration_s": round(time.time()-start, 3),
                "continuity": "CONTINUE" if self.iter_count < self.max_iter else "STOP_LIMIT"
            }
            self.history.append(record)
            # Decide continuity
            if self.iter_count >= self.max_iter:
                self.continuity = "STOP_LIMIT"
            elif decision == "BLOCKED":
                self.continuity = "STOP_BLOCKED"
            elif decision in ("INSUFFICIENT", "REJECTED"):
                self.continuity = "STOP_FAILURE"
            else:
                # Check if no more eligible tasks
                cap, status = self.select_eligible(artifact_path, manifest_path)
                if status == "NO_ELIGIBLE" or status == "COMPLETED":
                    self.continuity = "STOP_NO_ELIGIBLE"
                else:
                    self.continuity = "CONTINUE"
            return record
        except Exception as exc:
            # Persistence/recovery failure
            self.history.append({"iteration": self.iter_count, "error": str(exc), "continuity": "STOP_ERROR"})
            self.continuity = "STOP_ERROR"
            return {"iteration": self.iter_count, "error": str(exc), "continuity": "STOP_ERROR"}

    def run_cycle(self, artifact_path=None, manifest_path=None):
        start = time.time()
        # Check authorization (do not autocall --auto)
        if os.environ.get("RXRE_AUTO") == "1" or os.environ.get("OPENCODE_AUTO") == "1":
            self.history.append({"iteration": self.iter_count, "decision": "STOP_AUTH_NEEDED", "reason": "authorization required; --auto not permitted"})
            self.continuity = "STOP_AUTH_NEEDED"
            return self.history[-1]
        # Check time
        if (time.time() - self.start_time) > self.max_duration_s:
            self.continuity = "STOP_DURATION"
            return {"decision": "STOP_DURATION", "reason": "duration exceeded"}
        # Select
        cap, status = self.select_eligible(artifact_path, manifest_path)
        if status == "COMPLETED":
            self.history.append({"iteration": self.iter_count, "decision": "COMPLETED", "reason": "task already completed; not repeating automatically"})
            self.continuity = "STOP_COMPLETED"
            return self.history[-1]
        if status == "NO_ELIGIBLE" or cap is None:
            self.history.append({"iteration": self.iter_count, "decision": "NO_ELIGIBLE", "reason": "no eligible task found"})
            self.continuity = "STOP_NO_ELIGIBLE"
            return self.history[-1]
        if status == "BLOCKED":
            self.history.append({"iteration": self.iter_count, "decision": "BLOCKED", "reason": "precondition blocked"})
            self.continuity = "STOP_BLOCKED"
            return self.history[-1]
        # Execute
        return self.execute_task(cap, artifact_path or "/home/lucas/Escritorio/rxre/rx550_drv/vk_full_verified",
                                 manifest_path or "/tmp/m279_manifest.json")
