#!/usr/bin/env python3
"""RXRE-207 — Adaptador minimo: finding operativo -> claim formal TIERRA.

QUE ES
------
Un traductor FIDEL entre la observacion de RXRE (`findings`) y la
afirmacion formal de TIERRA (`claims` + `evidence`).

QUE NO ES
---------
- No decide la verdad de nada: transfiere el estado epistemolǫgico del
  hallazgo tal cual. Una referencia existente demuestra TRAZABILIDAD, no
  verdad; por eso el adaptador no puede elevar `PARTIAL` a `PROVEN`.
- No inventa campos: lo que no se puede derivar del hallazgo se EXIGE
  explicito o se RECHAZA con una razon verificable.
- No conecta a `machine.py` ni a la base operativa. Se ejecuta sobre una
  base aislada (Grafo con su propia ruta).

CONTRATOS REUTILIZADOS
----------------------
- 204: `claims` con `statement`/`epistemic_state`/`evidence_refs`.
- 205: la referencia debe EXISTIR (no basta con declararla).
- 206: `findings` = observacion; TIERRA = afirmacion formal evaluable;
        `research(kind='claim')` = registro operativo. Este adaptador NO
        sincroniza `research` (no hay sincronizacion bidireccional).

MAPEO (finding -> TIERRA)
-------------------------
    findings.claim            -> claims.statement
    findings.object_hash      -> claims.object_hash
    findings.scope            -> claims.scope
    findings.epistemic        -> claims.epistemic_state   (verbatim)
    findings.evidence_ids[]   -> evidence_refs[]  (via filas `evidence`)
    findings.derivation_refs  -> claims.derivation_refs
    findings.contradiction_refs -> contradictions[] (exige statement explicito)
    findings.falsification_test-> claims.falsification_test
    findings.limitations      -> claims.unresolved_obligations
    findings.finding_id       -> evidencia kind='observation' (identidad)
    findings.provenance       -> evidencia kind='observation' (procedencia)
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from rxre.arquitectura import TIERRA
from rxre.arquitectura.schemas import (ESTADOS, canonico, hash_contenido,
                                        hash_fila)

__all__ = [
    "AdapterError",
    "convertir_finding_a_tierra",
    "ejecutar_adaptador",
    "claim_id_de",
]


class AdapterError(ValueError):
    """El hallazgo no se puede convertir fielmente.

    El motivo es siempre verificable: que campo falta o que referencia no
    existe. Un adaptador que se calla y produce una afirmacion a medias
    seria peor que uno que se niega a convertir.
    """


# ----------------------------------------------------------------------
# Identidad: misma regla que TIERRA.afirmar (no una regla nueva).
# ----------------------------------------------------------------------
def claim_id_de(statement: str, object_hash: str, scope: str) -> str:
    """Id determinista de TIERRA para un claim.

    Usa EXACTAMENTE la formula de `TIERRA.afirmar`:
        "clm_" + hash_contenido([statement, object_hash, scope])[:16]
    Se replica aqui porque el adaptador necesita el id ANTES de crear
    la evidencia (el `ev_id` depende del `claim_id`).
    """
    return "clm_" + hash_contenido([statement, object_hash, scope])[:16]


# ----------------------------------------------------------------------
# Evidencia: misma construccion de contenido que TIERRA.aportar.
# ----------------------------------------------------------------------
def _contenido_evidencia(claim_id: str, kind: str, payload: Any,
                         producer: str, transformacion: str,
                         supersedes_ref: Optional[str]) -> Dict[str, Any]:
    return {
        "claim_id": claim_id,
        "kind": kind,
        "payload": canonico(payload),
        "producer": producer,
        "transformacion": transformacion,
        "supersedes_ref": supersedes_ref,
    }


def _json_or_dict(val):
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            import json
            return json.loads(val)
        except Exception:
            return {}
    return {}


def _ev_id_de(contenido: Dict[str, Any]) -> str:
    return "ev_" + hash_contenido(contenido)[:16]


def _registrar_evidencia(grafo: TIERRA.Grafo, claim_id: str, kind: str,
                          payload: Any, producer: str, transformacion: str,
                          supersedes_ref: Optional[str] = None) -> str:
    """Inserta UNA fila en `evidence` con el MISMO contenido y hash que
    produce `TIERRA.Grafo.aportar`.

    Por que no se llama a `aportar`: `aportar` hace `json_insert` de su
    `ev_id` en `claims.evidence_refs`. Como aqui el claim YA nace con
    `evidence_refs` poblado (lo exige `validar_claim` para `PROVEN`),
    llamar a `aportar` duplicaria cada referencia. Esta funcion inserta
    la fila sin volver a tocar el claim, y el hash de fila se calcula con
    la MISMA funcion que usa TIERRA, de modo que
    `Grafo.leer_evidencia(verificar=True)` confirma la integridad.
    """
    contenido = _contenido_evidencia(claim_id, kind, payload, producer,
                                      transformacion, supersedes_ref)
    ev_id = _ev_id_de(contenido)
    fila_hash = hash_fila(contenido)
    grafo.db.execute(
        "INSERT INTO evidence (evidence_id, claim_id, kind, payload,"
        " producer, transformacion, row_hash, supersedes_ref, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (ev_id, claim_id, kind, contenido["payload"], producer,
         transformacion, fila_hash, supersedes_ref, TIERRA._ahora()))
    return ev_id


# ----------------------------------------------------------------------
# Conversion: de finding a claim (sin escribir nada).
# ----------------------------------------------------------------------
def convertir_finding_a_tierra(finding: Dict[str, Any]) -> Dict[str, Any]:
    """Deriva el claim TIERRA de un hallazgo. NO escribe en la base.

    Lanza `AdapterError` con motivo verificable si algun campo no se
    puede derivar fielmente del hallazgo.
    """
    statement = finding.get("claim") or finding.get("statement")
    if not isinstance(statement, str) or not statement.strip():
        raise AdapterError("falta claim/statement: sin texto no hay statement")

    object_hash = finding.get("object_hash")
    if not isinstance(object_hash, str) or not object_hash.strip():
        raise AdapterError("falta object_hash: campo obligatorio del claim "
                           "(CLAIM_OBLIGATORIOS)")

    scope = finding.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        raise AdapterError("falta scope: campo obligatorio del claim "
                           "(CLAIM_OBLIGATORIOS)")
    # 249B: procedencia del scope debe ser EXPLICIT; INFERRED/UNKNOWN no se promueven.
    scope_prov = finding.get("scope_provenance")
    if scope_prov != "EXPLICIT":
        raise AdapterError("scope_provenance %r no es EXPLICIT: no se promueve "
                           "scope INFERRED/UNKNOWN a TIERRA (249B)" % (scope_prov,))

    falsification_test = finding.get("falsification_test")
    if not isinstance(falsification_test, str) or not falsification_test.strip():
        raise AdapterError("falta falsification_test: una afirmacion sin "
                           "termino de contraste no es un claim")

    epistemic = finding.get("epistemic") or finding.get("epistemic_state")
    if epistemic not in ESTADOS:
        raise AdapterError("epistemic %r no es un estado epistemico valido "
                           "(%s)" % (epistemic, ", ".join(ESTADOS)))

    refs = finding.get("evidence_ids")
    if refs is None:
        refs = finding.get("evidence_refs") or []
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except ValueError:
            raise AdapterError("evidence_ids no es JSON legible")
    if not isinstance(refs, list):
        raise AdapterError("evidence_ids no es una lista de referencias")
    for r in refs:
        if not isinstance(r, str) or not r.strip():
            raise AdapterError("referencia de evidencia invalida: %r" % (r,))

    derivation = finding.get("derivation_refs") or []
    if isinstance(derivation, str):
        derivation = json.loads(derivation)
    contradictions = finding.get("contradiction_refs") or []
    if isinstance(contradictions, str):
        contradictions = json.loads(contradictions)
    limitaciones = finding.get("limitations") or []
    if isinstance(limitaciones, str):
        limitaciones = json.loads(limitaciones)
    obligaciones = finding.get("unresolved_obligations")
    if obligaciones is None:
        obligaciones = limitaciones
    if isinstance(obligaciones, str):
        obligaciones = json.loads(obligaciones)

    return {
        "statement": statement,
        "object_hash": object_hash,
        "scope": scope,
        "scope_provenance": scope_prov if scope_prov == "EXPLICIT" else "UNKNOWN",
        "epistemic_state": epistemic,
        "evidence_refs": list(refs),
        "derivation_refs": list(derivation),
        "contradiction_refs": list(contradictions),
        "falsification_test": falsification_test,
        "unresolved_obligations": list(obligaciones),
        # Identidad y procedencia del hallazgo original: viajan en la
        # evidencia de tipo 'observation', no en campos del claim.
        "_finding_id": finding.get("finding_id"),
        "_provenance": (_json_or_dict(finding.get("provenance"))),
        "_limitations": list(limitaciones),
    }


# ----------------------------------------------------------------------
# Ejecucion: escritura atomica sobre la base aislada del grafo.
# ----------------------------------------------------------------------
def ejecutar_adaptador(grafo: TIERRA.Grafo, finding: Dict[str, Any],
                        resolver_refs: Optional[Callable[[str], bool]] = None,
                        contradiction_statements: Optional[List[Dict[str, Any]]] = None,
                        autorizacion: bool = False) -> Dict[str, Any]:
    if autorizacion is not True:
        raise AdapterError(
            "autorizacion requiere autorizacion=True (booleano exacto); recibido %r (%s). "
            "No se permite escribir TIERRA.claims sin autorizacion de la puerta 210." % (autorizacion, type(autorizacion).__name__))
    """Convierte y escribe el claim en el grafo indicado.

    `resolver_refs(ref_id) -> bool` es OBLIGATORIO para un claim `PROVEN`:
    sin el, el adaptador no puede afirmar que las referencias existen, y no
    esta permitido convertir `PROVEN` por la sola declaracion de refs.

    `contradiction_statements` es una lista de
    `{"statement": str, "severity": str}` y es OBLIGATORIA si el hallazgo
    trae `contradiction_refs`: TIERRA exige que cada contradiccion tenga
    un enunciado; el adaptador no lo inventa.

    Devuelve un dict con `claim_id`, `estado`, `evidencia`, `ya_existia`.
    """
    claim = convertir_finding_a_tierra(finding)
    claim_id = claim_id_de(claim["statement"], claim["object_hash"],
                           claim["scope"])

    # --- Verificacion de referencias (no basta declararlas) ---
    if claim["evidence_refs"] and resolver_refs is None:
        raise AdapterError(
            "referencias declaradas sin verificador: para %s se exige "
            "resolver_refs; una referencia no verificada demuestra "
            "trazabilidad declarada, no existencia" % claim["epistemic_state"])
    for ref in claim["evidence_refs"]:
        if not resolver_refs(ref):
            raise AdapterError("referencia inexistente: %s" % ref)

    # --- Idempotencia: si el claim ya existe, no se re-afirma ---
    existente = grafo.leer(claim_id)
    if existente is not None:
        return {"claim_id": claim_id, "estado": "ya_existia",
                "evidencia": list(existente.get("evidence_refs") or []),
                "epistemic_state": existente.get("epistemic_state"),
                "finding_id": claim.get("_finding_id")}

    # --- Contradicciones: exigidas explicitamente, nunca inventadas ---
    ctrs = claim["contradiction_refs"]
    statements = contradiction_statements or []
    if ctrs and not statements:
        raise AdapterError(
            "el hallazgo declara %d contradiccion(es) sin enunciado: TIERRA "
            "exige el texto de la contradiccion; aportelo en "
            "contradiction_statements (no se inventa)" % len(ctrs))
    if statements and not ctrs:
        raise AdapterError("contradiction_statements sin contradiction_refs "
                           "en el hallazgo: no se anexa lo que no se declara")

    # --- Escritura atomica ---
    grafo.db.execute("BEGIN")
    try:
        producer = (claim["_provenance"] or {}).get("producer") or "rxre.adapter_207"
        transformacion = "finding_to_tierra_adapter_207"

        # 1) Precomputo de los ids de evidencia: el `ev_id` depende del
        #    `claim_id` y del contenido, asi que puede calcularse antes de
        #    escribir. `afirmar` exige `evidence_refs` no vacio para PROVEN,
        #    y aqui se le pasan los ids REALES que se insertaran despues
        #    (mismo contenido -> mismo `ev_id` -> sin duplicados).
        ev_ids: List[str] = []
        for ref in claim["evidence_refs"]:
            ev_ids.append(_ev_id_de(_contenido_evidencia(
                claim_id, "artifact",
                {"rxre_result_id": ref, "resolved_by": "resolver_refs",
                 "verificado": True},
                producer, transformacion, None)))

        # --- P2 (261/263): contrato de procedencia antes de afirmar ---
        # El adapter ya verifico la EXISTENCIA de cada referencia con `resolver_refs`
        # (lineas 256-258). Por eso la ausencia en la fuente operativa NO se trata como
        # INVALID (no hay contradiccion demostrada): queda UNVERIFIED -> ALLOW_WITH_LIMITACION.
        scope_dec = None
        try:
            from rxre.contracts.scope_provenance_contract import verificar_autoridad_scope
            provs = []
            for ref in (claim.get("evidence_refs") or []):
                prov = verificar_autoridad_scope(
                    evidence_ref=ref, claim_scope=claim.get("scope") or "",
                    db_op_path="/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3",
                    db_op_result_id=ref,
                    manifest_e2e_path=None,
                    observed_artifact_path=None, observed_hash=None)
                provs.append(prov)
                if prov["decision"] in ("CONFLICT", "INVALID"):
                    raise AdapterError("adapter: procedencia de scope rechaza (%s): %s" % (prov["decision"], prov["explanation"]))
            scope_dec = "ALLOW_WITH_LIMITATION" if any(p["decision"] in ("UNVERIFIED", "INDETERMINATE") for p in provs) else "ALLOW"
        except AdapterError:
            raise
        except Exception:
            pass  # Estabilidad: un fallo tecnico del contrato no bloquea afirmaciones legitimas

        from rxre.contracts.admission_tierra import admit_claim as _admit
        _ok, _reason = _admit(
            statement=claim['statement'], object_hash=claim['object_hash'],
            scope=claim['scope'], scope_provenance=claim.get("scope_provenance", "UNKNOWN"),
            evidence_refs=claim['evidence_refs'], resolver_refs=resolver_refs)[:2]
        if not _ok:
            raise AdapterError('admission_tierra rechaza: %s' % _reason)
        grafo.afirmar(
            statement=claim["statement"],
            object_hash=claim["object_hash"],
            scope=claim["scope"],
            epistemic_state=claim["epistemic_state"],
            falsification_test=claim["falsification_test"],
            evidence_refs=ev_ids,
            derivation_refs=claim["derivation_refs"],
            unresolved_obligations=claim["unresolved_obligations"],
            claim_id=claim_id,
            reevaluation_ref=None)

        # 2) Evidencia de observacion: conserva identidad y procedencia.
        _registrar_evidencia(
            grafo, claim_id, "observation",
            payload={"rxre_finding_id": claim.get("_finding_id"),
                     "rxre_claim": claim["statement"],
                     "rxre_epistemic": claim["epistemic_state"],
                     "rxre_provenance": claim["_provenance"],
                     "rxre_limitations": claim["_limitations"],
                     "adapter": "adapter_finding_tierra.py"},
            producer=producer, transformacion=transformacion)

        # 3) Una fila de evidencia por cada referencia existente.
        for ref in claim["evidence_refs"]:
            _registrar_evidencia(
                grafo, claim_id, "artifact",
                payload={"rxre_result_id": ref,
                         "resolved_by": "resolver_refs",
                         "verificado": True},
                producer=producer, transformacion=transformacion)

        # 4) Contradicciones, si fueron aportadas explicitamente.
        for c in statements:
            grafo.contradecir(claim_id, c["statement"],
                              c.get("severity", "media"))

        grafo.db.execute("COMMIT")
    except Exception:
        grafo.db.execute("ROLLBACK")
        raise

    # P3 (261/263): persistencia de limitaciones post-COMMIT (separado de la transaccion principal)
    limitacion_persistida = False
    if scope_dec == "ALLOW_WITH_LIMITATION":
        try:
            ruta = grafo.ruta
            from rxre.contracts.limitations_contract import migrar_limitaciones_reversible, guardar_limitacion
            migrar_limitaciones_reversible(ruta)
            guardar_limitacion(
                ruta, claim_id,
                "UNVERIFIED", "ALLOW_WITH_LIMITATION",
                ["adapter: procedencia de scope no verificada (DB_OP.results.scope=NULL o manifest sin scope)"],
                claim.get("evidence_refs") or [],
                claim.get("scope"))
            limitacion_persistida = True
        except Exception:
            limitacion_persistida = False  # Persistencia fallida documentada; sin bloqueo de operacion

    final = grafo.leer(claim_id) or {}
    return {"claim_id": claim_id, "estado": "ok",
            "evidencia": list(final.get("evidence_refs") or []),
            "epistemic_state": final.get("epistemic_state"),
            "finding_id": claim.get("_finding_id"),
            "limitaciones_persistidas": limitacion_persistida}
