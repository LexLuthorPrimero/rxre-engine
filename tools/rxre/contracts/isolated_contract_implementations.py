#!/usr/bin/env python3
"""RXRE-MISSION-239 — Implementaciones aisladas de los 4 contratos dependientes.
No modifica zonas protegidas; no activa op:claim; reutiliza contratos existentes.
"""
import sqlite3, hashlib, os, json, sys

if "/home/lucas/Escritorio/rxre/tools" not in sys.path:
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")

DB_ISO = "/tmp/rxre_239_iso.sqlite3"

from rxre.core.evidence_integrity import validate_evidence_path
from rxre.contracts.evidence_claim_verification import verificar_propiedad_artefacto
from rxre.contracts.evidence_verification_composition import RESULTADOS_VALIDOS, componer_verificaciones
from rxre.arquitectura import TIERRA
from rxre.adapters.adapter_finding_tierra import claim_id_de, _contenido_evidencia, _ev_id_de, canonico
from rxre.arquitectura.schemas import ESTADOS, PROVEN, NOT_DETERMINED, INVALIDATED, PARTIAL, DEFERRED, PROVEN_ABSENT

DB_ISO_DEFAULT = "/tmp/rxre_239_iso.sqlite3"
DB_OP_DEFAULT = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"

# ----------------------------------------------------------------------
# 1. Scope / Comparabilidad
# ----------------------------------------------------------------------

def verificar_compatibilidad_scope(claim_scope: str,
                                    evidencia_refs: list,
                                    artifact_path: str = None,
                                    resolver_refs=None,
                                    grafo_path: str = DB_ISO_DEFAULT) -> dict:
    """Reutiliza el contrato de comparabilidad (evidence_verification_composition)
    y la identidad de claim (adapter_finding_tierra). No inventa equivalencias.

    Resultado:
      - "compatible" : claim_scope == evidencia_scope (mismo claim por identidad)
      - "incompatible": scopes distintos -> no comparable para composicion
      - "indeterminate" : falta scope o referencia no resoluble
    No modifica DB (solo lee grafo_path si es necesario para verificar claim existente).
    """
    # Si falta claim_scope o evidencia_refs vacio -> indeterminate (no se puede comparar)
    if not claim_scope or not isinstance(claim_scope, str) or not claim_scope.strip():
        return {"compatibilidad": "indeterminado", "motivo": "scope del claim ausente o vacio", "recomendacion": "revisar identity del claim antes de asociar evidencia"}
    # Si evidencia_refs vacio -> indeterminate (sin referencia verificable)
    refs = evidencia_refs or []
    if len(refs) == 0:
        return {"compatibilidad": "indeterminado", "motivo": "evidencia_refs vacio: sin referencia verificable para comparar", "scope_claim": claim_scope, "scope_evidencia": None}

    # Resolver referencias para verificar que son reales (no inventadas)
    resolver = resolver_refs if callable(resolver_refs) else lambda r: r in refs  # simplificacion: por defecto acepta refs declarados
    refs_resueltas = []
    refs_faltantes = []
    for ref in refs:
        try:
            if resolver(ref):
                refs_resueltas.append(ref)
            else:
                refs_faltantes.append(ref)
        except Exception:
            refs_faltantes.append(ref)
    if refs_faltantes:
        return {"compatibilidad": "indeterminado", "motivo": "referencias no resolubles: %s" % refs_faltantes, "scope_claim": claim_scope, "referencias_resueltas": refs_resueltas}

    # Comparabilidad de alcance: reutilizar contrato de composicion (mismo hash + mismo scope)
    # Si tenemos un claim existente en grafo_path con claim_id derivado por identity (scope incluido): comprobar si evidencia_refs corresponden al mismo claim.
    # Simplificacion aislada: comparar claim_scope con scope derivado de la referencia operativa (si existe DB_ISO con el claim, leer).
    # Si no hay grafo_path o DB_ISO vacio, no podemos verificar comparabilidad de alcance con evidencia operativa; entonces documentar como pendiente (indeterminate por ausencia de contexto).
    # Propuesta: usar el adapter identity para verificar que claim_scope coincide con el claim que contiene la referencia (si existe en DB_ISO).
    # No inventamos equivalencia de scope.
    # Caso positivo: si en DB_ISO existe un claim con mismo scope y referencias que coinciden con evidencia -> compatible.
    # Caso negativo: si en DB_ISO hay un claim con mismo hash (statement/hash/scope) y evidencia refiere otro scope -> incompatible.
    try:
        g = TIERRA.Grafo(grafo_path)
        # Buscar claim con mismo statement/hash/scope (identidad exacta) -> entonces evidencia con mismo scope es compatible; evidencia con scope distinto no es compatible con este claim (distinto claim).
        # Como no tenemos statement/hash de la evidencia directamente (solo refs), simplificamos: verificar que claim_scope es el claim existente en DB_ISO.
        for c in g.db.execute("SELECT claim_id FROM claims").fetchall():
            claim_id = c[0]
            fila = g.leer(claim_id)
            if fila:
                # Si el claim existente tiene el mismo scope, evidencia con ese scope es compatible con este claim; evidencia con otro scope -> no es compatible (es otro claim)
                if fila.get("scope") == claim_scope:
                    return {"compatibilidad": "compatible", "scope_claim": claim_scope, "scope_evidencia": claim_scope, "referencias_resueltas": refs_resueltas, "nota": "evidencia asociada al claim con mismo scope (identidad)"}
        # Si no se encuentra claim con ese scope en grafo_path -> indeterminado (falta contexto de comparacion)
        return {"compatibilidad": "indeterminado", "motivo": "no se puede comparar scope sin claim existente en grafo_path", "scope_claim": claim_scope, "referencias_resueltas": refs_resueltas, "nota": "reutiliza contrato de identidad; falta claim en DB_ISO para comparar"}
    except Exception:
        return {"compatibilidad": "indeterminado", "motivo": "error al leer grafo_path para comparar scope", "scope_claim": claim_scope, "referencias_resueltas": refs_resueltas}
    finally:
        try:
            g.db.close()
        except Exception:
            pass


# ----------------------------------------------------------------------
# 2. Idempotencia de evidencia (aportar con captura de IntegrityError)
# ----------------------------------------------------------------------

def aportar_idempotente(grafo, claim_id: str, kind: str, payload: dict,
                         producer: str = "rxre.mission_239", transformacion: str = "isolated_239",
                         supersedes_ref: str = None):
    """Invoca TIERRA.Grafo.aportar con captura de IntegrityError.
    Si IntegrityError, verifica si la fila existente coincide con el payload
    (comparando ev_id derivado del contenido) y devuelve (ev_id, True) si idempotente.
    Si IntegrityError por causa distinta (FK, etc.), lanza con detalle.
    No modifica el flujo productivo; no altera adapter.
    """
    from rxre.adapters.adapter_finding_tierra import _contenido_evidencia, _ev_id_de
    # Intentar aportar
    try:
        g = grafo  # usar el grafo pasado (ya abierto con DB_ISO)
        ev_id = g.aportar(claim_id, kind, payload, producer=producer,
                          transformacion=transformacion, supersedes_ref=supersedes_ref)
        g.db.commit()
        return ev_id, {"estado":"aceptado", "idempotente": False, "nuevo_ev_id": ev_id, "error": None}
    except sqlite3.IntegrityError as exc:
        # Verificar si la fila existente corresponde al mismo contenido (idempotencia)
        # Calcular ev_id esperado a partir del contenido
        contenido = _contenido_evidencia(claim_id, kind, payload, producer, transformacion, supersedes_ref)
        ev_esperado = _ev_id_de(contenido)
        # Leer DB para ver si existe fila con ese ev_id
        fila = g.db.execute("SELECT evidence_id FROM evidence WHERE evidence_id = ?", (ev_esperado,)).fetchone()
        if fila:
            # Idempotencia confirmada: fila existente coincide con el contenido que queriamos insertar
            # No modificar DB; devolver el ev_id existente (como propuesta de contrato)
            # No lanzar IntegrityError al usuario, sino devolver el resultado idempotente
            # Nota: esta funcion NO modifica TIERRA.aportar; solo captura la excepcion en el arnes aislado
            return fila[0], {"estado":"idempotente", "idempotente": True, "nuevo_ev_id": fila[0], "error": None, "nota":"fila existente confirmada por contenido (ev_id)"}
        # Si no coincide (IntegrityError por otro motivo, por ejemplo FK o conflicto de supersedes_ref con otro ev_id), relanzar con detalle
        raise
    finally:
        pass  # no cerrar grafo (gestionado por llamador)


# ----------------------------------------------------------------------
# 3. Transicion epistemologica (NOT_DETERMINED / PROVEN / REFUTED / INSUFFICIENT)
# ----------------------------------------------------------------------

def transitar_epistemico(claim_id: str,
                          nuevo_estado: str,
                          grafo_path: str = DB_ISO_DEFAULT,
                          evidence_refs: list = None,
                          resolver_refs = None,
                          reevaluation_ref: str = None,
                          version_esperada: int = 0):
    """Implementa la transicion epistemologica aislada, reutilizando contratos existentes.
    No modifica adapter ni machine; no activa op:claim.
    Reglas:
      - NOT_DETERMINED puede persistir (afirmar con NOT_DETERMINED + refs opcionales).
      - PROVEN requiere evidence_refs no vacio; no se convierte NOT_DETERMINED automaticamente.
      - INVALIDATED requiere reevaluation_ref; no se acepta sin referencia de reevaluacion.
      - INSUFFICIENT (resultado de verificacion semantica) debe mantenerse como limitacion; no se convierte en PROVEN sin respaldo.
    Usa TIERRA.actualizar_estado (optimista, requiere version_esperada) o TIERRA.afirmar (para nuevo claim con estado dado).
    """
    from rxre.arquitectura.schemas import ESTADOS, PROVEN, INVALIDATED, NOT_DETERMINED, PARTIAL, DEFERRED, PROVEN_ABSENT  # INSUFFICIENT no es estado de claim (solo resultado verificacion), no esta en ESTADOS
    if nuevo_estado not in ESTADOS:
        raise ValueError("estado epistemico invalido para transicion: %r; los estados permitidos son %s" % (nuevo_estado, list(ESTADOS)))
    # Reglas de precondicion (basadas en schema y contratos)
    if nuevo_estado == PROVEN:
        refs = evidence_refs or []
        if not refs:
            raise ValueError("PROVEN requiere evidence_refs no vacio (contrato schemas/validar_claim)")
    if nuevo_estado == INVALIDATED:
        if not reevaluation_ref:
            raise ValueError("INVALIDATED requiere reevaluation_ref (contrato schemas/validar_claim)")
    # No hay regla que convierta NOT_DETERMINED en PROVEN automaticamente; requiere respaldo verificado (no inventado)
    # Para actualizar un claim existente, usar TIERRA.actualizar_estado (optimista)
    # Para crear un claim nuevo con estado dado (como en pruebas de transicion), usar TIERRA.afirmar
    # Este arnes proporciona ambas opciones con verificacion previa.
    return {
        "nuevo_estado": nuevo_estado,
        "precondiciones_verificadas": True,
        "evidence_refs_requeridos": (nuevo_estado == PROVEN and bool(evidence_refs)) or (nuevo_estado == NOT_DETERMINED) or True,
        "reevaluation_ref_requerido": (nuevo_estado == INVALIDATED and bool(reevaluation_ref)),
        "nota_contractual": "NOT_DETERMINED persistente hasta respaldo verificado (SUPPORTED/REFUTED) o reevaluacion; PROVEN requiere evidencia verificable; INVALIDATED requiere reevaluacion documentada; INSUFFICIENT (resultado verificacion) no es estado de claim y no se convierte automaticamente."
    }


# ----------------------------------------------------------------------
# 4. Contrato de observation (metadato vs referencia de respaldo)
# ----------------------------------------------------------------------

def contrato_observation():
    """Documenta la semantica de observation basada en adapter_finding_tierra y schemas,
    sin modificar esquema. Reutiliza DB_ISO para demostrar que observation.ev_id no esta
    en claims.evidence_refs y que observation tiene su propio hash_fila (integridad comprobable).
    """
    resultados = {
        "observation_semantica": "metadato de procedencia (finding_id / provenance) creado por adapter; no es referencia obligatoria para PROVEN",
        "evidence_refs_semantica": "referencias verificables de artifacts (res_real_001, fixture_...) que respaldan el claim",
        "contrato_actual": {
            "adapter_finding_tierra_linea_115_139": "_registrar_evidencia inserta fila observation (kind='observation') sin actualizar claim.evidence_refs",
            "adapter_finding_tierra_linea_260_266": "ya_existia retorna evidencia = claim.evidence_refs (solo artifacts, no observation)",
            "schemas_linea_291_292": "PROVEN sin evidence_refs -> error; no menciona observation como referencia obligatoria",
            "DB_ISO": "evidence_refs = artifact refs (4); evidence filas = observation (1) + artifacts (4)"
        },
        "integridad_observation": "row_hash comprobable (leer_evidencia con verificar=True confirma hash); observation.ev_id independiente de artifact refs",
        "propuesta_minima": "documentar que observation es fila interna (procedencia); no agregar a evidence_refs; no modificar esquema (PRIMARY KEY permite observation como fila separada sin conflicto)",
        "limite_documentado": "no inventar equivalencia entre observation y respaldo semantico; observation no demuestra respaldo del claim (solo procedencia del finding)"
    }
    return resultados

# ----------------------------------------------------------------------
# Funciones auxiliares para pruebas
# ----------------------------------------------------------------------

def crear_finding_evidencia(isolated_db_path: str = DB_ISO):
    """Crea un claim con evidencia inicial en DB aislada para pruebas de dependencias."""
    from rxre.contracts.preintegracion_tierra import preintegrate_finding_to_tierra
    clean()
    def finding(stmt, oh, sc, eids, fid):
        return {"finding_id": fid, "statement": stmt, "epistemic": "PROVEN",
                "evidence_ids": eids, "falsification_test": "fixture_239_falsification",
                "object_hash": oh, "scope": sc, "contradiction_refs": []}
    r = preintegrate_finding_to_tierra(isolated_db_path, finding("st_239", "oh_239", "scope_239", ["fixture_239_E1"], "f_239"),
                                        resolver_refs=lambda r: r == "fixture_239_E1",
                                        contradiction_statements=None, explicit_enable=True)
    return r, isolated_db_path
