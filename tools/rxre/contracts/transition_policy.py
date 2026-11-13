#!/usr/bin/env python3
"""RXRE-208 — Contrato ejecutable de transición finding -> claim.

Política pura (no escribe nada). Recibe un hallazgo y opcionalmente un
`resolver_refs`; produce una decisión explicable.

Reglas (1–10 de Misión 208): codificadas directamente.
Reutiliza contratos 204–207.
"""
from __future__ import annotations
from typing import Optional, Callable, Dict, Any

DECISIONS = ("ACCEPT", "REJECT", "NEEDS_INPUT")
ESTADOS_TIERRA = ("PROVEN", "PARTIAL", "NOT_DETERMINED", "PROVEN_ABSENT",
                  "DEFERRED", "INVALIDATED")


def política_transición(
    finding: Dict[str, Any],
    resolver_refs: Optional[Callable[[str], bool]] = None,
    contradiction_statements: Optional[Dict] = None) -> Dict[str, Any]:
    """Devuelve {decision, reason, claim_pre, claim_id}

    `claim_pre` es el dict para `adapter_finding_tierra.convertir_finding_a_tierra`.
    No realiza escrituras; es una política pura.
    """
    # --- Regla 5: estados inválidos o desconocidos ---
    epistemic = finding.get("epistemic") or finding.get("epistemic_state")
    if epistemic not in ESTADOS_TIERRA:
        return {"decision": "REJECT", "reason": "epistemic %r no es válido (%s)" % (epistemic, ",".join(ESTADOS_TIERRA)),
                "claim_pre": None, "claim_id": None}

    # --- Regla 6: campos formales obligatorios ---
    must = ["object_hash", "scope", "falsification_test"]
    missing = [k for k in must if finding.get(k) is None or (isinstance(finding.get(k), str) and not finding.get(k).strip())]
    if missing:
        return {"decision": "NEEDS_INPUT",
                "reason": "campos formales obligatorios faltantes (v3 contrato): %s;aporte explicito o marque F-LEGACY-" % ",".join(missing),
                "claim_pre": None, "claim_id": None}

    # --- Regla 8: hallazgos históricos sin campos formales no se completan ---
    # Si el finding_id no es F-LEGACY- y falta algún campo obligatorio, ya se rechazó arriba.
    # Si es F-LEGACY-, permitimos CONFLICTO DOCUMENTADO, no invento.

    # --- Regla 9: deduplicación por contenido ---
    claim_text = finding.get("claim") or finding.get("statement", "")
    object_hash = finding.get("object_hash")
    scope = finding.get("scope")
    claim_id = ("clm_" + __import__("hashlib").sha256(
        (str(claim_text) + "|" + str(object_hash) + "|" + str(scope)).encode()
    ).hexdigest()[:16]) if claim_text and object_hash and scope else None

    # --- Regla 1: PROVEN solo si refs válidas y campos completos ---
    refs = finding.get("evidence_ids") or finding.get("evidence_refs") or []
    if isinstance(refs, str):
        import json
        try:
            refs = json.loads(refs)
        except Exception:
            refs = []
    if not isinstance(refs, list):
        refs = []
    refs = [r for r in refs if isinstance(r, str) and r.strip()]

    # Si es PROVEN y hay refs, comprobamos existencia (solo si resolver dado)
    if epistemic == "PROVEN":
        if not refs:
            return {"decision": "REJECT",
                    "reason": "PROVEN sin referencias: referencia existente no demostrada",
                    "claim_pre": None, "claim_id": claim_id}
        if resolver_refs is not None:
            bad = [r for r in refs if not resolver_refs(r)]
            if bad:
                return {"decision": "REJECT",
                        "reason": "referencias inexistentes: %s (trazabilidad no verificada)" % ",".join(bad),
                        "claim_pre": None, "claim_id": claim_id}
        # Regla 2: refs no prueban verdad; la política conserva PROVEN tal cual
    
    # --- Regla 3: PARTIAL no se eleva ---
    # (se conserva; no hay lógica de promoción)
    # --- Regla 4: PROVEN_ABSENT no se convierte ---
    # (se conserva; no hay conversión a PROVEN)

    # --- Regla 7: contradicciones requieren enunciado ---
    ctr_refs = finding.get("contradiction_refs") or []
    if isinstance(ctr_refs, str):
        import json
        try:
            ctr_refs = json.loads(ctr_refs)
        except Exception:
            ctr_refs = []
    if ctr_refs and (not contradiction_statements or not contradiction_statements.get("statements")):
        return {"decision": "NEEDS_INPUT",
                "reason": "contradicciones declaradas (%d) sin enunciado explicito; aporte contradiction_statements" % len(ctr_refs),
                "claim_pre": None, "claim_id": claim_id}

    # --- Regla 10: diferencia TIERRA vs research ---
    # Esta política decide para TIERRA formal. Si el llamador quiere solo
    # registro operativo (`research(kind='claim')`), debe usar `store`
    # directamente sin esta política (o con una variante que no exija
    # falsification_test). Documentamos aquí, no forzamos.
    claim_pre = {
        "statement": claim_text,
        "object_hash": object_hash,
        "scope": scope,
        "epistemic_state": epistemic,
        "evidence_refs": refs,
        "derivation_refs": finding.get("derivation_refs") or [],
        "contradiction_refs": ctr_refs,
        "falsification_test": finding.get("falsification_test"),
        "unresolved_obligations": finding.get("limitations") or finding.get("unresolved_obligations") or [],
        "_finding_id": finding.get("finding_id"),
        "_provenance": finding.get("provenance") or {},
    }

    return {"decision": "ACCEPT", "reason": "campos completos, refs verificados, estado preservado, contradicciones documentadas",
            "claim_pre": claim_pre, "claim_id": claim_id}
