#!/usr/bin/env python3
"""RXRE-209 — Preintegración aislada y explícita finding -> TIERRA.

NO se activa automáticamente. Requiere invocación explícita con DB
aislada y resolver_refs verificado. No modifica base operativa.

Reutiliza: adapter_207 (convertir/ejecutar), transition_policy_208,
TIERRA.Grafo (API canónica), store.conectar (solo para resolver refs
si se le pasa conexión operativa aislada).
"""
from __future__ import annotations
from typing import Dict, Any, Optional, Callable
import sqlite3, os

from rxre.contracts.transition_policy import política_transición
try:
    from rxre.adapters.adapter_finding_tierra import AdapterError
except ImportError:
    class AdapterError(ValueError):
        pass
from rxre.adapters.adapter_finding_tierra import ejecutar_adaptador
from rxre.arquitectura import TIERRA


def _normalizar_contradicciones(ctrs):
    """Acepta lista de dicts o {"statements": [...]} y devuelve la lista.

    La politica (208) y el adaptador (207) usaban formas distintas; esta
    funcion las unifica SIN cambiar el significado de ninguna de las dos.
    """
    if ctrs is None:
        return []
    if isinstance(ctrs, dict):
        ctrs = ctrs.get("statements") or []
    if isinstance(ctrs, str):
        return []
    return list(ctrs)


def preintegrate_finding_to_tierra(
    grafo_path: str,
    finding_dict: Dict[str, Any],
    resolver_refs: Optional[Callable[[str], bool]] = None,
    contradiction_statements: Optional[Any] = None,
    explicit_enable: bool = False,
) -> Dict[str, Any]:
    """Conversión aislada, explícita, reversible.

    `explicit_enable` debe ser `True`; si es `False` retorna bloqueado
    sin realizar ninguna escritura (defensa por defecto).

    Si la política rechaza o solicita datos (`REJECT`/`NEEDS_INPUT`),
    no escribe nada en `grafo_path`; devuelve el dict de la política.
    Si `ACCEPT`, escribe en `grafo_path` (base aislada) y devuelve
    `claim_id`; si el claim ya existe, retorna `ya_existia`.
    """
    if explicit_enable is not True:
        # [212] Solo el booleano True autoriza. `1`, `"true"`, `"false"`,
        # `"True"` son truthy pero NO son autorizacion: aceptarlos seria
        # una puerta que se abre con un valor mal escrito.
        return {"status": "blocked",
                "motivo": "autorizacion requiere explicit_enable=True (booleano exacto); "
                           "recibido %r (%s). La autorizacion no admite conversiones "
                           "implicitas ni valores truthy no booleanos"
                           % (explicit_enable, type(explicit_enable).__name__),
                "decision": "NOT_ACTIVATED",
                "claim_id": None}
    if not grafo_path or not grafo_path.startswith("/"):
        return {"status": "blocked",
                "motivo": "grafo_path debe ser absoluto y aislado",
                "decision": "NOT_ACTIVATED",
                "claim_id": None}

    # Política pura (no escribe)
    ctrs_norm = _normalizar_contradicciones(contradiction_statements)
    result_pol = política_transición(
        finding_dict,
        resolver_refs=resolver_refs,
        contradiction_statements=({"statements": ctrs_norm} if ctrs_norm else None))

    if result_pol["decision"] in ("REJECT", "NEEDS_INPUT"):
        # No escribir nada; la frontera se documenta y se detiene
        return {"status": "blocked", "motivo": result_pol.get("reason"),
                "decision": result_pol["decision"],
                "claim_id": result_pol.get("claim_id"),
                "claim_pre": result_pol.get("claim_pre")}

    # Solo si la política acepta y los datos están completos
    try:
        g = TIERRA.Grafo(grafo_path)
        # Resolver refs con la DB operativa aislada si el usuario provee
        # una conexión; por defecto confiamos en resolver_refs externo.
        res = ejecutar_adaptador(
            g, finding_dict,
            resolver_refs=resolver_refs,
            contradiction_statements=ctrs_norm or None,
            autorizacion=True)
        return {"status": "ok", "decision": "ACCEPT",
                "claim_id": res.get("claim_id"),
                "estado_epistemologico": res.get("estado"),
                "evidencia_registrada": len(res.get("evidencia") or []),
                "ya_existia": res.get("estado") == "ya_existia",
                "motivo": result_pol.get("reason")}
    except Exception as e:
        # ROLLBACK automático por ejecutar_adaptador; no hay parcial
        return {"status": "error", "motivo": str(e),
                "decision": result_pol.get("decision"),
                "claim_id": None}
