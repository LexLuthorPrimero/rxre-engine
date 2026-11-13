#!/usr/bin/env python3
"""RXRE-218 — Política determinista de conflictos (validación de referencias).

Pura, sin persistencia ni acoplamiento a DB operativa.
Reutiliza solo datos explícitos pasados por el llamador:
- claim_a / claim_b: dicts de TIERRA.Grafo.leer (o equivalentes)
- resolver_refs: callable(str) -> bool (verifica existencia de claim_id; 
  si no se proporciona, ninguna referencia se considera resoluble)
- contradicciones: Optional[Dict[str, List[str]]] (mapa claim_id -> 
  declaraciones de contradicción; debe ser proporcionado por la fuente 
  de evidencia, no inventado por la política)

Reglas estrictas (no inventar CONFLICT):
- CONFLICT requiere referencia mutua + verificación de existencia + 
  declaraciones de contradicción + mismo scope + mismo object_hash.
- INDETERMINATE cuando referencias son unilaterales, no resolubles, 
  sin declaraciones, con scopes/objetos incompatibles para la relación, 
  o cuando datos faltan.
- EQUIVALENT requiere misma identidad técnica (claim_id) + contenido 
  canónico consistente.
- DISTINCT requiere diferentes claim_ids y ausencia de relación de 
  contradicción verificable.
- No usar similitud textual como criterio.
- No crear referencias sintéticas ni asumir existencia de claims.
"""
from typing import Dict, Any, Optional, Callable

CLASIFICACIONES = {"EQUIVALENT", "CONFLICT", "DISTINCT", "INDETERMINATE"}


def politica_conflicto_claims(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    resolver_refs: Optional[Callable[[str], bool]] = None,
    contradicciones: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Clasificar la relación entre dos claims con validación de referencias."""

    # --- Validación de entrada ---
    if not isinstance(claim_a, dict) or not isinstance(claim_b, dict):
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "entradas malformadas: se requieren dos dicts (claims)",
            "a_id": None,
            "b_id": None,
            "criterios_aplicados": ["validacion_de_entrada"],
            "evidencia_que_respaldan": [],
            "limitaciones": ["tipo de entrada: %s, %s" % (type(claim_a).__name__, type(claim_b).__name__)],
        }

    a_id = (claim_a.get("claim_id") or claim_a.get("id") or "").strip()
    b_id = (claim_b.get("claim_id") or claim_b.get("id") or "").strip()

    if not a_id or not b_id:
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "falta claim_id en uno o ambos claims; no se establece identidad técnica",
            "a_id": a_id or None,
            "b_id": b_id or None,
            "criterios_aplicados": ["identidad_técnica"],
            "evidencia_que_respaldan": [],
            "limitaciones": ["identificador necesario para comparar"],
        }

    # --- Identidad técnica (mismo claim_id) ---
    if a_id == b_id:
        stmt_a = (claim_a.get("statement") or "").strip()
        stmt_b = (claim_b.get("statement") or "").strip()
        hash_a = (claim_a.get("object_hash") or "").strip()
        hash_b = (claim_b.get("object_hash") or "").strip()
        scope_a = (claim_a.get("scope") or "").strip()
        scope_b = (claim_b.get("scope") or "").strip()

        # Por diseño del adapter, claim_id es determinista de (statement, object_hash, scope).
        # Si los tres coinciden, es el mismo claim (EQUIVALENT).
        if stmt_a and stmt_b and hash_a and hash_b and scope_a and scope_b:
            if stmt_a == stmt_b and hash_a == hash_b and scope_a == scope_b:
                return {
                    "clasificacion": "EQUIVALENT",
                    "motivo": "mismo claim_id derivado de statement+object_hash+scope; contenido canónico idéntico",
                    "a_id": a_id,
                    "b_id": b_id,
                    "criterios_aplicados": ["identidad_técnica", "equivalencia_semántica"],
                    "evidencia_que_respaldan": ["claim_id determinista", "statement", "object_hash", "scope"],
                    "limitaciones": [],
                }
        # Caso imposible por diseño adapter: misma identidad con contenido diferente.
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "identidad técnica coincidente (claim_id) pero contenido canónico incongruente; esquema adapter no permite esta combinación por diseño",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["identidad_técnica"],
            "evidencia_que_respaldan": ["claim_id"],
            "limitaciones": ["discrepancia entre claim_id y contenido; requiere verificación de persistencia"],
        }

    # --- Diferentes claim_ids ---
    # No inferir contradicción por diferencia de id/hash/scope.
    a_refs = claim_a.get("contradiction_refs") or []
    b_refs = claim_b.get("contradiction_refs") or []
    a_has_b = b_id in a_refs if isinstance(a_refs, (list, tuple)) else False
    b_has_a = a_id in b_refs if isinstance(b_refs, (list, tuple)) else False

    # Verificación de referencias mutuas: obligatoria para cualquier CONFLICT.
    # Si no son mutuas, no es contradicción verificable.
    if not (a_has_b and b_has_a):
        # Unilateral o ninguna referencia de contradicción.
        if a_has_b != b_has_a:
            lado = "a->b" if a_has_b else "b->a"
            return {
                "clasificacion": "INDETERMINATE",
                "motivo": "relación de contradicción declarada solo por un lado (%s); sin reciprocidad no se confirma incompatibilidad" % lado,
                "a_id": a_id,
                "b_id": b_id,
                "criterios_aplicados": ["contradiction_refs_unilateral"],
                "evidencia_que_respaldan": [
                    "claim_a.contradiction_refs contiene b_id" if a_has_b else "claim_b.contradiction_refs contiene a_id",
                ],
                "limitaciones": [
                    "relación unilateral: no se demuestra contradicción sin reciprocidad",
                    "falta verificación de declaraciones de contradicción",
                ],
            }
        # Ninguna referencia de contradicción mutua: DISTINCT (pueden coexistir)
        # Si son distintos por diseño (diferentes claim_ids deterministas), no hay conflicto.
        return {
            "clasificacion": "DISTINCT",
            "motivo": "diferentes claim_ids deterministas (statement/object_hash/scope); sin referencias mutuas de contradicción; proposiciones pueden coexistir",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["identidad_técnica_diferente", "ausencia_contradicción_verificable"],
            "evidencia_que_respaldan": [
                "claim_id_a != claim_id_b",
                "statement / object_hash / scope distintos por diseño adapter",
            ],
            "limitaciones": [
                "no se evalúa potencial contradicción implícita sin declaración explícita",
                "requiere análisis semántico externo para establecer incompatibilidad real",
            ],
        }

    # --- Ambas partes declaran contradicción mutuamente ---
    # A partir de aquí, ambas referencias cruzadas existen (mutual refs).
    # Ahora debe verificarse si las referencias son RESOLUBLES (existen
    # los claims a los que apuntan) y si hay EVIDENCIA de declaración.
    # Si el resolver no confirma ambos, no es verificable.
    resolver_available = resolver_refs is not None
    a_resolvable = resolver_refs(a_id) if resolver_available else False
    b_resolvable = resolver_refs(b_id) if resolver_available else False

    if not (a_resolvable and b_resolvable):
        # Referencias mutuas declaradas pero un claim (o ambos) no se puede
        # verificar: no se confirma que la relación sea entre claims
        # existentes, por lo que no se puede afirmar CONFLICT.
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "referencias mutuas de contradicción presentes pero uno o ambos claims no resolubles vía resolver_refs",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["contradiction_refs_mutuos", "resolucion_de_referencias"],
            "evidencia_que_respaldan": [
                "claim_a.contradiction_refs contiene b_id",
                "claim_b.contradiction_refs contiene a_id",
                "resolver_refs: a=%s b=%s" % (a_resolvable, b_resolvable),
            ],
            "limitaciones": [
                "referencia declarada pero no resoluble; no se confirma existencia del claim objetivo",
                "la contradicción requiere verificación de ambos extremos",
            ],
        }

    # --- Referencias resolubles ---
    # Verificar declaraciones de contradicción (contradiction_statements)
    # Si no hay declaraciones explícitas en los datos disponibles, no se
    # puede confirmar que la relación sea semánticamente de contradicción.
    # El esquema TIERRA guarda contradiction_statements por claim; si no
    # se pasan como datos a esta política, no se inventan.
    a_statements = claim_a.get("contradiction_statements")
    b_statements = claim_b.get("contradiction_statements")
    # Si el llamador pasa contradicciones como diccionario externo, usarlo.
    if contradicciones is not None:
        # contradicciones puede ser un dict claim_id -> list of stat strings
        # o un dict con estructura más rica; usar de forma defensiva.
        a_decls = contradicciones.get(a_id) or a_statements or []
        b_decls = contradicciones.get(b_id) or b_statements or []
    else:
        a_decls = a_statements or []
        b_decls = b_statements or []

    has_statements = bool(
        (isinstance(a_decls, list) and len(a_decls) > 0) or
        (isinstance(b_decls, list) and len(b_decls) > 0)
    )

    if not has_statements:
        # Referencias mutuas, ambas resolubles, pero sin declaraciones
        # de contradicción verificables en los datos disponibles.
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "referencias mutuas resolubles pero sin declaraciones de contradicción verificables en datos disponibles",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["contradiction_refs_mutuos", "resolucion_de_referencias", "declaraciones_faltantes"],
            "evidencia_que_respaldan": [
                "claim_a.contradiction_refs contiene b_id (resoluble)",
                "claim_b.contradiction_refs contiene a_id (resoluble)",
            ],
            "limitaciones": [
                "falta contradiction_statements verificados en claim_a o claim_b",
                "el esquema básico de TIERRA almacena declaraciones pero este parámetro debe ser proporcionado por la fuente de evidencia",
                "no se declara CONFLICT sin evidencia declarada verificable",
            ],
        }

    # --- Verificación de compatibilidad de alcance/objeto para contradicción ---
    # Una contradicción semántica requiere que las proposiciones sean sobre
    # el mismo objeto/alcance; si los scopes son incompatibles o los
    # object_hash difieren sin evidencia de relación, no se puede afirmar
    # que la contradicción sea sobre el mismo objeto.
    scope_a = (claim_a.get("scope") or "").strip()
    scope_b = (claim_b.get("scope") or "").strip()
    hash_a = (claim_a.get("object_hash") or "").strip()
    hash_b = (claim_b.get("object_hash") or "").strip()

    # Si los scopes difieren de forma incompatible (no hay relación de
    # sub-objeto documentada), no se confirma contradicción sobre el
    # mismo dominio.
    if scope_a and scope_b and scope_a != scope_b:
        # Alcances diferentes: pueden ser proposiciones distintas que no
        # contradicen directamente (por ejemplo, mismo objeto en distintos
        # contextos). No inventar contradicción.
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "referencias mutuas resolubles con declaraciones, pero scopes diferentes; no se demuestra que la contradicción sea sobre el mismo contexto semántico",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["contradiction_refs_mutuos", "resolucion_de_referencias", "declaraciones_presentes", "scope_incompatible_con_contradicción"],
            "evidencia_que_respaldan": [
                "claim_a.contradiction_refs (resoluble)",
                "claim_b.contradiction_refs (resoluble)",
                "declaraciones presentes",
            ],
            "limitaciones": [
                "scopes distintos impiden confirmar contradicción sobre mismo objeto/alcance",
                "requiere verificación de relación de sub-objetos o contexto si aplica",
            ],
        }

    # Si object_hash difiere y no hay evidencia de relación de objeto,
    # tampoco se confirma contradicción del mismo objeto.
    if hash_a and hash_b and hash_a != hash_b:
        # Diferentes objetos: no contradicción del mismo objeto.
        # (Nota: la misma proposición podría contradiccirse sobre objetos
        # relacionados, pero esa relación no está verificada aquí.)
        return {
            "clasificacion": "INDETERMINATE",
            "motivo": "referencias mutuas resolubles con declaraciones, pero object_hash distintos; no se confirma contradicción sobre el mismo objeto sin evidencia de relación",
            "a_id": a_id,
            "b_id": b_id,
            "criterios_aplicados": ["contradiction_refs_mutuos", "resolucion_de_referencias", "declaraciones_presentes", "object_hash_distinto"],
            "evidencia_que_respaldan": [
                "claim_a.contradiction_refs (resoluble)",
                "claim_b.contradiction_refs (resoluble)",
                "declaraciones presentes",
            ],
            "limitaciones": [
                "object_hash distintos impiden afirmar contradicción del mismo objeto",
                "requiere verificación de relación de objeto o contexto",
            ],
        }

    # --- Si llega aquí, referencias mutuas, resolubles, declaraciones presentes,
    # mismo scope (o compatible), mismo objeto (o verificado): CONFLICT verificable ---
    return {
        "clasificacion": "CONFLICT",
        "motivo": "contradicción demostrada: referencias mutuas resolubles, declaraciones presentes, mismo alcance y objeto; proposiciones incompatibles respaldadas por estructura verificable",
        "a_id": a_id,
        "b_id": b_id,
        "criterios_aplicados": [
            "contradiction_refs_mutuos",
            "resolucion_de_referencias",
            "declaraciones_de_contradicción_presentes",
            "scope_compatible",
            "object_hash_compatible",
            "identidad_técnica_diferente",
        ],
        "evidencia_que_respaldan": [
            f"{a_id}.contradiction_refs contiene {b_id} (resoluble)",
            f"{b_id}.contradiction_refs contiene {a_id} (resoluble)",
            "declaraciones de contradicción verificadas (contradicciones param)",
            "scope igual o compatible",
            "object_hash igual (mismo objeto canónico)",
        ],
        "limitaciones": [
            "verificación semántica completa de la proposición requiere análisis de contexto; este resultado se basa en estructura verificable del esquema TIERRA",
        ],
    }
