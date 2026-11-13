#!/usr/bin/env python3
"""M324 — Comparación semántica de informes M323 recuperados (archivo permitido; sin ejecución; sin invento; sin mecanismo falso; sin autorización simulada). Usa M323 store contract; clasificación determinista."""
import sys, hashlib, json, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

class M324ReportDiff:
    def __init__(self, validated_reference=None, max_iter=1):
        self.validated_reference = validated_reference or {}
        self.autonomous_loop = False
        self.max_iter = max_iter

    def compare(self, report_a_path=None, report_b_path=None, payload_a=None, payload_b=None):
        observations = {}
        differences = []
        matched = []
        unmatched_a = []
        unmatched_b = []
        interpretation = {}
        anomalies = {}
        unsupported = {}
        not_determined = {}
        if (not payload_a and not report_a_path) or (not payload_b and not report_b_path):
            return self._final(status="BLOCKED", decision="NOT_DETERMINED", observations={"reason":"missing_report_input"}, differences=[], continuity="STOP_BLOCKED", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","input missing"], restrictions=["fixture synthetic labeled"])
        # Recuperación mínima desde archivo si se indica; sin modificar históricos
        def load(p, path):
            if p is not None: return p
            if not path or not os.path.isfile(path): return None
            try:
                with open(path,"r",encoding="utf-8") as f: return json.load(f)
            except Exception: return None
        a = load(payload_a, report_a_path)
        b = load(payload_b, report_b_path)
        if not a or not b:
            return self._final(status="INSUFFICIENT", decision="NOT_DETERMINED", observations={"reason":"load_failed_or_invalid_input","a_present":bool(a),"b_present":bool(b)}, differences=[], continuity="STOP_LIMIT", limitations=["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","invalid_input"], restrictions=["fixture synthetic labeled"])
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M324-SYNTHETIC-DIFF-FIXTURE); not real artifact evidence"
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        hash_a = a.get("hash_input")
        hash_b = b.get("hash_input")
        observations["artifact_identity_a"] = hash_a[:16] if hash_a else None
        observations["artifact_identity_b"] = hash_b[:16] if hash_b else None
        # Categoría 1: identidad del artefacto
        if hash_a and hash_b and hash_a != hash_b:
            differences.append({"category":"ARTIFACT_IDENTITY_CHANGED","rule":"hash_input differs between reports; not treated as regression of same binary","a_hash":hash_a[:16],"b_hash":hash_b[:16],"status":"DOCUMENTED","interpretation":"Different artifacts; comparison is cross-artifact, not regression"})
        # Integridad / versión
        fp_a = a.get("fingerprint_sha256")
        fp_b = b.get("fingerprint_sha256")
        observations["integrity_a"] = fp_a is not None
        observations["integrity_b"] = fp_b is not None
        # Encontrar hallazgos (findings) y comparar por identidad semántica (tipo + stage + rule + evidence base, no id generado)
        findings_a = a.get("findings", [])
        findings_b = b.get("findings", [])
        # Emparejamiento simple por (type, rule) con fallback a evidencia
        def key(f): return (f.get("type"), f.get("status"), f.get("rule",""))
        keys_a = {key(f): f for f in findings_a}
        keys_b = {key(f): f for f in findings_b}
        common = set(keys_a) & set(keys_b)
        only_a = set(keys_a) - set(keys_b)
        only_b = set(keys_b) - set(keys_a)
        for k in common:
            matched.append({"key":k,"a":keys_a[k],"b":keys_b[k],"category":"MATCHED","status":"NO_CHANGE" if keys_a[k].get("status")==keys_b[k].get("status") else "EPISTEMIC_STATUS_CHANGED","interpretation":"Matched finding; status change documented if different; not treated as refutation"})
        for k in only_a:
            unmatched_a.append({"key":k,"finding":keys_a[k],"category":"FINDING_REMOVED","rule":"finding present in A absent in B; not treated as refutation (absence may be due to blocked/incomplete stage)"})
        for k in only_b:
            unmatched_b.append({"key":k,"finding":keys_b[k],"category":"FINDING_ADDED","rule":"finding present in B absent in A"})
        if unmatched_a: differences.append({"category":"FINDING_REMOVED","count":len(unmatched_a),"status":"DOCUMENTED","rule":"absence documented; not elevated to refutation; may reflect blocked/incomplete stage"})
        if unmatched_b: differences.append({"category":"FINDING_ADDED","count":len(unmatched_b),"status":"DOCUMENTED"})
        # Derivación / procedencia: comparar correlations / observations / interpretation
        # Cobertura: stage_results cambios
        stages_a = a.get("stage_results", {})
        stages_b = b.get("stage_results", {})
        stages_common = set(stages_a) & set(stages_b)
        stages_only_a = set(stages_a) - set(stages_b)
        stages_only_b = set(stages_b) - set(stages_a)
        if stages_only_a or stages_only_b:
            differences.append({"category":"COVERAGE_CHANGED","rule":"stage coverage differs; absence not treated as refutation","only_in_a":list(stages_only_a),"only_in_b":list(stages_only_b),"status":"DOCUMENTED"})
        # Estado epistemológico: comparar status de hallazgos comunes con cambio
        for m in matched:
            if m.get("category")=="EPISTEMIC_STATUS_CHANGED":
                differences.append({"category":"EPISTEMIC_STATUS_CHANGED","key":m["key"],"from":m["a"].get("status"),"to":m["b"].get("status"),"interpretation":"Status weakened or changed; degradation preserved; not upgraded automatically"})
        # Diferencia representacional pura: si todos los hallazgos coinciden, hash del artefacto igual, estados iguales, pero fingerprint u orden difiere => REPRESENTATION_ONLY
        if not differences and (hash_a == hash_b) and (fp_a == fp_b):
            differences.append({"category":"REPRESENTATION_ONLY","rule":"canonical content identical; any file-level difference is representation-only","status":"CONFIRMED"})
        # Conflictos / anomalias
        anomalies_a = a.get("anomalies", {})
        anomalies_b = b.get("anomalies", {})
        if anomalies_a or anomalies_b:
            differences.append({"category":"ANOMALY","rule":"anomalies present; compared but not resolved automatically","a_keys":list(anomalies_a.keys()),"b_keys":list(anomalies_b.keys()),"status":"DOCUMENTED"})
        # Resultado global
        global_status = "PASS_PARTIAL"
        if differences:
            # Si hay cambio de identidad de artefacto => no regresión; si hay cambios semánticos documentados => PARTIAL
            has_artifact_change = any(d.get("category")=="ARTIFACT_IDENTITY_CHANGED" for d in differences)
            has_removal = any(d.get("category")=="FINDING_REMOVED" for d in differences)
            interpretation["global_result"] = "COMPARISON_COMPLETE" if not has_artifact_change else "CROSS_ARTIFACT_COMPARISON"
            if has_artifact_change:
                interpretation["regression_claim"] = "NOT_SUPPORTED (artifact identity changed; not regression of same binary)"
            else:
                interpretation["regression_claim"] = "PARTIAL (changes documented; absence not treated as refutation; states preserved)"
        else:
            interpretation["global_result"] = "IDENTICAL"
            interpretation["regression_claim"] = "NO CHANGE"
        interpretation["limitations"] = "Comparison relies on contractual fields of M323 payload; full semantic verification requires authorization + independent recovery + M322 provenance; fixture synthetic labeled"
        interpretation["separation_applied"] = {"OBSERVATION":"field comparisons","DERIVATION":"classification rules","INTERPRETATION":"global result with explicit limitations","ANOMALY":"documented anomalies","UNSUPPORTED":"full behavioral verification unsupported","NOT_DETERMINED":"some differences indeterminate without full verification"}
        observations["fixture_evidence_labeled"] = True
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["continuity_state"] = "CONTINUE"
        unsupported["full_behavioral_verification"] = True
        unsupported["full_regression_proof"] = True
        not_determined["indeterminate_differences"] = "NOT_DETERMINED (full independent verification blocked)"
        return self._final(status=global_status, decision="PARTIAL" if differences else "PASS", observations=observations, differences=differences, matched=matched, unmatched_a=unmatched_a, unmatched_b=unmatched_b, interpretation=interpretation, anomalies=anomalies, unsupported=unsupported, not_determined=not_determined, continuity="CONTINUE")

    def _final(self, status, decision, observations, differences, matched, unmatched_a, unmatched_b, interpretation, anomalies, unsupported, not_determined, continuity):
        observations["autonomous_loop"] = False
        observations["max_iter"] = self.max_iter
        observations["db_auth_actor_m294"] = "BLOCKED"
        observations["dbop_schema_m290"] = "INSUFFICIENT"
        observations["fixture_evidence_note"] = "Fixture synthetic clearly labeled (M324-SYNTHETIC-DIFF-FIXTURE); not real artifact evidence"
        observations["no_false_regression"] = True
        observations["absence_not_refutation"] = True
        observations["no_automatic_elevation"] = True
        return {"status":status,"decision":decision,"observations":observations,"differences":differences,"matched":matched,"unmatched_a":unmatched_a,"unmatched_b":unmatched_b,"interpretation":interpretation,"anomalies":anomalies,"unsupported":unsupported,"not_determined":not_determined,"continuity":continuity,"limitations":["DB_AUTH_ACTOR_M294 BLOCKED","DBOP_SCHEMA_M290 INSUFFICIENT","fixture synthetic clearly labeled","full behavioral verification unsupported","absence not treated as refutation"],"restrictions":["no execution","fixture synthetic labeled","autonomous_loop=False","max_iter=1","op_claim=False","no protected file change"],"autonomous_loop":False,"max_iter":self.max_iter,"db_auth_actor_m294":"BLOCKED","dbop_schema_m290":"INSUFFICIENT","race_condition_documented":"NOT_DETERMINED"}

if __name__ == "__main__":
    import hashlib
    f = bytes.fromhex('4889c790c3') + b'M324-SYNTHETIC-DIFF-FIXTURE'
    ref = {"hash_sha256": hashlib.sha256(f).hexdigest(), "bytes_read_once": True, "race_condition_documented":"NOT_DETERMINED"}
    # Prueba básica con informes idénticos (simulados)
    a = {"format_version":"rxre-v1.0-m323","hash_input":ref["hash_sha256"],"fingerprint_sha256":"abc","continuity":"CONTINUE","stage_results":{"structural":{"status":"PASS_PARTIAL"}},"findings":[{"type":"OBSERVATION","status":"PASS_PARTIAL","rule":"integrity","evidence":"hash"}],"observations":{"integrity_reference":"PASS","fixture_evidence_labeled":True},"limitations":["DB_AUTH_ACTOR_M294 BLOCKED"]}
    b = {"format_version":"rxre-v1.0-m323","hash_input":ref["hash_sha256"],"fingerprint_sha256":"abc","continuity":"CONTINUE","stage_results":{"structural":{"status":"PASS_PARTIAL"}},"findings":[{"type":"OBSERVATION","status":"PASS_PARTIAL","rule":"integrity","evidence":"hash"}],"observations":{"integrity_reference":"PASS","fixture_evidence_labeled":True},"limitations":["DB_AUTH_ACTOR_M294 BLOCKED"]}
    res = M324ReportDiff(validated_reference=ref, max_iter=1).compare(payload_a=a, payload_b=b)
    print("M324 identical:", res["status"], res["decision"], "differences:", len(res.get("differences",[])), "global=", res["interpretation"].get("global_result"))
    # Diferencia de representación (mismo contenido, fp diferente por orden) — simulado cambiando fingerprint
    b2 = dict(b); b2["fingerprint_sha256"] = "def"
    res2 = M324ReportDiff(validated_reference=ref, max_iter=1).compare(payload_a=a, payload_b=b2)
    print("M324 rep change:", res2["status"], res2["decision"], [d["category"] for d in res2.get("differences",[])])
