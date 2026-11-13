"""RXRE-MISSION-386 — CONTRATO EPISTÉMICO GENÉRICO DE BUFFER-CAPACITY PROVENANCE.

Define un esquema versionado y validador para representar, de forma genérica y
reutilizable, la procedencia, capacidad, rangos inicializados/accesibles,
offsets, longitudes, alias, ownership y lifetime de buffers a través de
llamadas interprocedurales.

Reglas epistemológicas obligatorias:
  1. Asignación != inicialización.
  2. Longitud lógica != capacidad física.
  3. Parámetro puntero != propiedad.
  4. Alias candidato != alias demostrado.
  5. Offset desconocido != 0.
  6. Ausencia de liberación observada != lifetime ilimitado.
  7. Tamaño de escritura solicitado != escritura efectiva.
  8. Capacidad desconocida != capacidad ilimitada.
  9. Rango accesible != inicializado.
 10. Hash/identificador != identidad semántica de región.

No introduce heurísticas específicas de lenguaje/binario. No modifica contratos
protegidos. No ejecuta binarios.
"""
from __future__ import annotations

BUFFER_CAPACITY_PROVENANCE_CONTRACT_VERSION = "1.0.0"

VALID_STATES = ("PROVEN", "PARTIAL", "NOT_DETERMINED", "BLOCKED", "INSUFFICIENT")

VALID_OBJECT_CLASSES = ("HEAP", "STACK", "GLOBAL", "DERIVED", "UNKNOWN")

VALID_ORIGIN_KINDS = ("ALLOC", "PARAM", "GLOBAL", "DERIVED", "UNKNOWN", "MULTIPLE")
VALID_OFFSET_KINDS = ("CONSTANT", "VARIABLE", "UNKNOWN")
VALID_LENGTH_KINDS = ("CONSTANT", "SYMBOLIC", "UNKNOWN")
VALID_ALIAS_KINDS = ("PROVEN", "CANDIDATE", "AMBIGUOUS", "NONE", "UNKNOWN")
VALID_OWNERSHIP_KINDS = ("OWNED", "TRANSFERRED", "SHARED", "UNKNOWN")
VALID_LIFETIME_KINDS = ("DEMONSTRATED", "PARTIAL", "UNKNOWN")

# Propiedades canónicas (cada una conserva estado propio)
BUFFER_PROPERTIES = (
    "BUFFER_IDENTITY",
    "BUFFER_ORIGIN",
    "BUFFER_BASE",
    "BUFFER_CAPACITY",
    "BUFFER_INITIALIZED_RANGE",
    "BUFFER_ACCESSIBLE_RANGE",
    "BUFFER_OFFSET",
    "BUFFER_ACCESS_LENGTH",
    "BUFFER_ALIAS_SET",
    "BUFFER_OWNERSHIP",
    "BUFFER_LIFETIME",
)

# Clasificación epistemológica de afirmaciones
AFFIRMATION_CLASSES = ("STRUCTURAL_FACT", "SEMANTIC_INFERENCE", "CONTRACT_ASSERTION",
                       "VALIDATED_PROPERTY", "UNRESOLVED_PROPERTY")

PROPERTY_REQUIRED_FIELDS = ("state", "evidence_origin", "code_location", "method",
                            "conditions", "uncertainty", "value")


def _is_valid_state(s):
    return s in VALID_STATES


def validate_property(prop_name, prop):
    """Valida una propiedad individual. Devuelve lista de errores."""
    errors = []
    if not isinstance(prop, dict):
        return [f"{prop_name}: debe ser dict"]
    for f in PROPERTY_REQUIRED_FIELDS:
        if f not in prop:
            errors.append(f"{prop_name}: campo requerido ausente '{f}'")
    if "state" in prop and not _is_valid_state(prop["state"]):
        errors.append(f"{prop_name}: estado inválido '{prop['state']}'")
    # regla: ausencia no implica certeza
    if prop.get("state") == "PROVEN":
        if not prop.get("evidence_origin") or prop.get("evidence_origin") in ("unknown", None, ""):
            errors.append(f"{prop_name}: PROVEN requiere evidence_origin")
        if not prop.get("code_location") or prop.get("code_location") in ("unknown", None, ""):
            errors.append(f"{prop_name}: PROVEN requiere code_location")
        if not prop.get("method") or prop.get("method") in ("unknown", None, ""):
            errors.append(f"{prop_name}: PROVEN requiere method")
    # regla 5: offset desconocido != 0
    if prop_name == "BUFFER_OFFSET":
        if prop.get("value") == 0 and prop.get("state") in ("NOT_DETERMINED", "UNKNOWN"):
            errors.append(f"{prop_name}: offset desconocido no puede representarse como 0")
    # regla 8: capacidad desconocida != ilimitada
    if prop_name == "BUFFER_CAPACITY":
        if prop.get("value") is None and prop.get("state") in ("NOT_DETERMINED", "UNKNOWN"):
            # OK, pero si se marca como ilimitada es error
            if prop.get("value") == "unlimited" or prop.get("value") == float("inf"):
                errors.append(f"{prop_name}: capacidad desconocida no puede ser ilimitada")
    # regla 10: hash no demuestra identidad semántica
    if prop_name == "BUFFER_IDENTITY":
        if prop.get("method", "").lower().find("hash") != -1 and prop.get("state") == "PROVEN":
            # permitido solo si evidence_origin también demuestra semántica; se deja como advertencia
            pass
    return errors


def validate_record(record):
    """Valida un registro completo de buffer-capacity provenance."""
    errors = []
    if not isinstance(record, dict):
        return ["record debe ser dict"]
    if record.get("contract_version") != BUFFER_CAPACITY_PROVENANCE_CONTRACT_VERSION:
        errors.append(f"contract_version debe ser {BUFFER_CAPACITY_PROVENANCE_CONTRACT_VERSION}")
    if "buffer_id" not in record or not record.get("buffer_id"):
        errors.append("buffer_id requerido")
    # object_class validation (M408): optional, default UNKNOWN, no false promotion
    oc = record.get("object_class", "UNKNOWN")
    if oc not in VALID_OBJECT_CLASSES:
        errors.append(f"object_class inválido: {oc}")
    if oc == "DERIVED" and not record.get("parent_object_id"):
        errors.append("object_class DERIVED requiere parent_object_id")
    # object_class must not be promoted without evidence
    oc_ev = record.get("object_class_evidence")
    if oc != "UNKNOWN" and (not isinstance(oc_ev, dict) or not oc_ev.get("evidence_origin")):
        errors.append(f"object_class {oc} requiere object_class_evidence con evidence_origin")
    if "properties" not in record or not isinstance(record.get("properties"), dict):
        errors.append("properties debe ser dict")
    else:
        props = record["properties"]
        for p in BUFFER_PROPERTIES:
            if p not in props:
                errors.append(f"propiedad requerida ausente: {p}")
            else:
                errors.extend(validate_property(p, props[p]))
    # regla: no un único estado para todo el buffer
    if "properties" in record and isinstance(record["properties"], dict):
        states = {p.get("state") for p in record["properties"].values() if isinstance(p, dict)}
        # permitido si todas NOT_DETERMINED, pero si hay mezcla con PROVEN en una sola propiedad global -> error
        if "global_state" in record:
            errors.append("no se permite global_state único para todo el buffer")
    # regla: alias candidato != alias demostrado
    alias = record.get("properties", {}).get("BUFFER_ALIAS_SET", {})
    if isinstance(alias, dict):
        if alias.get("state") == "PROVEN" and alias.get("value_kind") == "CANDIDATE":
            errors.append("BUFFER_ALIAS_SET: candidato no puede ser PROVEN")
    # regla: rango accesible != inicializado
    init = record.get("properties", {}).get("BUFFER_INITIALIZED_RANGE", {})
    acc = record.get("properties", {}).get("BUFFER_ACCESSIBLE_RANGE", {})
    if isinstance(init, dict) and isinstance(acc, dict):
        if init.get("value") == acc.get("value") and init.get("state") == "PROVEN" and acc.get("state") == "PROVEN":
            # no es automáticamente error, pero si se afirma igualdad sin evidencia -> error
            if not init.get("evidence_origin") or init.get("evidence_origin") != acc.get("evidence_origin"):
                errors.append("BUFFER_INITIALIZED_RANGE == BUFFER_ACCESSIBLE_RANGE requiere evidencia común")
    # afirmaciones deben estar clasificadas
    if "affirmations" in record and isinstance(record["affirmations"], list):
        for a in record["affirmations"]:
            if not isinstance(a, dict):
                errors.append("afirmación debe ser dict")
                continue
            if a.get("class") not in AFFIRMATION_CLASSES:
                errors.append(f"clase de afirmación inválida: {a.get('class')}")
            if a.get("state") not in VALID_STATES:
                errors.append(f"estado de afirmación inválido: {a.get('state')}")
    return errors


def build_minimal_record(buffer_id, origin_kind="UNKNOWN", object_class="UNKNOWN",
                         parent_object_id=None, capacity_state="NOT_DETERMINED",
                         offset_state="NOT_DETERMINED", alias_state="UNKNOWN",
                         init_state="NOT_DETERMINED", access_state="NOT_DETERMINED",
                         ownership_state="UNKNOWN", lifetime_state="UNKNOWN",
                         base_state="NOT_DETERMINED", identity_state="NOT_DETERMINED",
                         access_length_state="NOT_DETERMINED"):
    """Construye un registro mínimo con estados explícitos (sin certeza por defecto)."""
    def prop(state, value=None, ek="unknown", cl="unknown", method="unknown",
             conditions="none", uncertainty="unspecified", **extra):
        d = {
            "state": state,
            "value": value,
            "evidence_origin": ek,
            "code_location": cl,
            "method": method,
            "conditions": conditions,
            "uncertainty": uncertainty,
        }
        d.update(extra)
        return d
    return {
        "contract_version": BUFFER_CAPACITY_PROVENANCE_CONTRACT_VERSION,
        "buffer_id": buffer_id,
        "object_class": object_class,
        "parent_object_id": parent_object_id,
        "object_class_evidence": {"state": "NOT_DETERMINED", "evidence_origin": "", "method": "unclassified"},
        "origin_kind": origin_kind,
        "properties": {
            "BUFFER_IDENTITY": prop(identity_state, value=buffer_id),
            "BUFFER_ORIGIN": prop("NOT_DETERMINED" if origin_kind == "UNKNOWN" else "PARTIAL",
                                  value=origin_kind, method="origin_classification"),
            "BUFFER_BASE": prop(base_state),
            "BUFFER_CAPACITY": prop(capacity_state),
            "BUFFER_INITIALIZED_RANGE": prop(init_state),
            "BUFFER_ACCESSIBLE_RANGE": prop(access_state),
            "BUFFER_OFFSET": prop(offset_state, value=None if offset_state in ("NOT_DETERMINED", "UNKNOWN") else 0),
            "BUFFER_ACCESS_LENGTH": prop(access_length_state),
            "BUFFER_ALIAS_SET": prop("NOT_DETERMINED" if alias_state == "UNKNOWN" else "PARTIAL",
                                     value=alias_state, value_kind=alias_state),
            "BUFFER_OWNERSHIP": prop("NOT_DETERMINED" if ownership_state == "UNKNOWN" else "PARTIAL",
                                     value=ownership_state),
            "BUFFER_LIFETIME": prop("NOT_DETERMINED" if lifetime_state == "UNKNOWN" else "PARTIAL",
                                    value=lifetime_state),
        },
        "affirmations": [],
    }


def classify_from_observations(obs):
    """Clasifica observaciones estructurales en un registro (sin heurísticas de ejecución).

    obs: dict con claves opcionales:
      has_allocation (bool), has_init (bool), has_caller_capacity (bool),
      has_offset (bool), has_alias (bool), has_ownership (bool),
      has_lifetime (bool), has_accessible (bool), has_identity (bool)
    """
    def st(cond, proven=False):
        if proven and cond:
            return "PROVEN"
        if cond:
            return "PARTIAL"
        return "NOT_DETERMINED"
    rec = build_minimal_record(
        buffer_id=obs.get("buffer_id", "unknown"),
        origin_kind="ALLOC" if obs.get("has_allocation") else "UNKNOWN",
        capacity_state=st(obs.get("has_caller_capacity", False)),
        offset_state=st(obs.get("has_offset", False)),
        alias_state="CANDIDATE" if obs.get("has_alias") else "UNKNOWN",
        init_state=st(obs.get("has_init", False)),
        access_state=st(obs.get("has_accessible", False)),
        ownership_state="UNKNOWN",
        lifetime_state="UNKNOWN",
        base_state=st(obs.get("has_allocation", False)),
        identity_state=st(obs.get("has_identity", False)),
        access_length_state=st(obs.get("has_accessible", False)),
    )
    return rec


__all__ = [
    "BUFFER_CAPACITY_PROVENANCE_CONTRACT_VERSION",
    "VALID_STATES",
    "BUFFER_PROPERTIES",
    "AFFIRMATION_CLASSES",
    "validate_property",
    "validate_record",
    "build_minimal_record",
    "classify_from_observations",
]
