#!/usr/bin/env python3
"""RXRE-M322 — EVALUADOR REUTILIZABLE DE AFIRMACIONES Y EVIDENCIA.
Reutiliza contratos existentes: evidence_claim_verification (hash/artefacto),
evidence_snapshot (captura física), manifest_binding_contract (vinculación),
scope_provenance_contract (alcance/procedencia), unified_verified_contract (decisión).
NO crea un segundo sistema de integridad/atestación/autorización.
No modifica archivos protegidos ni DB_OP / DB_ISO.
"""
import os, json, hashlib, sqlite3

sys_path = "/home/lucas/Escritorio/rxre/tools"
if sys_path not in __import__("sys").path:
    __import__("sys").path.insert(0, sys_path)

from rxre.contracts.evidence_claim_verification import calcular_sha256
from rxre.core import evidence_snapshot as es
from rxre.core.manifest_binding_contract import validar_vinculacion
from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
from rxre.core.unified_verified_contract import evaluar_transicion

DECISION_SUPPORTED = "SUPPORTED"
DECISION_REFUTED = "REFUTED"
DECISION_INSUFFICIENT = "INSUFFICIENT"
DECISION_CONFLICT = "CONFLICT"
DECISION_INVALID = "INVALID"

LIMITS = ("Identidad del actor no verificada por fuente de producción "
          "(DB_AUTH_ACTOR_M294 pendiente); autorización de escritura en DB_OP pendiente "
          "(DBOP_ACCESS_M295); esta evaluación no declara VERIFIED ni cierra BYPASS_PROVEN.")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _scope_de_manifest(manifest_path):
    m = _read_json(manifest_path) if manifest_path else None
    if not m:
        return None, None
    scope = m.get("scope") or m.get("scope_esperado")
    if not scope:
        hf = m.get("hash_fuentes") or {}
        scope = hf.get("anidado") or m.get("artefacto_scope")
    art = m.get("artifact_path") or m.get("artefacto_path") or m.get("file")
    return scope, art


def evaluate_claim_evaluator(assertion_id, claim_text, evidence_refs, claim_scope=None,
                             artifact_path=None, manifest_path=None,
                             observed_artifact_hash=None,
                             db_op_path=None, db_op_result_id=None,
                             evidence_ref=None):
    """Evalúa una afirmación contra evidencia verificable.

    evidence_refs: lista de rutas REALES de evidencia (artefactos) o referencias
                   lógicasaccompanied de artifact_path. Una referencia que no resuelve
                   a un artefacto real -> INVALID (no se inventa evidencia).
    """
    out = {
        "assertion_id": assertion_id,
        "claim_text": claim_text,
        "claim_scope": claim_scope,
        "evidence_refs": list(evidence_refs or []),
        "decision": DECISION_INSUFFICIENT,
        "reason": "",
        "rules_applied": [],
        "integrity_check": "NOT_RUN",     # validez del artefacto
        "evidence_valid": False,          # validez de la evidencia
        "scope_compatible": False,        # compatibilidad de alcance
        "semantic_conclusion": "",        # conclusión semántica
        "resolved_evidence": [],
        "verifications_executed": [],
        "procedencia": {
            "source_contracts": ["contracts/evidence_claim_verification", "core/evidence_snapshot",
                                 "core/manifest_binding_contract", "contracts/scope_provenance_contract",
                                 "core/unified_verified_contract"],
            "db_op_modified": False,
            "authority_real": False,
            "protected_untouched": ["core/store.py", "core/machine.py",
                                     "core/unified_verified_contract.py", "core/evidence_integrity.py"],
        },
        "limitations": [LIMITS],
        "missing_data": [],
    }

    # ---------- R1: referencias de evidencia ----------
    if not evidence_refs:
        out["decision"] = DECISION_INSUFFICIENT
        out["reason"] = "R1_NO_EVIDENCE: la afirmación no tiene referencias de evidencia; ausencia de evidencia no es refutación"
        out["rules_applied"].append("R1")
        out["missing_data"].append("evidence_refs")
        return out
    resolved = []
    for ref in evidence_refs:
        cand = ref
        if not os.path.isabs(str(ref)) and artifact_path:
            cand = os.path.join(os.path.dirname(artifact_path), str(ref))
        if not os.path.isfile(cand):
            out["decision"] = DECISION_INVALID
            out["reason"] = "R1_REFERENCE_UNRESOLVED: evidencia '%s' no resuelve a un artefacto existente" % ref
            out["rules_applied"].append("R1")
            out["missing_data"].append("evidence_ref:%s" % ref)
            return out
        h = calcular_sha256(cand)
        resolved.append({"ref": ref, "path": cand, "sha256": h})
        out["verifications_executed"].append("calcular_sha256(%s)=%s" % (os.path.basename(cand), h[:16]))
    out["resolved_evidence"] = resolved

    # ---------- R2: integridad del artefacto observado ----------
    target = artifact_path if (artifact_path and os.path.isfile(artifact_path)) else resolved[0]["path"]
    h_real = calcular_sha256(target)
    if observed_artifact_hash and observed_artifact_hash != h_real:
        out["decision"] = DECISION_REFUTED
        out["integrity_check"] = "FAIL"
        out["semantic_conclusion"] = "la evidencia observada no corresponde al artefacto declarado"
        out["reason"] = "R2_INTEGRITY_MISMATCH: hash observado (%s) != hash declarado (%s)" % (h_real[:16], observed_artifact_hash[:16])
        out["rules_applied"].append("R2")
        out["procedencia"]["evidence_sha256"] = h_real
        return out
    out["integrity_check"] = "PASS"
    out["procedencia"]["evidence_sha256"] = h_real
    out["rules_applied"].append("R2")

    # ---------- R3: procedencia y vinculación de manifiesto ----------
    manifest_scope, manifest_artifact = _scope_de_manifest(manifest_path)
    if manifest_path:
        if not os.path.isfile(manifest_path):
            out["decision"] = DECISION_INVALID
            out["reason"] = "R3_MANIFEST_UNRESOLVED: manifiesto '%s' no existe" % manifest_path
            out["rules_applied"].append("R3")
            return out
        try:
            # M325/M328: verificación mínima de hash canónico en manifiesto
            expected_hash = None
            try:
                import json
                m = json.load(open(manifest_path, "r"))
                expected_hash = m.get("artefacto_hash_sha256") or m.get("hash_sha256") or m.get("artifact_hash_sha256")
            except Exception:
                pass
            if expected_hash is None or expected_hash == "":
                out["decision"] = DECISION_INSUFFICIENT
                out["reason"] = "R3_MANIFEST_INSUFFICIENT: manifiesto sin hash de artefacto canónico (evidencia insuficiente, no refutada)"
                out["rules_applied"].append("R3")
                out["integrity_check"] = "PASS"
                out["evidence_valid"] = False
                out["limitations"].append("manifiesto_sin_hash_canonico")
                return out
            v = validar_vinculacion(manifest_path, artifact_path_esperado=target,
                                     scope_esperado=claim_scope)
            out["verifications_executed"].append("validar_vinculacion(manifest)=%s" % v.get("decision"))
            out["evidence_valid"] = (v.get("decision") == "PASS")
            if v.get("decision") == "REJECTED":
                out["decision"] = DECISION_REFUTED
                out["integrity_check"] = "PASS"
                out["semantic_conclusion"] = "el manifiesto no describe estos bytes"
                out["reason"] = "R3_LINKING_REFUTED: %s" % str(v.get("explanation", ""))[:110]
                out["rules_applied"].append("R3")
                return out
        except Exception as exc:
            out["verifications_executed"].append("validar_vinculacion(manifest)=EXCEPTION")
            out["missing_data"].append("validar_vinculacion:%s" % str(exc)[:60])
    else:
        out["missing_data"].append("manifest_path")
    out["rules_applied"].append("R3")

    # ---------- R4: compatibilidad de alcance ----------
    if claim_scope and manifest_scope and claim_scope != manifest_scope:
        out["decision"] = DECISION_REFUTED
        out["scope_compatible"] = False
        out["semantic_conclusion"] = "la evidencia pertenece a otro alcance"
        out["reason"] = "R4_SCOPE_MISMATCH: alcance de la afirmación ('%s') != alcance de la evidencia ('%s')" % (claim_scope, manifest_scope)
        out["rules_applied"].append("R4")
        return out
    out["scope_compatible"] = True
    out["rules_applied"].append("R4")

    # ---------- R5: conflicto entre evidencias comparables ----------
    if len(resolved) >= 2:
        hashes = {r["sha256"] for r in resolved}
        scopes = set()
        scope_known = True
        for r in resolved:
            sibling = r["path"] + ".manifest.json"
            if os.path.isfile(sibling):
                sc, _a = _scope_de_manifest(sibling)
            elif r["path"] == target and manifest_path and os.path.isfile(manifest_path):
                sc, _a = _scope_de_manifest(manifest_path)
            else:
                sc = None
            if sc is None:
                scope_known = False
            scopes.add(sc)
        # Comparabilidad exigida: mismo alcance conocido y unico
        comparables = scope_known and len(scopes) == 1
        if len(hashes) > 1 and comparables:
            out["decision"] = DECISION_CONFLICT
            out["semantic_conclusion"] = "evidencias comparables con contenidos divergentes"
            out["reason"] = "R5_CONFLICT: %d evidencias comparables con %d hashes distintos" % (len(resolved), len(hashes))
            out["rules_applied"].append("R5")
            return out
        if len(hashes) > 1 and not comparables:
            out["decision"] = DECISION_INSUFFICIENT
            out["semantic_conclusion"] = "resultados distintos pero no comparables; no se declara CONFLICT"
            out["reason"] = "R5_NOT_COMPARABLE: hashes distintos y alcances no demonstrablemente comparables (scopes=%s); no es CONFLICT" % sorted(str(x) for x in scopes)
            out["rules_applied"].append("R5")
            out["missing_data"].append("comparabilidad_entre_evidencias")
            return out
    out["rules_applied"].append("R5")

    # ---------- R6: conclusión semántica ----------
    if not out["evidence_valid"]:
        out["decision"] = DECISION_INSUFFICIENT
        out["semantic_conclusion"] = "no hay evidencia verificable suficiente para afirmar"
        out["reason"] = "R6_EVIDENCE_NOT_VERIFIED: la evidencia no supera la verificación de vinculación"
        out["missing_data"].append("evidence_valid")
    elif out["integrity_check"] != "PASS":
        out["decision"] = DECISION_REFUTED
        out["semantic_conclusion"] = "integridad fallida"
        out["reason"] = "R6_INTEGRITY_NOT_PASS"
    else:
        out["decision"] = DECISION_SUPPORTED
        out["semantic_conclusion"] = "la evidencia observada respalda la afirmación dentro del alcance evaluado"
        out["reason"] = "R6_SUPPORTED: evidencia íntegra, verificable y de alcance compatible; sin contradicción"
    out["rules_applied"].append("R6")
    return out
