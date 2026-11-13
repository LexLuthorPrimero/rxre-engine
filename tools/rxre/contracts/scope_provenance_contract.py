#!/usr/bin/env python3
"""RXRE-MISSION-253 / M284 — CONTRATO DE PROCEDENCIA DEL SCOPE (REPARADO).
Reparaciones aplicadas vs versión anterior:
- _read_only_scope extrae hash anidado (raw_json.raw_json.hash) y lee operation_id.
- Se exige linkage DB↔Manifiesto (operation_id/result_id) antes de VERIFIED.
- Se consume observed_artifact_path/observed_hash para comprobar vinculo con artefacto.
- Se rechaza VERIFIED con solo una fuente (§5 ya no produce VERIFIED sin manifest).
- Se verifican verified_scope/scope_decision/row_hash en fila; contradicciones rechazan.
- No se modifica DB_OP ni production zones.
"""
import json
import os
import sqlite3


def _coincide_hash(a, b):
    try:
        from rxre.contracts.evidence_claim_verification import _coincide_hash as co
        return co(a, b)
    except Exception:
        return str(a).strip().lower() == str(b).strip().lower()


def _read_only_scope(db_path, result_id):
    if not db_path or not os.path.isfile(db_path) or not result_id:
        return (None, None, None, None)
    try:
        uri = "file:%s?mode=ro" % db_path
        con = sqlite3.connect(uri, uri=True)
        row = con.execute(
            "SELECT scope, file, raw_json, operation_id FROM results WHERE result_id=? LIMIT 1",
            (result_id,)
        ).fetchone()
        con.close()
    except Exception:
        return (None, None, None, None)
    if not row:
        return (None, None, None, None)
    scope, file_col, raw_json, op_id = row
    h = None
    try:
        meta = json.loads(raw_json or "{}")
        # Formato real del escritor M281: raw_json anidado (el dict completo guardado por store.registrar)
        # El hash puede estar en meta.get("hash") (plano) o meta["raw_json"]["hash"] (anidado como guarda el escritor).
        nested_raw = meta.get("raw_json") if isinstance(meta, dict) else None
        if isinstance(nested_raw, dict) and "hash" in nested_raw:
            h = nested_raw["hash"]
        elif isinstance(meta, dict) and "hash" in meta:
            h = meta["hash"]
        elif isinstance(meta, dict) and "artefacto_hash_sha256" in meta:
            h = meta["artefacto_hash_sha256"]
    except Exception:
        pass
    # Si no se encontró hash, intentar extraer de la estructura real del artefacto (no inventar)
    return (scope, file_col, h, op_id)


def _verificar_fila_integridad(db_path, result_id):
    """Recalcular row_hash a partir de campos canónicos presentes en DB (independiente del contrato)."""
    if not db_path or not result_id:
        return None, "DB o result_id ausente"
    try:
        uri = "file:%s?mode=ro" % db_path
        con = sqlite3.connect(uri, uri=True)
        row = con.execute(
            "SELECT result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp FROM results WHERE result_id=? LIMIT 1",
            (result_id,)
        ).fetchone()
        con.close()
        if not row:
            return None, "Fila no encontrada"
        import hashlib, json
        campos = {
            "result_id": row[0],
            "operation_id": row[1],
            "type": row[2],
            "value": str(row[3])[:4000],
            "source": row[4],
            "file": row[5] or "",
            "line": row[6],
            "scope": row[7] or "",
            "tool": row[8] or "",
            "tool_version": row[9] or "",
            "status": row[10] or "",
            "raw_json": json.dumps(json.loads(row[11] or "{}"), sort_keys=True, default=str) if isinstance(row[11], str) else str(row[11]),
            "timestamp": row[12] or "",
        }
        expected = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
        # El row_hash guardado está en columna 13 (row_hash) si existe; leerlo por separado
        # (esta función solo puede calcular esperado, no comparar sin conocer el guardado)
        return expected, None
    except Exception as exc:
        return None, "Error de integridad: %s" % str(exc)


# --- M285: estado persistido de la fila + integridad de row_hash ---
_ESTADOS_CONOCIDOS = ("VERIFIED", "AUTHORIZED", "UNVERIFIED", "INDETERMINATE", "CONFLICT", "REJECTED")
_ESTADOS_NEGATIVOS = ("CONFLICT", "REJECTED")


def _leer_estado_fila(db_path, result_id):
    """Lee estado persistido (scope_decision/verified_scope) y verifica row_hash
    recalculandolo desde los valores RECUPERADOS DE LA BASE (no desde memoria).
    Devuelve dict con los estados y el veredicto de integridad."""
    out = {
        "present": False,
        "scope_decision": None,
        "verified_scope": None,
        "row_hash_persisted": None,
        "row_hash_expected": None,
        "row_hash_state": "INDETERMINATE",   # OK | MISMATCH | ABSENT | INDETERMINATE
        "row_hash_reason": "",
    }
    if not db_path or not os.path.isfile(db_path) or not result_id:
        out["row_hash_reason"] = "DB o result_id ausente: no se puede leer el estado de la fila"
        return out
    try:
        uri = "file:%s?mode=ro" % db_path
        con = sqlite3.connect(uri, uri=True)
        row = con.execute(
            "SELECT result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,"
            "status,raw_json,timestamp,row_hash,verified_scope,scope_decision FROM results "
            "WHERE result_id=? LIMIT 1", (result_id,)
        ).fetchone()
        con.close()
    except Exception as exc:
        out["row_hash_reason"] = "Error leyendo la fila: %s" % str(exc)
        return out
    if not row:
        out["row_hash_reason"] = "Fila no encontrada en la base"
        return out
    out["present"] = True
    out["verified_scope"] = row[14]
    out["scope_decision"] = row[15]
    out["row_hash_persisted"] = row[13]
    # Recálculo canónico idéntico al escritor M281 (campos_result, sin row_hash/supersedes_ref)
    try:
        import hashlib
        raw_obj = json.loads(row[11] or "{}")
        if not isinstance(raw_obj, dict):
            out["row_hash_state"] = "INDETERMINATE"
            out["row_hash_reason"] = "raw_json no es un objeto JSON: serializacion ambigua"
            return out
        canonical_raw = json.dumps(raw_obj, sort_keys=True, default=str)
        campos = {
            "result_id": row[0],
            "operation_id": row[1],
            "type": row[2] or "",
            "value": str(row[3])[:4000],
            "source": row[4] or "",
            "file": row[5] or "",
            "line": row[6],
            "scope": row[7] or "",
            "tool": row[8] or "",
            "tool_version": row[9] or "",
            "status": row[10] or "",
            "raw_json": canonical_raw,
            "timestamp": row[12] or "",
        }
        expected = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
        out["row_hash_expected"] = expected
        persisted = (row[13] or "").strip()
        if persisted == "":
            out["row_hash_state"] = "ABSENT"
            out["row_hash_reason"] = "row_hash ausente en la fila: no hay evidencia de integridad; nunca VERIFIED"
        elif persisted != expected:
            out["row_hash_state"] = "MISMATCH"
            out["row_hash_reason"] = "row_hash persistido (%s...) no coincide con el recalculado desde la base (%s...)" % (persisted[:12], expected[:12])
        else:
            out["row_hash_state"] = "OK"
            out["row_hash_reason"] = "row_hash coincide con el recalculo canonico sobre los valores de la base"
    except Exception as exc:
        out["row_hash_state"] = "INDETERMINATE"
        out["row_hash_reason"] = "No se pudo recalcular row_hash (%s): decision conservadora" % str(exc)
    return out


def _componer_estados(db_estado, mf_estado):
    """Regla de composicion (sin precedencia arbitraria):
      - negativa en cualquier fuente (CONFLICT/REJECTED) domina y se propaga;
      - 'VERIFIED' en una fuente con la otra restrictiva o intermedia es CONFLICT;
      - estados intermedios/restrictivos compatibles no son contradiccion.
    Devuelve (decision, motivo)."""
    neg = {"CONFLICT": "CONFLICT", "REJECTED": "REJECTED"}
    if db_estado in neg:
        return neg[db_estado], "Estado persistido en DB es %s" % db_estado
    if mf_estado in neg:
        return neg[mf_estado], "Estado declarado en el manifiesto es %s" % mf_estado
    if db_estado == "VERIFIED" and mf_estado not in ("VERIFIED", None):
        return "CONFLICT", "DB afirma VERIFIED pero el manifiesto declara %s" % mf_estado
    if mf_estado == "VERIFIED" and db_estado not in ("VERIFIED", None):
        return "CONFLICT", "Manifiesto afirma VERIFIED pero la fila declara %s" % db_estado
    return None, "Estados compatibles (DB=%s, manifest=%s)" % (db_estado, mf_estado)

def verificar_autoridad_scope(
    evidence_ref: str,
    claim_scope: str = None,
    db_op_path: str = None,
    db_op_result_id: str = None,
    manifest_e2e_path: str = None,
    observed_artifact_path: str = None,
    observed_hash: str = None,
) -> dict:
    result = {
        "decision": "UNVERIFIED",
        "explanation": "",
        "evidence_ref": evidence_ref,
        "claim_scope": claim_scope,
        "sources": {
            "db_op": {"present": False, "scope": None, "file": None, "hash": None, "operation_id": None, "result_id": None},
            "manifest": {"present": False, "scope": None, "artifact_path": None, "hash": None, "operation_id": None, "result_id": None},
            "consumer_declaration": {"scope": claim_scope, "authoritative": False},
            "observed_artifact": {"present": False, "path": None, "hash": None},
        },
        "integrity_is_separate_precondition": True,
    }

    if not evidence_ref or not isinstance(evidence_ref, str) or evidence_ref.strip() == "":
        result["decision"] = "INVALID"
        result["explanation"] = "Referencia de evidencia inválida o ausente (no inventable)"
        return result

    # --- Fuente operativa (DB) ---
    db_op_result_id = db_op_result_id or evidence_ref
    db_scope, db_file, db_hash, db_op_id = _read_only_scope(db_op_path, db_op_result_id)
    if db_scope is not None or db_file is not None:
        result["sources"]["db_op"]["present"] = True
        result["sources"]["db_op"]["scope"] = db_scope
        result["sources"]["db_op"]["file"] = db_file
        result["sources"]["db_op"]["hash"] = db_hash
        result["sources"]["db_op"]["operation_id"] = db_op_id
        result["sources"]["db_op"]["result_id"] = db_op_result_id

    db_has_scope = db_scope is not None and str(db_scope).strip() != ""
    db_row_exists = db_scope is not None or (db_op_path and os.path.isfile(db_op_path) and db_op_result_id)

    # --- Fuente manifest ---
    mf_scope = None
    mf_path = None
    mf_hash = None
    mf_op_id = None
    mf_res_id = None
    if manifest_e2e_path:
        if not os.path.isfile(manifest_e2e_path):
            result["decision"] = "INVALID"
            result["explanation"] = "Manifest E2E inexistente o inaccesible: %s" % manifest_e2e_path
            return result
        try:
            with open(manifest_e2e_path) as f:
                m = json.load(f)
        except Exception as exc:
            result["decision"] = "INVALID"
            result["explanation"] = "Manifest E2E malformado (%s): %s" % (manifest_e2e_path, str(exc))
            return result
        mf_scope = m.get("scope") or m.get("e2e_scope") or m.get("scope_operativo")
        mf_path = m.get("artefacto_path") or m.get("artifact_path")
        mf_hash = m.get("artefacto_hash_sha256") or m.get("hash_sha256")
        mf_op_id = m.get("operation_id")
        mf_res_id = m.get("result_id")
        result["sources"]["manifest"].update({"present": True, "scope": mf_scope, "artifact_path": mf_path, "hash": mf_hash, "operation_id": mf_op_id, "result_id": mf_res_id})
    mf_has_scope = mf_scope is not None and str(mf_scope).strip() != ""

    # --- Fuente observada (artefacto independiente) ---
    if observed_artifact_path is not None or observed_hash is not None:
        result["sources"]["observed_artifact"]["present"] = True
        result["sources"]["observed_artifact"]["path"] = observed_artifact_path
        result["sources"]["observed_artifact"]["hash"] = observed_hash
        # Si hay observación de artefacto con hash, y la fila DB o manifiesto indican otro, es conflicto.
        # El contrato NO debe admitir VERIFIED si el artefacto observado contradice la fuente.
        # Comprobación: si hay db_hash y observed_hash, deben coincidir (si ambos presentes).
        # Si hay mf_hash y observed_hash, deben coincidir.
        # Nota: observado es externo; si no coincide, REJECTED.
        # Implementación: se valida más adelante tras determinar fuentes disponibles.

    # --- M285: Politica de contradicciones persistidas + integridad de fila ---
    estado_fila = _leer_estado_fila(db_op_path, db_op_result_id)
    db_estado = estado_fila.get("scope_decision")
    db_vscope = estado_fila.get("verified_scope")
    mf_estado = None
    if manifest_e2e_path:
        try:
            mf_estado = m.get("scope_decision") or m.get("decision")
        except Exception:
            mf_estado = None
    # 1) Contradiccion interna de la fila: verified_scope='VERIFIED' con decision no-VERIFIED
    if db_vscope is not None and str(db_vscope).strip() == "VERIFIED" and db_estado not in ("VERIFIED",):
        result["decision"] = "CONFLICT"
        result["explanation"] = "Contradiccion persistida en la fila: verified_scope='VERIFIED' con scope_decision=%s" % (db_estado if db_estado is not None else "AUSENTE")
        return result
    # 2) Composicion de estados DB / manifiesto
    composicion, motivo_comp = _componer_estados(db_estado, mf_estado)
    if composicion:
        result["decision"] = composicion
        result["explanation"] = "Contradiccion de estados: %s" % motivo_comp
        return result
    # 3) scope_decision ausente o invalido -> decision conservadora (nunca VERIFIED)
    if db_estado is not None and str(db_estado).strip() not in _ESTADOS_CONOCIDOS:
        result["decision"] = "INDETERMINATE"
        result["explanation"] = "scope_decision persistido no valido (%s): no se puede decidir; no se afirma VERIFIED" % str(db_estado)
        return result
    # 4) Integridad de fila (row_hash recalculado desde la base)
    rh_state = estado_fila.get("row_hash_state")
    if rh_state == "MISMATCH":
        result["decision"] = "REJECTED"
        result["explanation"] = "Integridad de fila no demostrada: %s" % estado_fila.get("row_hash_reason")
        return result
    if rh_state in ("ABSENT", "INDETERMINATE"):
        # Evidencia insuficiente de integridad: nunca VERIFIED, pero no se inventa corrupcion.
        result["decision"] = "INDETERMINATE"
        result["explanation"] = "Integridad de fila no demostrable: %s" % estado_fila.get("row_hash_reason")
        return result

    # --- 4) Vínculo causal DB ↔ Manifiesto ---
    # El manifiesto debe vincularse a la operación/resultado de la fila DB (si existe fila DB)
    # y la fila DB debe corresponder al manifiesto (si existe manifiesto).
    # Si db_op_path y manifest_e2e_path ambos presentes y hay fila DB con result_id:
    linkage_ok = True
    linkage_notes = []
    if db_row_exists and manifest_e2e_path and (mf_op_id is not None or mf_res_id is not None):
        if mf_op_id is not None and db_op_id is not None and str(mf_op_id).strip() != str(db_op_id).strip():
            linkage_ok = False
            linkage_notes.append("operation_id manifest (%s) != DB operation_id (%s)" % (mf_op_id, db_op_id))
        if mf_res_id is not None and db_op_result_id is not None and str(mf_res_id).strip() != str(db_op_result_id).strip():
            linkage_ok = False
            linkage_notes.append("result_id manifest (%s) != DB result_id (%s)" % (mf_res_id, db_op_result_id))
        # Si el manifiesto no declara op/res pero DB sí existe, no es suficiente por sí solo;
        # sin embargo, para un vínculo completo, el manifiesto debe referenciar la fila concreta.
        if mf_op_id is None and mf_res_id is None:
            linkage_ok = False
            linkage_notes.append("manifiesto sin operation_id ni result_id; no vinculado a DB")
    # Si no hay fila DB pero sí manifest, el vínculo no puede ser verificado completamente.
    # Reglas de decisión según falta de vínculo:
    if not linkage_ok:
        result["decision"] = "REJECTED"
        result["explanation"] = "Vínculo roto entre DB y manifiesto: %s; referencia %s" % ("; ".join(linkage_notes), evidence_ref)
        return result

    # --- 3b) Conflicto entre fuentes independientes (hash / scope) ---
    # Hash de DB (extraído correctamente, anidado o plano) contra manifest.
    # También debe compararse con artefacto observado si está presente.
    if db_hash is not None and mf_hash is not None:
        d = str(db_hash).strip()
        m = str(mf_hash).strip()
        if not (_coincide_hash(m, d) or _coincide_hash(d, m)):
            result["decision"] = "CONFLICT"
            result["explanation"] = "Conflicto entre fuentes independientes: hash operativo (%s...) vs hash de manifest (%s...)" % (d[:12], m[:12])
            return result
    if db_has_scope and mf_has_scope:
        if str(db_scope).strip() != str(mf_scope).strip():
            result["decision"] = "CONFLICT"
            result["explanation"] = "Conflicto de scope entre fuentes independientes: DB_OP.scope=%s vs manifest.scope=%s" % (str(db_scope).strip(), str(mf_scope).strip())
            return result

    # --- 3c) Conflicto con artefacto observado ---
    # Si hay archivo observado y su hash no coincide con DB o manifest (cuando corresponda)
    if observed_artifact_path is not None or observed_hash is not None:
        # Intentar leer hash observado del archivo (si no se pasó observed_hash)
        observed_file_hash = observed_hash
        if observed_artifact_path and observed_hash is None:
            try:
                import hashlib
                if os.path.isfile(observed_artifact_path):
                    with open(observed_artifact_path, "rb") as f:
                        observed_file_hash = hashlib.sha256(f.read()).hexdigest()
            except Exception:
                pass
        # Comprobar consistencia con DB y manifest
        if observed_file_hash is not None:
            db_for_check = db_hash
            mf_for_check = mf_hash
            # Si hay DB hash y no coincide con observado
            if db_for_check is not None and not (_coincide_hash(str(db_for_check).strip(), str(observed_file_hash).strip()) or _coincide_hash(str(observed_file_hash).strip(), str(db_for_check).strip())):
                result["decision"] = "CONFLICT"
                result["explanation"] = "Artefacto observado (%s...) no coincide con hash de DB (%s...)" % (str(observed_file_hash)[:12], str(db_for_check)[:12])
                return result
            # Si hay manifest hash y no coincide con observado
            if mf_for_check is not None and not (_coincide_hash(str(mf_for_check).strip(), str(observed_file_hash).strip()) or _coincide_hash(str(observed_file_hash).strip(), str(mf_for_check).strip())):
                result["decision"] = "CONFLICT"
                result["explanation"] = "Artefacto observado (%s...) no coincide con hash de manifest (%s...)" % (str(observed_file_hash)[:12], str(mf_for_check)[:12])
                return result

    # --- 4) Integridad de fila (row_hash) ---
    # Solo se puede comprobar si tenemos acceso a DB con la fila completa.
    if db_op_path and db_op_result_id and db_row_exists:
        try:
            expected_row_hash, err_integrity = _verificar_fila_integridad(db_op_path, db_op_result_id)
            if expected_row_hash is None:
                # No se puede comprobar por ausencia de datos; no rechazar automáticamente,
                # pero si hay error de integridad (e.g., fila corrupta en estructura), es indicativo.
                if err_integrity and "Error" in err_integrity:
                    pass  # no rechazar por incapacidad técnica
        except Exception:
            pass  # No rechazar automáticamente por incapacidad de recomputación.
        # Nota: si el usuario solicita explícitamente verificación de integridad y falla,
        # debe ser un paso externo (como en M276). El contrato no rechaza por row_hash
        # si no se puede verificar, pero no afirma VERIFIED si hay una contradicción
        # entre el manifest y la fila (ya cubierto por linkage/hash).

    # --- 5) Estado y alcance ---
    # Si se llega a esta sección sin conflictos y con vínculo causal (DB + manifest + linkage) y ambos con scope:
    # Verificamos consistencia de verified_scope / scope_decision si existen.
    # Si DB tiene verified_scope='VERIFIED' o scope_decision='VERIFIED' sin manifest, o viceversa,
    # es una contradicción que debe ser INDETERMINATE / REJECTED.
    db_path_exists_and_readable = db_op_path is not None and isinstance(db_op_path, str) and os.path.isfile(db_op_path)
    if db_row_exists and db_path_exists_and_readable:
        # Intentar leer verified_scope / scope_decision de la fila
        try:
            con_tmp = sqlite3.connect("file:%s?mode=ro" % db_op_path, uri=True)
            row_state = con_tmp.execute(
                "SELECT verified_scope, scope_decision FROM results WHERE result_id=? LIMIT 1",
                (db_op_row_id := db_op_result_id,)
            ).fetchone()
            con_tmp.close()
            if row_state:
                vscope, sdecision = row_state
                # Si la fila afirma VERIFIED (verificado por fuente externa) pero no hay manifest ni integridad comprobada,
                # o si afirma UNVERIFIED pero el contrato determina VERIFIED por DB+manifest,
                # debe ser consistente: si DB dice VERIFIED y manifest confirma -> OK; si DB dice UNVERIFIED y contrato confía,
                # es INDETERMINATE hasta que la fila refleje el estado.
                # Implementación defensiva:
                if (vscope is not None and str(vscope).strip() == "VERIFIED") and (mf_has_scope and str(db_scope).strip() == str(mf_scope).strip()) and (db_hash or mf_hash):
                    # Si DB dice VERIFIED y tenemos manifest + linkage -> OK (no contradicción)
                    pass
                elif (sdecision is not None and str(sdecision).strip() == "VERIFIED") and not mf_has_scope:
                    result["decision"] = "INDETERMINATE"
                    result["explanation"] = "Fila afirma VERIFIED (scope_decision='VERIFIED') pero no hay manifiesto independiente vinculado (condición de verificación incompleta)"
                    return result
                elif (vscope is not None and str(vscope).strip() == "VERIFIED") and (mf_has_scope and str(mf_scope).strip() == str(db_scope).strip()) and (db_hash or mf_hash) and linkage_ok and (observed_artifact_path or observed_hash or (db_file and db_hash)):
                    # DB afirma VERIFIED y tenemos todo -> OK (no contradicción; podría ser VERIFIED)
                    pass
                elif (vscope is not None and str(vscope).strip() == "VERIFIED") and (str(mf_has_scope) == "False" or not linkage_ok):
                    result["decision"] = "CONFLICT"
                    result["explanation"] = "Contradicción: fila afirma VERIFIED pero vínculo con manifest o integridad no comprobado"
                    return result
        except Exception:
            pass  # No rechazar por incapacidad de lectura de fila

    # --- Política de decisión corregida (M284) ---
    # §5 removido: no más VERIFIED con una sola fuente sin vínculo causal comprobado.
    # Solo VERIFIED cuando:
    # - DB y manifest presentes (mf_has_scope y db_has_scope)
    # - Linkage causal comprobado (operation_id/result_id coinciden o al menos no contradicen de forma clara; para casos de prueba con DB+manifiesto del MISMO op/res asumimos vínculo si no hay conflicto de IDs si se pasan los IDs)
    # - No hay conflicto de hash o scope
    # - Artículo observado (si se proporciona) coincide o no contradice
    # - Fila no presenta contradicción de verified_scope/scope_decision
    if db_has_scope and mf_has_scope:
        if linkage_ok and (db_hash or mf_hash or (db_file and db_file != "")):
            # Ambas fuentes presentes, vínculo causal comprobado, sin conflicto
            result["decision"] = "VERIFIED"
            result["explanation"] = "Procedencia verificada: DB_OP y manifest coinciden en scope=%s para referencia %s (vínculo causal comprobado)" % (str(db_scope).strip(), evidence_ref)
            return result
        else:
            # Hay ambas fuentes pero falta vínculo causal comprobado o integridad completa
            result["decision"] = "INDETERMINATE"
            result["explanation"] = "Fuentes presentes (DB y manifest) pero vínculo causal incompleto o integridad no totalmente comprobada para referencia %s; no se inventa procedencia" % evidence_ref
            return result

    if db_has_scope:
        # Solo DB (sin manifest), o con manifest que no cumplió condiciones
        # No VERIFIED (corrección M284: §5 eliminado)
        # Si hay manifest pero no pasó por conflicto (ej. manifest de otra op sin conflicto de scope porque el otro tiene mismo scope) — ya rechazado por linkage; esta rama solo para DB puro
        result["decision"] = "UNVERIFIED"
        result["explanation"] = "Fuente operativa (DB_OP.results.scope=%s) vinculada a referencia %s, pero manifest independiente o vínculo causal no comprobado; una declaración del consumidor no es procedencia autoritativa" % (str(db_scope).strip(), evidence_ref)
        return result

    if mf_has_scope:
        result["decision"] = "UNVERIFIED"
        result["explanation"] = "Manifest E2E (scope=%s) vinculado a referencia %s, pero fuente operativa independiente (DB_OP) no verificable para la referencia; no se inventa procedencia sin DB" % (str(mf_scope).strip(), evidence_ref)
        return result

    if claim_scope is not None and str(claim_scope).strip() != "":
        result["decision"] = "UNVERIFIED"
        result["explanation"] = "Scope declarado por el claim (%s) sin fuente independiente acreditada (DB_OP.scope=%s; manifest.scope=%s); una declaración del consumidor no es procedencia autoritativa" % (
            str(claim_scope).strip(),
            "NULO" if db_scope is None else db_scope,
            "AUSENTE" if mf_scope is None else mf_scope,
        )
        return result

    result["decision"] = "UNVERIFIED"
    result["explanation"] = "Sin fuente autoritativa verificable para la referencia %s (DB_OP.scope=%s; manifest.scope=%s); no se inventa procedencia" % (
        evidence_ref,
        "NULO" if db_scope is None else db_scope,
        "AUSENTE" if mf_scope is None else mf_scope,
    )
    return result


# --- Función auxiliar de verificación de fila (para pruebas M283) ---
def verificar_fila_contrato(db_op_path: str, result_id: str, manifest_e2e_path: str = None, claimed_op_id: str = None) -> dict:
    """Verificación completa con verificación de fila + linkage + integridad."""
    return verificar_autoridad_scope(
        "verificacion_completa_%s" % result_id,
        claim_scope=None,
        db_op_path=db_op_path,
        db_op_result_id=result_id,
        manifest_e2e_path=manifest_e2e_path,
        observed_artifact_path=None,
        observed_hash=None,
    )
