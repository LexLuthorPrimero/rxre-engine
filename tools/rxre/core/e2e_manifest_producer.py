#!/usr/bin/env python3
"""RXRE-MISSION-273 — PRODUCTOR REAL DE MANIFIESTO E2E CON SCOPE VINCULADO.

Cadena: decision de autoridad -> request -> operacion -> resultado -> manifiesto E2E -> verificador.

Reglas (no negociables):
  * El manifiesto se deriva de una operacion y un resultado REALES (leidos de la base),
    nunca de parametros sueltos del consumidor.
  * `scope` solo se escribe si la autorizacion esta documentada y es coherente
    request/operacion/resultado. Una declaracion del consumidor NO sustituye la
    autorizacion: si falta, el manifiesto se emite SIN scope y con
    `scope_decision = UNVERIFIED` (no se inventa procedencia).
  * `DOCUMENTED_AUTHORITY` (archivo de decision del operador) NO se presenta como
    autenticidad criptografica.
  * Ante alteracion (scope, identificadores, hash), el productor RECHAZA y no escribe.
  * No modifica evidencia canonica existente; escribe solo donde se le indique.
  * No escribe en la base: solo LEE (mode=ro) y escribe el archivo de manifiesto.
"""
import json, os, sqlite3, hashlib
from pathlib import Path

AUTH_DECISION_FILE = "/home/lucas/Escritorio/rxre/audit/debugfs/SCOPE_AUTHORITY_DECISION.md"
try:
    from rxre.contracts import immutable_write_contract as iwc
except Exception:
    from ..contracts import immutable_write_contract as iwc


def _autoridad_documentada():
    """Lee la decision de autoridad del operador. Distingue DOCUMENTED de criptografico."""
    try:
        texto = Path(AUTH_DECISION_FILE).read_text()
    except Exception:
        return {"estado": "PENDING", "operador": None, "autenticidad": "NO_AUTHORITY_DOCUMENTED"}
    aprobado = "Estado:" in texto and "APPROVED" in texto
    operador = "lucas" if "lucas" in texto.lower() else None
    return {
        "estado": "APPROVED" if aprobado else "PENDING",
        "operador": operador,
        "autenticidad": "DOCUMENTED_AUTHORITY" if aprobado else "NO_AUTHORITY_DOCUMENTED",
        "nota": "Evidencia documental de la decision del operador; no es firma criptografica.",
    }


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def _leer_operacion_y_resultado(db_path, op_id, result_id):
    """Lee operacion y resultado REALES de la base (solo lectura)."""
    uri = "file:%s?mode=ro" % db_path
    con = sqlite3.connect(uri, uri=True)
    try:
        op = con.execute(
            "SELECT operation_id, scope, request_json, response_json, timestamp FROM operations "
            "WHERE operation_id=? LIMIT 1", (op_id,)).fetchone()
        res = con.execute(
            "SELECT result_id, operation_id, scope, file, raw_json, row_hash, status, timestamp "
            "FROM results WHERE result_id=? LIMIT 1", (result_id,)).fetchone()
    finally:
        con.close()
    return op, res


def generar_manifest_e2e(db_path, op_id, result_id, destino, e2e_id=None,
                         epistemic="OBSERVED", procedencia=None, tipo="evidencia"):
    """Genera un manifiesto E2E derivado de la operacion y el resultado reales.

    Devuelve dict con status: WRITTEN | REJECTED.
    """
    if not db_path or not os.path.isfile(db_path):
        return {"status": "REJECTED", "motivo": "base no disponible: %s" % db_path}
    if not op_id or not result_id:
        return {"status": "REJECTED", "motivo": "op_id y result_id son obligatorios (no se infieren)"}
    try:
        op, res = _leer_operacion_y_resultado(db_path, op_id, result_id)
    except Exception as exc:
        return {"status": "REJECTED", "motivo": "no se pudo leer operacion/resultado: %s" % exc}
    if not op:
        return {"status": "REJECTED", "motivo": "operacion inexistente: %s" % op_id}
    if not res:
        return {"status": "REJECTED", "motivo": "resultado inexistente: %s" % result_id}

    # Vinculo inequivoco: el resultado debe pertenecer a la operacion
    if str(res[1]) != str(op[0]):
        return {"status": "REJECTED",
                "motivo": "vínculo roto: resultado %s pertenece a %s, no a %s" % (result_id, res[1], op[0])}

    request = {}
    try:
        request = json.loads(op[2] or "{}")
    except Exception:
        request = {}
    auth_in_req = request.get("scope_authorization") or {}
    declared_scope = request.get("scope")
    op_scope = op[1]
    res_scope = res[2]

    # Coherencia de scope entre etapas (no basta un hash valido)
    scopes = {"request.scope": declared_scope, "operations.scope": op_scope, "results.scope": res_scope}
    valores = {k: (str(v).strip() if v is not None else None) for k, v in scopes.items()}
    no_nulos = {k: v for k, v in valores.items() if v}
    if len(set(no_nulos.values())) > 1:
        return {"status": "REJECTED",
                "motivo": "conflicto de scope entre etapas: %s" % json.dumps(scopes, sort_keys=True),
                "scope_etapas": scopes}

    autoridad = _autoridad_documentada()
    autorizado = bool(auth_in_req) and auth_in_req.get("decision") == "AUTHORIZED" \
        and autoridad["estado"] == "APPROVED" \
        and auth_in_req.get("actor") == autoridad["operador"]

    scope_efectivo = None
    scope_decision = "UNVERIFIED"
    if autorizado:
        scope_efectivo = request.get("scope") or auth_in_req.get("scope")
        scope_decision = "AUTHORIZED"   # el verificador independiente decide VERIFIED despues
    elif valores.get("request.scope") or valores.get("results.scope"):
        # Hay scope pero sin autorizacion verificable: se documenta, no se eleva
        scope_efectivo = None
        scope_decision = "UNVERIFIED"

    # Artefacto observado y verificación de integridad vía el contrato
    # immutable_write_contract.verificar_integridad_artefacto.
    # Reconoce explícitamente el formato real del escritor (raw_json anidado
    # cuando store.registrar lo guarda): el hash del artefacto puede estar
    # en forma plana ("hash") o en forma anidada ("raw_json.hash"); ambas
    # fuentes se clasifican, y ningún hash falificado o contradictorio se
    # acepta silenciosamente.
    art_path = res[3] or request.get("artifact_path") or request.get("artefacto_path")
    art_hash_real = None
    art_size = None
    if art_path and os.path.isfile(art_path):
        art_hash_real = _sha256(art_path)
        art_size = os.path.getsize(art_path)
    integridad = iwc.verificar_integridad_artefacto(res[4], art_path if art_path else None)
    integridad["operacion"] = op[0] if op else None
    integridad["operacional"] = bool(op) and int(bool(op[0]))  # cobertura parética

    # Clasificación estricta del hash.
    if integridad["status"] == "MISMATCH":
        return {"status": "REJECTED",
                "motivo": "hash del resultado no coincide con el artefacto real (integridad rota)",
                "integridad": integridad}
    if integridad["status"] == "CONFLICT":
        return {"status": "REJECTED",
                "motivo": "conflicto de hash: fuentes contradictorias (plano vs anidado); no se acepta un hash ambiguo",
                "integridad": integridad}

    # Si se pretunea emitir scoped manifiesto pero la integerecia del artefactual
    # es insuficiente (ausente o contradictoria), no emitimos. Si no hay scope
    # declarado ni autorizado, se emite con classificacion explíciTICA.
    scope_claimed = bool(scope_efectivo)
    if scope_claimed and integridad["status"] not in ("OK",):
        return {"status": "REJECTED",
                "motivo": "alcance autorizado pero integridad del artefacto insuficiente: no se afirma VERIFIED sin evidencia completa",
                "integridad": integridad}

    manifest = {
        "e2e_id": e2e_id or ("e2e_%s" % result_id),
        "objetivo": "manifiesto generado por productor real (RXRE-273) desde operacion y resultado",
        "artefacto_path": art_path or "",
        "artefacto_size_bytes": art_size,
        "artefacto_hash_sha256": art_hash_real or integridad.get("hash_declarado") or "",
        "epistemic": epistemic,
        "procedencia": procedencia or ("operation_id=%s; result_id=%s; db=%s" % (op_id, result_id, db_path)),
        "tipo": tipo,
        # --- vinculo verificable con la cadena ---
        "operation_id": op[0],
        "result_id": res[0],
        "result_row_hash": res[5],
        "operation_timestamp": op[4],
        "result_timestamp": res[7],
        # --- scope: tres niveles distintos, nunca fundidos ---
        "declared_scope": valores.get("request.scope"),
        "authorized_scope": scope_efectivo,
        "verified_scope": None,   # lo decide el verificador independiente
        "scope": scope_efectivo,   # campo que lee scope_provenance_contract
        "scope_decision": scope_decision,
        "scope_autorizacion": {
            "decision": auth_in_req.get("decision"),
            "actor": auth_in_req.get("actor"),
            "timestamp": auth_in_req.get("timestamp"),
            "autoridad_estado": autoridad["estado"],
            "autenticidad": autoridad["autenticidad"],
            "nota": autoridad["nota"],
        },
        "scope_etapas_observadas": scopes,
        "integridad_artefacto": integridad,
        "hash_fuentes": integridad.get("fuentes") if isinstance(integridad, dict) else None,
    }
    if not manifest["artefacto_hash_sha256"]:
        manifest["scope_decision"] = "UNVERIFIED"
        manifest["scope_autorizacion"]["nota"] = "Sin hash de artefacto verificable; no se afirma integridad."
    destino_path = Path(destino)
    destino_path.parent.mkdir(parents=True, exist_ok=True)
    destino_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return {"status": "WRITTEN", "path": str(destino_path), "manifest": manifest,
            "e2e_id": manifest["e2e_id"], "scope_decision": scope_decision}
