#!/usr/bin/env python3
"""RXRE-MISSION-256 — FLUJO GUARDADO (aislado, contrato de integracion). NO integrado en machine.py, core/store.py, adaptadores productivos.

Reutiliza contratos 252/253/254 y 255. No escribe en DB_OP. Usa lectura `mode=ro`.
Política C: `VERIFIED`/`MATCH` => ALLOW; `UNVERIFIED`/`INDETERMINATE` => ALLOW_WITH_LIMITATION
(no se afirma `COMPATIBLE` ni `PROVEN`); `CONFLICT`/`INVALID` => REJECT.
"""
import sys, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
from rxre.contracts.evidence_scope_contract import vincular_evidencia_claim

# Mapeo de decisiones del contrato a decisiones del flujo guardado (política C provisoria)
MAP = {"MATCH": "ALLOW", "UNVERIFIED": "ALLOW_WITH_LIMITATION",
       "INDETERMINATE": "ALLOW_WITH_LIMITATION", "MISMATCH": "REJECT",
       "CONFLICT": "REJECT", "INVALID": "REJECT"}

def evaluar_guardado(evidence_refs, claim_scope, db_op_path, manifest_by_ref, art_path, art_hash,
                     refs_verificados_por_llamador=False):
    """`refs_verificados_por_llamador=True`: el llamador ya verifico la EXISTENCIA de cada
    referencia con su propio verificador (`resolver_refs`). En ese caso una referencia que no
    aparece en la fuente operativa NO es INVALID (no hay contradiccion demostrada): queda
    UNVERIFIED -> ALLOW_WITH_LIMITACION. Nunca se convierte en MATCH.
    """
    decisiones = []
    peor = "ALLOW_WITH_LIMITATION"
    orden = {"ALLOW": 0, "ALLOW_WITH_LIMITATION": 1, "REJECT": 2}
    for ref in (evidence_refs or []):
        # Precondición: la referencia debe ser resoluble (registro operativo o manifest).
        # Referencia no resoluble => INVALID (bloquea antes de cualquier escritura).
        resoluble = False
        try:
            import sqlite3
            if db_op_path and os.path.isfile(db_op_path):
                con = sqlite3.connect("file:%s?mode=ro" % db_op_path, uri=True)
                row = con.execute("SELECT result_id FROM results WHERE result_id=? LIMIT 1", (ref,)).fetchone()
                con.close()
                resoluble = row is not None
        except Exception:
            resoluble = False
        mf = (manifest_by_ref or {}).get(ref)
        if mf and os.path.isfile(mf):
            resoluble = True
        if not resoluble:
            if refs_verificados_por_llamador:
                # Existencia ya verificada por el llamador; la ausencia en la fuente operativa
                # no prueba contradiccion: queda sin autoridad verificable (UNVERIFIED).
                decisiones.append({"ref": ref, "contrato": "UNVERIFIED", "flujo": "ALLOW_WITH_LIMITATION",
                                   "prov": "referencia verificada por el llamador; sin fuente operativa de scope"})
                continue
            decisiones.append({"ref": ref, "contrato": "INVALID", "flujo": "REJECT",
                               "prov": "referencia no resoluble"})
            continue
        prov = verificar_autoridad_scope(
            evidence_ref=ref, claim_scope=claim_scope,
            db_op_path=db_op_path, db_op_result_id=ref,
            manifest_e2e_path=manifest_by_ref.get(ref) if manifest_by_ref else None,
            observed_artifact_path=art_path, observed_hash=art_hash)
        # Integridad independiente (si hay archivo + hash y no coincide => INVALID inmediato)
        # El contrato de integridad se verifica independientemente
        contrato_dec = prov["decision"]
        # Vinculo evidencia-claim (scope + integridad) para casos donde proviene verificado
        if contrato_dec == "VERIFIED" and art_path:
            vinc = vincular_evidencia_claim(
                evidence_ref=ref, evidence_path=art_path, evidence_hash=art_hash,
                evidence_scope_verifiable=prov["sources"].get("db_op",{}).get("scope") or prov["sources"].get("manifest",{}).get("scope"),
                claim_scope=claim_scope)
            if vinc["decision"] == "MISMATCH":
                contrato_dec = "MISMATCH"
            elif vinc["decision"] == "INVALID":
                contrato_dec = "INVALID"
            elif vinc["decision"] == "MATCH":
                contrato_dec = "MATCH"
        flujo = MAP.get(contrato_dec, "ALLOW_WITH_LIMITATION")
        decisiones.append({"ref": ref, "contrato": contrato_dec, "flujo": flujo,
                           "prov": prov["decision"]})
        if orden.get(flujo, 99) > orden.get(peor, 99):
            peor = flujo
    # Aggregate: REJECT > ALLOW > ALLOW_WITH_LIMITATION
    flujos_obs = [d["flujo"] for d in decisiones]
    if any(f == "REJECT" for f in flujos_obs):
        peor = "REJECT"
    elif any(f == "ALLOW" for f in flujos_obs):
        peor = "ALLOW"
    else:
        peor = "ALLOW_WITH_LIMITATION"
    return peor, decisiones
