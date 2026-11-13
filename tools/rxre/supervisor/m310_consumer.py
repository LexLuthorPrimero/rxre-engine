#!/usr/bin/env python3
"""M310 — Consumidor de análisis estático de artefactos (archivo permitido, sin ejecución real, sin autorización simulada)."""
import hashlib, json, os, sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M310StaticConsumer:
    """Consumidor estático que opera sobre contenido validado (bytes o referencia estable). No ejecuta el artefacto. No modifica DB protegida."""
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.max_iter = max_iter
        self.autonomous_loop = False
        self.observations = {}

    def analyze(self):
        """Análisis estático: opera solo sobre referencia validada (no reabre archivo físico sin verificación)."""
        if not self.validated_reference:
            return {
                "status": "BLOCKED",
                "decision": "NOT_DETERMINED",
                "observations": {},
                "hash_input": None,
                "continuity": "STOP_BLOCKED",
                "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "validated_reference absent"],
                "restrictions": ["no execution", "no GPU", "no sudo", "static analysis only"],
                "race_condition_documented": "NOT_DETERMINED (no validated_reference)"
            }
        # Verificar que referencia contiene hash verificado
        hash_input = self.validated_reference.get("hash_sha256")
        if not hash_input:
            return {
                "status": "BLOCKED",
                "decision": "NOT_DETERMINED",
                "observations": {},
                "hash_input": None,
                "continuity": "STOP_ERROR",
                "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "validated_reference incomplete (no hash_sha256)"],
            }
        # Proceso estático: no reabrir archivo físico; usar referencia (hash verificado, lectura única documentada)
        # No hay archivo físico que reabrir en memoria; el análisis es sobre metadatos de la referencia (hash + lectura única) y formato del archivo original (solo si se provee ruta con autorización explícita y verificación independiente; hoy bloqueado).
        # Para análisis estático con archivo físico (requiere autorización externa), documentamos límite.
        observations = {
            "hash_verified": hash_input,
            "bytes_read_once": self.validated_reference.get("bytes_read_once"),
            "path_read": self.validated_reference.get("path_read"),
            "format_inferred": "unknown (requires file access for static analysis of content)",
            "analysis_type": "static_reference_only",
            "execution": None,
            "content_bytes_analyzed": False,  # hoy no analizamos bytes completos (restricción); solo referencia
        }
        # Intento de análisis estático limitado con archivo físico (solo lectura, no ejecución; documentado como limitado)
        path_read = self.validated_reference.get("path_read")
        if path_read and os.path.isfile(path_read) and self.max_iter >= 1:
            try:
                with open(path_read, "rb") as art:
                    b = art.read()
                actual_hash = hashlib.sha256(b).hexdigest()
                if actual_hash != hash_input:
                    # M307/M308: integridad fallida si archivo cambió; documentar REJECT
                    observations["integrity_after_reference"] = "REJECT (hash mismatch: file changed after validation)"
                    observations["race_condition_confirmed"] = True
                    observations["analysis_result"] = "REJECT"
                    return {
                        "status": "REJECT",
                        "decision": "REJECT",
                        "observations": observations,
                        "hash_input": hash_input,
                        "continuity": "STOP_ERROR",
                        "limitations": ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "integrity failure: file changed after validation"],
                    }
                # Análisis estático básico con archivo físico (solo lectura, sin ejecución)
                observations["content_bytes_analyzed"] = True
                observations["content_length_bytes"] = len(b)
                observations["content_is_ascii_text"] = all(32 <= c <= 126 or c in (9, 10, 13) for c in b[:min(32, len(b))])
                observations["format_inferred"] = "text/ascii_synthetic" if observations.get("content_is_ascii_text") else "binary/unknown"
                observations["analysis_result"] = "PASS_PARTIAL"
            except Exception as exc:
                observations["integrity_after_reference"] = f"INSUFFICIENT (read error: {str(exc)[:80]})"
                observations["analysis_result"] = "INSUFFICIENT"
        else:
            observations["integrity_after_reference"] = "NOT_RUN (file not accessible or authorization blocked)"
            observations["analysis_result"] = "PASS_PARTIAL (reference only; no real file access)"
        observations["race_condition_documented"] = self.validated_reference.get("race_condition_documented", "NOT_DETERMINED")
        observations["limitations"] = ["DB_AUTH_ACTOR_M294 BLOCKED", "DBOP_SCHEMA_M290 INSUFFICIENT", "static analysis only; no execution"]
        observations["restrictions"] = ["no execution", "no GPU", "no sudo", "static analysis only"]
        observations["continuity"] = "CONTINUE" if observations.get("analysis_result") in ("PASS_PARTIAL",) else "STOP_LIMIT"
        return {
            "status": "PASS_PARTIAL" if observations.get("analysis_result") == "PASS_PARTIAL" else "INSUFFICIENT",
            "decision": "PARTIAL",
            "observations": observations,
            "hash_input": hash_input,
            "continuity": observations.get("continuity", "STOP_LIMIT"),
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
        }

if __name__ == "__main__":
    # Ejemplo de uso aislado con referencia de M308
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    from supervisor.m296_executor import M296Executor
    ex = M296Executor(mission_id="m310_demo", max_iter=1)
    cl = ex.run_single('/tmp/m306_synthetic/artifact_valid.bin', '/tmp/m306_synthetic/manifest_h1.json')
    consumer = M310StaticConsumer(validated_reference=getattr(ex, 'validated_reference', {}), max_iter=1)
    result = consumer.analyze()
    print("M310 CONSUMER RESULT:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
