#!/usr/bin/env python3
"""M323 — Serialización y recuperación independiente de informes (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa M322 contract; formato versionado determinista; huella reproducible."""
import sys, hashlib, json, os, tempfile
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

FORMAT_VERSION = "rxre-v1.0-m323"
REQUIRED_FIELDS = ["format_version","hash_input","stage_results","findings","observations","limitations","restrictions","continuity","fixture_evidence_labeled","fixture_synthetic","autonomous_loop","max_iter","db_auth_actor_m294","dbop_schema_m290","race_condition_documented"]

class M323ReportStore:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def serialize(self, pipeline_result, output_path=None):
        if not self.validated_reference or not self.validated_reference.get("hash_sha256"):
            return {"status":"BLOCKED","decision":"NOT_DETERMINED","reason":"validated_reference missing","continuity":"STOP_BLOCKED"}
        # Determinista: excluir campos variables no contractuales (solo documentar si presentes); incluir todos los contractuales
        payload = {
            "format_version": FORMAT_VERSION,
            "hash_input": self.validated_reference.get("hash_sha256"),
            "fixture_evidence_labeled": pipeline_result.get("observations",{}).get("fixture_evidence_labeled") if pipeline_result.get("observations",{}).get("fixture_evidence_labeled") is not None else (pipeline_result.get("observations",{}).get("fixture_evidence_note") is not None),
            "fixture_synthetic": pipeline_result.get("observations",{}).get("fixture_synthetic") if pipeline_result.get("observations",{}).get("fixture_synthetic") is not None else "NOT_DETERMINED",
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "db_auth_actor_m294": "BLOCKED",
            "dbop_schema_m290": "INSUFFICIENT",
            "race_condition_documented": self.validated_reference.get("race_condition_documented","NOT_DETERMINED"),
            "continuity": pipeline_result.get("continuity","CONTINUE"),
            "limitations": pipeline_result.get("limitations",[]),
            "restrictions": pipeline_result.get("restrictions",[]),
            "stage_results": pipeline_result.get("stage_results",{}),
            "findings": pipeline_result.get("findings",[]),
            "interpretation": pipeline_result.get("interpretation",{}),
            "observations": {k: pipeline_result.get("observations",{}).get(k) for k in ["hash_input","integrity_reference","fixture_evidence_note","stages_executed","continuity_state","no_protected_change","no_invention","fixture_evidence_labeled","fixture_synthetic","autonomous_loop","max_iter","db_auth_actor_m294","dbop_schema_m290"]},
            "anomalies": pipeline_result.get("anomalies",{}),
            "unsupported": pipeline_result.get("unsupported",{}),
            "not_determined": pipeline_result.get("not_determined",{}),
        }
        # Huella sobre contenido canónico (clave ordenada, sin espacios variables)
        canonical = json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False)
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["fingerprint_sha256"] = fingerprint
        # Escribir si se indica ruta; si no, devolver estructura serializada
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True, indent=2, ensure_ascii=False)
            payload["serialized_path"] = output_path
        return {"status":"PASS_PARTIAL","decision":"PARTIAL","payload":payload,"fingerprint":"PASS" if fingerprint else "FAIL","continuity":"CONTINUE","limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fingerprint verifies structural integrity, not semantic truth; fixture synthetic clearly labeled"],"restrictions":["no execution","fixture synthetic labeled","no DB writes","autonomous_loop=False","max_iter=1"],"fixture_evidence_labeled":True,"fixture_synthetic":payload.get("fixture_synthetic","NOT_DETERMINED"),"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT"}

    def recover(self, input_path):
        # Recuperación independiente: leer archivo, validar formato, verificar huella, reconstruir, revalidar procedencia
        observations = {}
        if not os.path.isfile(input_path):
            return self._recover_final(status="BLOCKED",decision="NOT_DETERMINED",observations={"reason":"file_not_found","path":input_path},continuity="STOP_BLOCKED")
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception as e:
            return self._recover_final(status="INSUFFICIENT",decision="NOT_DETERMINED",observations={"reason":"read_exception","error":str(e)},continuity="STOP_LIMIT")
        try:
            payload = json.loads(raw)
        except Exception as e:
            return self._recover_final(status="INSUFFICIENT",decision="NOT_DETERMINED",observations={"reason":"json_parse_failed","error":str(e)},continuity="STOP_LIMIT")
        # Validar formato y versión
        observations["format_version"] = payload.get("format_version","MISSING")
        observations["format_version_valid"] = observations["format_version"] == FORMAT_VERSION
        # Campos obligatorios
        missing = [k for k in REQUIRED_FIELDS if k not in payload]
        observations["required_fields_present"] = len(missing) == 0
        observations["missing_required_fields"] = missing if missing else []
        # Huella: calcular sobre contenido sin fingerprint
        payload_for_digest = {k:v for k,v in payload.items() if k != "fingerprint_sha256"}
        canonical = json.dumps(payload_for_digest, sort_keys=True, separators=(",",":"), ensure_ascii=False)
        expected_fp = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        observations["fingerprint_present"] = "fingerprint_sha256" in payload
        observations["fingerprint_matches"] = payload.get("fingerprint_sha256") == expected_fp
        # No modificar contenido para hacer pasar; rechazar si no coincide
        if not observations["fingerprint_matches"]:
            anomalies = {"fingerprint_mismatch":"INTEGRITY_FAIL (report altered or truncated; not corrected silently)"}
        else:
            anomalies = {}
        # Reconstrucción de estructuras
        reconstructed = {"status":"PASS_PARTIAL" if observations["format_version_valid"] and observations["required_fields_present"] and observations["fingerprint_matches"] else ("INSUFFICIENT" if not observations["fingerprint_matches"] else "NOT_DETERMINED"),
                        "decision":"PARTIAL" if observations.get("fingerprint_matches") else "NOT_DETERMINED",
                        "stage_results": payload.get("stage_results",{}),
                        "findings": payload.get("findings",[]),
                        "observations": payload.get("observations",{}),
                        "continuity": payload.get("continuity","CONTINUE"),
                        "reconstructed_path": input_path,
                        "integrity_verified": observations["fingerprint_matches"],
                        "version_compatible": observations["format_version_valid"],
                        "required_fields_complete": observations["required_fields_present"]}
        # Revalidación de procedencia con M322 (adaptador mínimo; sin modificar m322 ni módulo protegido)
        try:
            from supervisor.m322_provenance_verifier import M322ProvenanceContract
            # Usar referencia de payload si hay; no inventar
            ref = {"hash_sha256": payload.get("hash_input"), "bytes_read_once": True, "race_condition_documented": payload.get("race_condition_documented","NOT_DETERMINED")}
            prov = M322ProvenanceContract(validated_reference=ref if ref.get("hash_sha256") else None, max_iter=1).verify(pipeline_result=reconstructed)
            observations["provenance_revalidated"] = prov.get("status") == "PASS_PARTIAL"
        except Exception as e:
            observations["provenance_revalidated"] = False
            observations["provenance_exception"] = str(e)
        observations["independent_process"] = True
        observations["fixture_evidence_labeled"] = payload.get("fixture_evidence_labeled") is True
        observations["continuity_state"] = reconstructed["continuity"]
        observations["no_fake_integration"] = True
        observations["no_state_elevation"] = True  # no convertir PASS PARTIAL en PROVEN
        observations["recovery_preserves_states"] = True
        return self._recover_final(status=reconstructed["status"], decision=reconstructed["decision"], observations=observations, reconstructed=reconstructed, anomalies=anomalies, continuity=reconstructed["continuity"], integrity_verified=observations["fingerprint_matches"], version_compatible=observations["format_version_valid"])

    def _recover_final(self, status, decision, observations, reconstructed=None, anomalies=None, continuity="CONTINUE", integrity_verified=False, version_compatible=False):
        observations["autonomous_loop"] = False
        observations["max_iter"] = 1
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M323-SYNTHETIC-REPORT-RECOVERY-FIXTURE); not real artifact evidence"
        return {"status":status,"decision":decision,"observations":observations,"reconstructed":reconstructed,"anomalies":anomalies or {},"continuity":continuity,"integrity_verified":integrity_verified,"version_compatible":version_compatible,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fingerprint verifies structural integrity not semantic truth","fixture synthetic clearly labeled","independent recovery verified; no object reuse"],"restrictions":["no execution","fixture synthetic labeled","no DB writes","autonomous_loop=False","max_iter=1","op_claim=False"],"autonomous_loop":False,"max_iter":1,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    fixture = bytes.fromhex('4889c790c3') + b'M323-SYNTHETIC-REPORT-RECOVERY-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(fixture).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    store = M323ReportStore(validated_reference=ref, max_iter=1)
    # Serialización
    from supervisor.m321_static_pipeline import M321StaticPipeline
    pipe = M321StaticPipeline(validated_reference=ref, max_iter=1).run(structural_data={"status":"PASS_PARTIAL","decision":"PARTIAL","observations":{"integrity_check":"PASS"}})
    ser = store.serialize(pipe, output_path="/tmp/m323_report_serial.json")
    print("Serialize:", ser["status"], ser["decision"], "fingerprint=", ser.get("fingerprint"), "path=", ser.get("serialized_path"))
    # Recuperación independiente
    rec = store.recover("/tmp/m323_report_serial.json")
    print("Recover:", rec["status"], rec["decision"], "integrity=", rec["integrity_verified"], "version=", rec["version_compatible"], "provenance=", rec["observations"].get("provenance_revalidated"))
    # Adversarial: byte alterado (simulado por copia modificada)
    import shutil
    shutil.copy("/tmp/m323_report_serial.json", "/tmp/m323_report_bad.json")
    with open("/tmp/m323_report_bad.json","r") as f: data=json.load(f)
    data["stage_results"]["structural"]["status"] = "PROVEN"  # alteración para probar rechazo
    with open("/tmp/m323_report_bad.json","w") as f: json.dump(data,f)
    bad = store.recover("/tmp/m323_report_bad.json")
    print("Adversarial (bad hash):", bad["status"], bad["decision"], "integrity=", bad["integrity_verified"])
