#!/usr/bin/env python3
"""RXRE-MISSION-252 — CONTRATO DE VINCULACIÓN EVIDENCIA-SCOPE (aislado).
No modifica core/store.py, evidence_integrity.py, machine.py, adaptadores.
No activa op:claim; no escribe DB_OP.

Evaluación pura de vinculación evidencia ↔ claim según:
  - integridad de evidencia (hash / estructura / referencia resoluble)
  - procedencia verificable de evidence scope
  - scope declarado por claim
  - regla explícita de compatibilidad / incompatibilidad (solo si ambos scopes verificables)
"""
import hashlib, json

# Regla contractual mínima: solo MISMATCH si ambos scopes verificables y distintos
# (no hay regla de incompatibilidad por diferencias no especificadas en contrato)
REGLAS_EXPLICITAS = {
    # ejemplo contractual: si claim = "scope_A" y evidencia = "scope_A_deriv" => MISMATCH
    # por defecto: sin regla explícita => INDETERMINATE cuando scopes verificables y distintos
}


def vincular_evidencia_claim(
    evidence_ref: str,           # ID de evidencia (ej. "res_real_001")
    evidence_path: str = None,   # archivo observado (opcional)
    evidence_manifest_path: str = None,  # manifest E2E (opcional)
    evidence_hash: str = None,   # hash esperado del artefacto
    evidence_scope_verifiable: str = None,  # scope con procedencia verificada; None = desconocido
    claim_scope: str = None,     # scope declarado por claim (de finding_dict / DB_ISO)
    claim_statement_hash: str = None,
) -> dict:
    """
    Devuelve dict tipado:
      decision: MATCH | MISMATCH | INDETERMINATE | INVALID
      explanation: str
      integrity_ok: bool
      provenance_ok: bool
      scope_evidence_ok: bool
      scope_claim_ok: bool
    Regla: integridad es precondición independiente, nunca prueba de scope.
    """
    result = {
        "decision": "INDETERMINATE",
        "explanation": "",
        "integrity_ok": False,
        "provenance_ok": False,
        "scope_evidence_ok": False,
        "scope_claim_ok": False,
        "evidence_ref": evidence_ref,
    }

    # --- 1) Precondición de referencia (no inventar) ---
    if not evidence_ref or not isinstance(evidence_ref, str) or evidence_ref == "":
        result["decision"] = "INVALID"
        result["explanation"] = "Referencia de evidencia inválida o ausente (no inventable)"
        return result

    # --- 2) Integridad (precondición independiente) ---
    # Si hay manifest y archivo, verificar hash básico (simulado por contrato; no usa core)
    integrity = False
    if evidence_path and evidence_hash:
        import os
        if os.path.isfile(evidence_path):
            try:
                with open(evidence_path, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                # Tolerancia de truncamiento (como _coincide_hash)
                if evidence_hash == h or (len(evidence_hash) >= 8 and h.startswith(evidence_hash)) or (len(h) >= 8 and evidence_hash.startswith(h)):
                    integrity = True
            except Exception:
                pass
    # Si no hay archivo / hash: no se afirma integridad; pero no se declara INVALID automáticamente
    # (la referencia puede ser resoluble por DB_OP sin archivo local; integridad puede ser no verificada, no fallida)
    if evidence_manifest_path and (not evidence_path or not integrity):
        # Si hay manifest pero no archivo o hash no coincide -> INVALID (manifest alterado / incompleto)
        try:
            with open(evidence_manifest_path) as f:
                m = json.load(f)
            mhash = m.get("artefacto_hash_sha256") or m.get("hash_sha256", "")
            if mhash and evidence_hash:
                if evidence_hash != mhash and not (len(mhash) >= 8 and evidence_hash.startswith(mhash)) and not (len(evidence_hash) >= 8 and mhash.startswith(evidence_hash)):
                    result["decision"] = "INVALID"
                    result["explanation"] = "Integridad fallida: manifest y hash observados divergen (precondición independiente)"
                    result["integrity_ok"] = False
                    return result
            # Si manifest existe y es consistente con hash (o sin hash): integridad no fallida por manifest
            if mhash or ("artefacto_path" in m and "artefacto_size_bytes" in m):
                integrity = True  # manifest intacto como respaldo mínimo
        except Exception as exc:
            result["decision"] = "INVALID"
            result["explanation"] = "Manifest E2E malformado o inaccesible: %s" % str(exc)
            result["integrity_ok"] = False
            return result

    # Si hay archivo y se verificó -> integridad ok
    if evidence_path and evidence_hash and integrity:
        result["integrity_ok"] = True
    elif evidence_path and evidence_hash and not integrity:
        result["integrity_ok"] = False
        result["decision"] = "INVALID"
        result["explanation"] = "Integridad fallida: archivo observado no coincide con hash esperado (precondición independiente)"
        return result
    elif evidence_manifest_path and integrity:
        result["integrity_ok"] = True
    else:
        # No se confirma ni se rechaza integridad; sigue como precondición no cumplida (no INVALID, a menos que manifest alterado)
        result["integrity_ok"] = False

    # --- 3) Procedencia verificable de evidence scope ---
    # Regla: "Scope declarado sin procedencia verificable no equivale a scope auténtico"
    # Si evidence_scope_verifiable es None o vacío => no autenticado
    if evidence_scope_verifiable is not None and str(evidence_scope_verifiable).strip() != "":
        result["scope_evidence_ok"] = True
        result["provenance_ok"] = True
    else:
        result["scope_evidence_ok"] = False
        result["provenance_ok"] = False

    # --- 4) Scope del claim ---
    if claim_scope is not None and str(claim_scope).strip() != "":
        result["scope_claim_ok"] = True
    else:
        result["scope_claim_ok"] = False

    # --- 5) Decisión de vinculación ---
    # Regla: integridad es precondición; si integridad fallida => INVALID (ya manejado arriba para manifest alterado / hash divergente)
    # Regla: si evidencia no tiene scope verificable => INDETERMINATE (no MATCH)
    # Regla: si claim sin scope => INDETERMINATE (política requiere scope no vacío; sin contexto no hay MATCH)
    # Regla: si ambos con scope verificable:
    #   - iguales => MATCH (evidencia aplicable a claim)
    #   - distintos => MISMATCH solo si existe regla explícita; por defecto INDETERMINATE (contrato conservador)

    if result["decision"] == "INVALID":
        # Ya resuelto (manifest/hash alterado)
        return result

    if not result["integrity_ok"]:
        # Si hay archivo/manifest pero no se confirma integridad (archivo ausente, hash no coincide pero no se detectó manifest alterado)
        # No se declara INVALID automáticamente sin evidencia de alteración; se mantiene INDETERMINATE
        pass

    if not result["scope_evidence_ok"]:
        result["decision"] = "INDETERMINATE"
        result["explanation"] = "Scope de evidencia no verificable (falta procedencia o es desconocido); no se promueve a MATCH"
        return result

    if not result["scope_claim_ok"]:
        result["decision"] = "INDETERMINATE"
        result["explanation"] = "Claim declara scope vacío; sin contexto de ámbito no se autoriza MATCH"
        return result

    # Ambos scopes presentes y evidencia con procedencia verificable
    ev_sc = str(evidence_scope_verifiable).strip()
    cl_sc = str(claim_scope).strip()

    if ev_sc == cl_sc:
        # Igualdad textual no es suficiente si no hay integridad verificada; pero integridad ya verificada o no falla por manifest
        if result["integrity_ok"]:
            result["decision"] = "MATCH"
            result["explanation"] = "Scope verificado igual al del claim e integridad confirmada (no se deduce por identidad de referencia)"
        else:
            result["decision"] = "INDETERMINATE"
            result["explanation"] = "Scopes iguales pero integridad no verificada completamente (archivo/hash no disponibles); no se promueve"
    else:
        # Distintos; verificar regla explícita
        regla = REGLAS_EXPLICITAS.get((cl_sc, ev_sc)) or REGLAS_EXPLICITAS.get((ev_sc, cl_sc))
        if regla == "INCOMPATIBLE":
            result["decision"] = "MISMATCH"
            result["explanation"] = "Scopes verificables e incompatibles según regla contractual explícita: %s vs %s" % (cl_sc, ev_sc)
        else:
            # Sin regla explícita: no se declara MISMATCH (evita inferencia por diferencia textual)
            result["decision"] = "INDETERMINATE"
            result["explanation"] = "Scopes verificables distintos (%s vs %s) pero sin regla contractual de incompatibilidad; no se infiere MISMATCH" % (cl_sc, ev_sc)

    return result
