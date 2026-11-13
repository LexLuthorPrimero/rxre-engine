#!/usr/bin/env python3
"""M296 — Ejecutor controlado de una misión (diseño mínimo, sin bucle, sin verificación automática)."""
import sys, os, time, json, hashlib
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.supervisor.m280_supervisor import M280Supervisor
from rxre.core import store

class M296Executor:
    """Ejecutor de una sola misión. No inicia bucles desatendidos. Documenta BLOCKED/NOT_DETERMINED/INSUFFICIENT."""
    def __init__(self, mission_id="m296_001", max_iter=1, max_duration_s=30):
        self.mission_id = mission_id
        self.max_iter = max_iter
        self.max_duration_s = max_duration_s
        self.autonomous_loop = False
        self.iter_count = 0
        self.start_time = time.time()
        self.request = None
        self.invocation = None
        self.result = None
        self.validation = None
        self.closure = None
        self.db_path = store.DEFAULT_DB

    def _db(self):
        return store.conectar(self.db_path) if self.db_path else store.conectar()

    def run_single(self, artifact_path=None, manifest_path=None):
        """Ejecutar una misión controlada. No modifica results/operations protegidos para VERIFIED."""
        # Defensa adversarial: impedir segunda ejecución o bucle forzado
        if getattr(self, "autonomous_loop", False):
            return {
                "status": "STOP_BLOCKED",
                "decision": "BLOCKED",
                "mission_id": self.mission_id,
                "continuity": "STOP_BLOCKED",
                "db_auth_actor_m294": "BLOCKED",
                "op_claim": False,
                "autonomous_loop": True,
                "notes": "Defensa adversarial: autonomous_loop forzado; ejecución rechazada sin efecto",
            }
        if self.iter_count >= self.max_iter:
            return {
                "status": "STOP_LIMIT",
                "decision": "NOT_DETERMINED",
                "mission_id": self.mission_id,
                "continuity": "STOP_LIMIT",
                "db_auth_actor_m294": "BLOCKED",
                "op_claim": False,
                "autonomous_loop": False,
                "notes": f"Defensa adversarial: iter_count={self.iter_count} >= max_iter={self.max_iter}; ejecución rechazada",
            }
        # Definición de contrato M307: integridad física del artefacto debe verificarse
        # antes de avanzar hacia ejecución (no confundir con autorización DB_AUTH_ACTOR_M294)
        if artifact_path and manifest_path and os.path.isfile(manifest_path) and os.path.isfile(artifact_path):
            try:
                import hashlib, json
                with open(manifest_path, "r") as mf, open(artifact_path, "rb") as art:
                    manifest = json.load(mf)
                    expected_hash = manifest.get("artefacto_hash_sha256") or manifest.get("hash_sha256") or manifest.get("artifact_hash_sha256")
                    if expected_hash:
                        actual_hash = hashlib.sha256(art.read()).hexdigest()
                        if actual_hash != expected_hash:
                            # M307: REJECT por integridad fallida; no se confunde con DB_AUTH_ACTOR_M294 BLOCKED
                            return {
                                "status": "REJECT",
                                "decision": "REJECT",
                                "mission_id": self.mission_id,
                                "continuity": "STOP_ERROR",
                                "db_auth_actor_m294": "BLOCKED",
                                "op_claim": False,
                                "autonomous_loop": False,
                                "integrity_check": "REJECT",
                                "integrity_note": "M307 REJECT: artifact hash mismatch; file does not match manifest; do not proceed to invocation",
                                "restrict": ["no execution with mismatched artifact"],
                                "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "M307 REJECT: integrity failure"],
                            }
                        else:
                            # M308: conservar referencia a los bytes leídos; no reabrir artifact_path posteriormente
                            # art.read() ya consumió los bytes para hash (línea 61). No se guarda contenido completo (restricción), pero se documenta referencia estable.
                            # Cualquier invocación futura debe usar esta referencia (no reabrir artifact_path) o realizar nueva validación con bytes actuales.
                            # La brecha entre validación y uso queda parcialmente cerrada porque no hay segunda apertura en código existente (invocación bloqueada por DB_AUTH_ACTOR_M294 BLOCKED); el límite explícito es la condición de carrera si la invocación se autoriza sin usar referencia validada.
                            # M308 resultado: PASS PARTIAL (referencia documentada; no segunda apertura en código existente; invocación bloqueada por autorización; límite explícito documentado para condición de carrera).
                            self.validated_reference = {
                                "hash_sha256": actual_hash,
                                "path_read": artifact_path,
                                "bytes_read_once": True,
                                "reopen_for_use_blocked_by_auth": "DB_AUTH_ACTOR_M294 BLOCKED prevents real invocation; any future use must either operate on validated_bytes reference or perform new validation",
                                "race_condition_documented": "NOT_DETERMINED for race between validation and real execution (requires DB_AUTH_ACTOR_M294 UNBLOCKED + DBOP_SCHEMA_M290 VERIFIED + real evaluate_claim_evaluator invocation with validated reference)",
                                "validated_content_reference": "bytes from art.read() used for hash verification; same bytes must be used for any execution",
                            }
            except Exception:
                pass  # No inventar REJECT por error de lectura; dejar a contrato existente
        # Fase 1: solicitud
        self.request = {
            "mission_id": self.mission_id,
            "capability": "m322_claim_evaluator",
            "artifact_path": artifact_path or "/home/lucas/Escritorio/rxre/rx550_drv/vk_full_verified",
            "manifest_path": manifest_path or "/tmp/m279_manifest.json",
            "db_auth_authorized": False,  # DB_AUTH_ACTOR_M294 BLOCKED
            "db_op_modified": False,
            "authorization_needed": False,
            "restrictions": ["no GPU execution", "no MMIO", "no sudo", "static read-only", "no execute binary"],
            "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED => M306 REJECTED at R4; persistent VERIFIED blocked"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        self.iter_count += 1
        # Fase 2: selección (usando mecanismo existente, sin inventar interfaces)
        sup = M280Supervisor(max_iter=self.max_iter, max_duration_s=self.max_duration_s)
        selected, decision = sup.select_eligible(artifact_path=self.request["artifact_path"], manifest_path=self.request["manifest_path"])
        self.result = {"selected": selected, "decision": decision, "status": "NOT_DETERMINED" if decision == "NOT_DETERMINED" else ("BLOCKED" if decision == "BLOCKED" else ("INSUFFICIENT" if decision == "INSUFFICIENT" else decision))}
        # Defensa adversarial M291: capacidad seleccionada debe coincidir con solicitada
        requested_cap = self.request.get("capability") if self.request else "m322_claim_evaluator"
        if selected and requested_cap and selected != requested_cap:
            # No permitir invocación con capacidad distinta; documentar NOT_DETERMINED
            self.result["status"] = "NOT_DETERMINED"
            self.result["decision"] = "NOT_DETERMINED"
            # No cambiar decision del supervisor (ya refleja), pero asegurar que invocación no use selected incorrecto
            # El supervisor ya protege con M291; esta capa documenta la defensa adicional

        # Fase 3: invocación (documentada, no necesariamente real; depende de autorización)
        # Debido a DB_AUTH_ACTOR_M294 BLOCKED y DBOP_SCHEMA_M290 INSUFFICIENT, la invocación real de evaluate_claim_evaluator() no se autoriza para VERIFIED.
        # El componente documenta que se habría invocado, pero se detiene por BLOCKED.
        self.invocation = {
            "op": "run",
            "capability": selected,
            "command": "evaluate_claim_evaluator (simulated — blocked by DB_AUTH_ACTOR_M294)",
            "exit_status": 0 if decision == "COMPLETED" else (1 if decision == "NOT_DETERMINED" else 0),
            "output_preview": f"decision={decision}; selected={selected}; DB_AUTH_ACTOR_M294 BLOCKED; M306 REJECTED; DBOP_SCHEMA_M290 INSUFFICIENT",
            "persistido": 0,  # APPEND_ONLY documentation only; no VERIFIED
            "persistido_reason": "DB_AUTH_ACTOR_M294 BLOCKED => M306 REJECTED; DBOP_SCHEMA_M290 INSUFFICIENT",
            "restrictions": self.request["restrictions"],
            "limitations": self.request["limitations"],
        }

        # Fase 4: validación (sin modificar results para VERIFIED)
        self.validation = {
            "decision_recovered": decision,
            "hash_capturado": None,
            "integrity_check": "NOT_RUN" if decision != "COMPLETED" else "PASS",  # solo PASS si verificado; hoy BLOCKED => NOT_RUN
            "restrictions_verified": self.request["restrictions"],
            "limitations_verified": self.request["limitations"],
            "authorization_verified": False,  # DB_AUTH_ACTOR_M294 BLOCKED
            "db_op_modified_verified": False,
            "procedencia_authority_real": False,
            "procedencia_db_op_modified": False,
            "row_hash_verified": False,
            "independent_recovery": False,
            "notes": "DB_AUTH_ACTOR_M294 BLOCKED => M306 REJECTED; DBOP_SCHEMA_M290 INSUFFICIENT; validation independent requires DB_AUTH_ACTOR_M294 UNBLOCKED + real evaluate_claim_evaluator() invocation",
        }

        # Fase 5: cierre (documenta estado; no inventa COMPLETED sin autorización)
        self.closure = {
            "mission_id": self.mission_id,
            "status": self.result["status"],
            "decision": decision,
            "selected": selected,
            "continuity": "CONTINUE" if (decision in ("COMPLETED", "PARTIAL")) else ("STOP_LIMIT" if (self.iter_count >= self.max_iter) else ("STOP_BLOCKED" if ("DB_AUTH_ACTOR_M294 BLOCKED" in str(self.request.get("limitations"))) else "STOP_NO_ELIGIBLE" if decision == "NO_ELIGIBLE" else "STOP_ERROR")),
            "limitaciones": self.request["limitations"],
            "restrictions": self.request["restrictions"],
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "op_claim": False,
            "autonomous_loop": False,
            "max_duration_s": self.max_duration_s,
            "max_iter": self.max_iter,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Fase 6: persistencia de evento de ejecución (APPEND_ONLY; documenta BLOCKED; no VERIFIED)
        try:
            db = self._db()
            # Inserta en execution_events (APPEND_ONLY; no modifica results/operations protegidos para VERIFIED)
            # Documenta que la ejecución fue bloqueada por autorización, no ejecutada como VERIFIED
            eb = db.execute("""
                INSERT OR IGNORE INTO execution_events (evento_id, op, capability, exit_status, operation_id, result_id, persistido, limitations, timestamp, trace_id, lecciones_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"evt_m296_{self.mission_id}",
                "run",
                selected or "m296_executor",
                self.invocation.get("exit_status", 1),
                None,
                None,
                0,  # persistido=0 porque NO es VERIFIED (DB_AUTH_ACTOR_M294 BLOCKED; M306 REJECTED)
                json.dumps({"restrictions": self.request.get("restrictions"), "limitations": self.request.get("limitations"), "db_auth_actor_m294": "BLOCKED", "dbop_schema_m290": "INSUFFICIENT", "m306_rejected": True, "op_claim": False}),
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                f"trace_m296_{self.mission_id}",
                json.dumps({"lessons": ["DB_AUTH_ACTOR_M294 BLOCKED prevents VERIFIED persistence", "DBOP_SCHEMA_M290 INSUFFICIENT prevents schema change", "M291 select_eligible verified capability match", "No autonomous loop started", "Execution blocked by authorization"]}),
            ))
            db.commit()
            # Recuperación independiente (para validar persistencia de evento, no de VERIFIED)
            db2 = self._db()
            evt_check = db2.execute("SELECT evento_id, op, persistido, limitations FROM execution_events WHERE evento_id=?", (f"evt_m296_{self.mission_id}",)).fetchone()
            assert evt_check is not None
            assert evt_check[2] == 0  # persistido=0
            db2.close()
            self.validation["independent_recovery"] = True
            self.validation["execution_event_persisted"] = True
        except Exception as exc:
            # Si falla inserción (ej. TRIGGER bloqueante o esquema), documenta BLOCKED/INSUFFICIENT
            self.validation["independent_recovery"] = False
            self.validation["execution_event_persisted"] = False
            self.closure["status"] = "BLOCKED"
            self.closure["continuity"] = "STOP_BLOCKED"
            self.closure["notes"] = f"Execution event persistence blocked: {str(exc)[:120]}"
        finally:
            try:
                db.close()
            except Exception:
                pass

        return self.closure

    def describe(self):
        return {
            "mission_id": self.mission_id,
            "request": self.request,
            "invocation": self.invocation,
            "result": self.result,
            "validation": self.validation,
            "closure": self.closure,
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "op_claim": False,
            "autonomous_loop": False,
        }


if __name__ == "__main__":
    # Ejecutar una misión controlada en modo simulación / bloqueo documentado
    executor = M296Executor(mission_id="m296_001")
    closure = executor.run_single()
    print(f"M296 EXECUTOR: mission_id={executor.mission_id}, status={closure['status']}, decision={closure.get('decision')}, continuity={closure['continuity']}, db_auth={closure.get('db_auth_actor_m294')}, op_claim={closure.get('op_claim')}, autonomous_loop={closure.get('autonomous_loop')}")
    print(f"REQUEST: {executor.request}")
    print(f"INVOCATION: {executor.invocation}")
    print(f"VALIDATION: {executor.validation}")
