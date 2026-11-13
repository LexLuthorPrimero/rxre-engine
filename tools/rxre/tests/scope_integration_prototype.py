#!/usr/bin/env python3
"""RXRE-MISSION-255 — PROTOTIPO DE INTEGRACION DE SCOPE (SOLO PRUEBA, AISLADO).

NO es codigo productivo: no se importa desde machine.py, semantic_verification_chain,
adaptadores ni core. Su unico proposito es demostrar, sobre el flujo real de
`op:claim` (handler de machine.py) y sobre fixtures aislados, como se comportaria
una integracion de los contratos de procedencia (252/253) con la politica
conservadora C (scope indeterminado hasta que exista productor autoritativo).

No escribe en DB_OP: todas las lecturas son `mode=ro`. Escribe unicamente en la
base aislada que recibe el llamador (DB_ISO de prueba).
"""
import os
import sys

sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
from rxre.contracts.evidence_scope_contract import vincular_evidencia_claim

# Politica C (provisional): el scope permanece indeterminado mientras no exista
# productor autoritativo. Por tanto:
#   INVALID / CONFLICT  -> REJECT (bloquea; evidencia o vinculo invalido/contradictorio)
#   UNVERIFIED          -> ALLOW_WITH_LIMITATION (no se afirma MATCH ni compatibilidad;
#                           se registra limitacion; NO se usa como prueba de compatibilidad)
#   VERIFIED + MATCH    -> ALLOW (scope verificado e in-scope)
FLUJO = {
    "INVALID": "REJECT",
    "CONFLICT": "REJECT",
    "UNVERIFIED": "ALLOW_WITH_LIMITATION",
    "MATCH": "ALLOW",
    "INDETERMINATE": "ALLOW_WITH_LIMITATION",
}


def evaluar_scope_para_claim(
    finding_dict: dict,
    evidence_refs: list,
    db_op_path: str,
    manifest_by_ref: dict = None,
    observed_artifact_path: str = None,
    observed_hash: str = None,
) -> dict:
    """Devuelve: decision de contrato (agregada), decision de flujo, limitaciones y detalle por evidencia."""
    manifest_by_ref = manifest_by_ref or {}
    claim_scope = (finding_dict or {}).get("scope")
    detalles = []
    limitaciones = []
    peor = None
    peor_contrato = None
    orden = {"ALLOW": 0, "ALLOW_WITH_LIMITATION": 1, "REJECT": 2}
    orden_contrato = {"MATCH": 0, "UNVERIFIED": 1, "INDETERMINATE": 1, "CONFLICT": 2, "INVALID": 2}

    for ref in evidence_refs or []:
        prov = verificar_autoridad_scope(
            evidence_ref=ref,
            claim_scope=claim_scope,
            db_op_path=db_op_path,
            db_op_result_id=ref,
            manifest_e2e_path=manifest_by_ref.get(ref),
            observed_artifact_path=observed_artifact_path,
            observed_hash=observed_hash,
        )
        if prov["decision"] == "VERIFIED":
            vinc = vincular_evidencia_claim(
                evidence_ref=ref,
                evidence_path=observed_artifact_path,
                evidence_hash=observed_hash,
                evidence_scope_verifiable=prov["sources"]["db_op"]["scope"] or prov["sources"]["manifest"]["scope"],
                claim_scope=claim_scope,
            )
            contrato = vinc["decision"] if vinc["decision"] in ("MATCH", "MISMATCH", "INVALID") else prov["decision"]
            detalle = {
                "ref": ref,
                "procedencia": prov["decision"],
                "contrato": contrato,
                "explicacion": vinc["explanation"] if contrato != prov["decision"] else prov["explanation"],
            }
            if contrato == "INVALID":
                contrato = "INVALID"
        else:
            contrato = prov["decision"]
            detalle = {"ref": ref, "procedencia": prov["decision"], "contrato": contrato, "explicacion": prov["explanation"]}

        flujo = FLUJO.get(contrato, "ALLOW_WITH_LIMITATION")
        detalle["flujo"] = flujo
        detalles.append(detalle)
        if peor is None or orden[flujo] > orden[peor]:
            peor = flujo
        if peor_contrato is None or orden_contrato.get(contrato, 99) > orden_contrato.get(peor_contrato, 99):
            peor_contrato = contrato
        if flujo != "ALLOW":
            limitaciones.append("%s: %s (%s)" % (ref, contrato, detalle["explicacion"][:120]))

    if peor is None:
        peor = "ALLOW_WITH_LIMITATION"
        peor_contrato = "INDETERMINATE"
        limitaciones.append("sin referencias de evidencia: scope no evaluable")

    return {
        "contrato": peor_contrato,
        "flujo": peor,
        "claim_scope": claim_scope,
        "detalle": detalles,
        "limitaciones": limitaciones,
        "persiste_permitido": peor != "REJECT",
    }
