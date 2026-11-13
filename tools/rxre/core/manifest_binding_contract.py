#!/usr/bin/env python3
"""RXRE-MISSION-301 — Contrato de vinculación verificable manifest–artefacto.
Nuevo archivo. No modifica componentes protegidos ni DB_OP."""
import sqlite3, os, json, hashlib, stat, time, pathlib

ESTADOS_CONOCIDOS = {"VERIFIED", "UNVERIFIED", "AUTHORIZED", "PENDING", "REJECTED", "INVALID", "INDETERMINATE", "CONFLICT", None}

def _detectar_duplicados(pairs):
    d = {}
    duplicados = set()
    for k, v in pairs:
        if k in d:
            duplicados.add(k)
        d[k] = v
    return d, duplicados

def _hook_con_duplicados(colector):
    """object_pairs_hook que devuelve dict plano y registra claves duplicadas en cualquier nivel."""
    def hook(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                colector.add(k)
            d[k] = v
        return d
    return hook

def _sha256_bytes(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()

def _file_identity_snapshot(path):
    st = os.stat(path)
    return {"dev": st.st_dev, "ino": st.st_ino, "size": st.st_size, "mtime_ns": st.st_mtime_ns, "mode": st.st_mode}

def _resolucion_equivoca(manifest_dict, key_artifact):
    """Resuelve la ruta del artefacto desde el manifest; rechaza ambigüedad/symlink."""
    path_declared = manifest_dict.get("artefacto_path") or manifest_dict.get("artifact_path")
    if not path_declared:
        return None, "manifest: ruta del artefacto ausente (artefacto_path/artifact_path)"
    # Resolver absoluto
    abs_path = os.path.abspath(os.path.expanduser(path_declared))
    # Verificar existencia y archivo regular (no directorio/symlink si no se permite)
    if not os.path.isfile(abs_path):
        return None, "manifest: ruta no es archivo regular: %s" % abs_path
    # Detectar symlink: comparar realpath con la ruta declarada
    real_path = os.path.realpath(abs_path)
    if real_path != abs_path:
        if not os.path.islink(abs_path):
            # Si no es symlink pero realpath difiere, puede ser por montajes; documentamos
            pass
        else:
            # Symlink detectado: informar explícitamente
            pass
    # Resolver a ruta inequívoca
    resolved = os.path.abspath(real_path)
    return resolved, None

def validar_vinculacion(manifest_path, artifact_path_esperado=None,
                         scope_esperado=None, registro_row_hash=None,
                         hash_esperado_registro=None, db_op_path=None,
                         db_op_result_id=None):
    """Validación del vínculo manifest→artefacto con evidencia verificable.
    Devuelve dict con 'decision', 'explanation', 'hash_computado', 'hash_declarado',
    'file_identity', 'scope', 'duplicados', etc."""
    result = {
        "decision": "INSUFFICIENT",
        "explanation": "",
        "manifest_path": manifest_path,
        "hash_computado": None,
        "hash_declarado": None,
        "hash_integridad_declarado": None,
        "hash_integridad_observado": None,
        "hash_fuentes_anidado": None,
        "hash_fuentes_plano": None,
        "scope_declared": None,
        "scope_decision": None,
        "scope_esperado": scope_esperado,
        "duplicados": False,
        "archivo_resuelto": None,
        "archivo_identity": None,
        "archivo_size": None,
        "archivo_mtime_ns": None,
        "archivo_symlink": False,
        "file_identity_snapshot": None,
        "referencia_db_op_id": None,
        "referencia_result_id": None,
    }
    # 1. Existencia y lectura del manifest
    if not manifest_path or not os.path.isfile(manifest_path):
        result["decision"] = "REJECTED"
        result["explanation"] = "manifest inexistente o inaccesible: %s" % manifest_path
        return result
    # Resolver ruta real del manifest (para evitar symlink ambiguo)
    manifest_real = os.path.abspath(os.path.realpath(manifest_path))
    # 2. Cargar JSON; detectar duplicados de claves
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        duplicados = set()
        manifest_dict = json.load(open(manifest_path, "r"), object_pairs_hook=_hook_con_duplicados(duplicados))
        result["duplicados"] = bool(duplicados)
        if duplicados:
            result["decision"] = "REJECTED"
            result["explanation"] = "manifest con claves duplicadas (inconsistencia): %s" % sorted(duplicados)
            # No salir: seguir para capturar la mayor evidencia posible antes de rechazar
    except Exception as exc:
        result["decision"] = "REJECTED"
        result["explanation"] = "manifest malformado o no legible: %s" % str(exc)
        return result
    # 3. Resolver ruta del artefacto de forma inequívoca
    resolved_artifact, err_artifact = _resolucion_equivoca(manifest_dict, "artefacto_path")
    result["archivo_resuelto"] = resolved_artifact
    if err_artifact:
        result["decision"] = "REJECTED"
        result["explanation"] = err_artifact
        return result

    # Comprobar que el artefacto existe como archivo regular y no está vacío sin intención
    if not os.path.isfile(resolved_artifact):
        result["decision"] = "REJECTED"
        result["explanation"] = "artefacto no es archivo regular: %s" % resolved_artifact
        return result
    # Verificar que el artefacto exista como archivo regular y no sea symlink (referencia ambigua)
    if not os.path.isfile(resolved_artifact):
        result["decision"] = "REJECTED"
        result["explanation"] = "artefacto no es archivo regular: %s" % resolved_artifact
        return result
    # Symlink: referencia ambigua (puede re-apuntarse entre validación y uso) -> se rechaza
    if os.path.islink(os.path.abspath(os.path.expanduser(manifest_dict.get("artefacto_path") or manifest_dict.get("artifact_path")))):
        result["archivo_symlink"] = True
        result["decision"] = "REJECTED"
        result["explanation"] = "ruta del artefacto es enlace simbólico (referencia ambigua): %s" % resolved_artifact
        return result

    # 3-bis. Vínculo inequívoco: la ruta resuelta del artefacto del manifest debe ser la esperada
    if artifact_path_esperado:
        esperado_real = os.path.abspath(os.path.realpath(artifact_path_esperado))
        if esperado_real != resolved_artifact:
            result["decision"] = "REJECTED"
            result["explanation"] = (result.get("explanation", "") +
                                     "; artefacto del manifest no coincide con el artefacto esperado (%s vs %s)" % (resolved_artifact, esperado_real))
            return result
    # Tamaño y mtime del archivo
    st_artifact = os.stat(resolved_artifact)
    result["archivo_size"] = st_artifact.st_size
    result["archivo_mtime_ns"] = st_artifact.st_mtime_ns
    result["archivo_identity"] = {"dev": st_artifact.st_dev, "ino": st_artifact.st_ino, "mode": st_artifact.st_mode}

    # 4. Cálculo independiente del hash a partir de los bytes del archivo (no confiar en cliente)
    computed_hash = _sha256_bytes(resolved_artifact)
    result["hash_computado"] = computed_hash

    # 5. Leer todos los hashes declarados en el manifest y comprobar consistencia entre ellos
    # Top-level hash
    declared_top = manifest_dict.get("artefacto_hash_sha256") or manifest_dict.get("hash_sha256") or manifest_dict.get("hash_fuentes",{}).get("plano") or manifest_dict.get("hash_fuentes",{}).get("anidado")
    # Integridad (observado/declarado)
    integridad = manifest_dict.get("integridad_artefacto",{})
    integridad_fuentes = integridad.get("fuentes",{})
    hash_fuentes_anidado = manifest_dict.get("hash_fuentes",{}).get("anidado")
    hash_fuentes_plano = manifest_dict.get("hash_fuentes",{}).get("plano")
    hash_declarado = integridad.get("hash_declarado")
    hash_observado = integridad.get("hash_observado")

    result["hash_declarado"] = declared_top
    result["hash_integridad_declarado"] = hash_declarado
    result["hash_integridad_observado"] = hash_observado
    result["hash_fuentes_anidado"] = hash_fuentes_anidado
    result["hash_fuentes_plano"] = hash_fuentes_plano

    # Comprobar consistencia interna de los hashes del manifest (todos presentes deben coincidir)
    hashes_manifest = []
    for k, v in [("top", declared_top),
                 ("integridad_declarado", hash_declarado),
                 ("integridad_observado", hash_observado),
                 ("fuentes_anidado", hash_fuentes_anidado),
                 ("fuentes_plano", hash_fuentes_plano)]:
        if v is not None and v != "" and v != "null" and not (isinstance(v, str) and v.startswith("null")):
            # Algunos valores pueden ser string "null" literal (como en JSON con null -> str)
            # Filtramos valores que parecen reales (longitud 64, hexadecimales)
            if isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v.lower()):
                hashes_manifest.append((k, v))
    # Si hay al menos un hash real, todos los hashes reales deben ser iguales entre sí y con el calculado
    hashes_vals = list({v for _, v in hashes_manifest})
    if len(hashes_vals) > 1:
        result["decision"] = "REJECTED"
        result["explanation"] = "inconsistencia interna de hashes en manifest: %s" % sorted({k: v for k, v in hashes_manifest})
        # Continuar para capturar más evidencia
    elif len(hashes_vals) == 1:
        hash_manifesto = hashes_vals[0]
        if computed_hash != hash_manifesto:
            result["decision"] = "REJECTED"
            result["explanation"] = "hash del manifest (%s...) no coincide con hash calculado del archivo (%s...)" % (hash_manifesto[:16], computed_hash[:16])
    else:
        # No hay hash en manifest: se documenta como ausencia; no se rechaza automáticamente (podría ser un manifest sin integridad declarada), pero para verificación VERIFICADA debe requerirse al menos un hash.
        result["explanation"] = result.get("explanation", "") + "; manifest sin hash de integridad declarable (no se rechaza automáticamente, pero se documenta ausencia)"

    # Si el manifest aún no fue rechazado y hay inconsistencia de hash, forzar REJECTED
    # Si hay duplicados, mantener REJECTED (ya establecido)
    if result.get("explanation", "").startswith("manifest") and result.get("decision") == "INSUFFICIENT" and result.get("explanation", "").startswith("manifest"):
        # Ya rechazado por manifest ausente/malformado; no sobrescribir
        pass

    # 6. Verificación de `scope` y `scope_decision`
    scope_declared = manifest_dict.get("scope") or manifest_dict.get("e2e_scope") or manifest_dict.get("scope_operativo") or manifest_dict.get("declared_scope")
    scope_decision_manifest = manifest_dict.get("scope_decision") or manifest_dict.get("decision")
    result["scope_declared"] = scope_declared
    result["scope_decision"] = scope_decision_manifest

    if scope_esperado is not None and scope_esperado != "" and scope_esperado is not None:
        if scope_declared is not None and str(scope_declared).strip() != "" and str(scope_declared).strip() != str(scope_esperado).strip():
            result["decision"] = "REJECTED"
            result["explanation"] = result.get("explanation", "") + "; conflicto de scope: manifest=%s esperado=%s" % (str(scope_declared), str(scope_esperado))
        if scope_decision_manifest is not None and str(scope_decision_manifest).strip() != "" and str(scope_decision_manifest).strip() not in ESTADOS_CONOCIDOS:
            result["decision"] = "REJECTED"
            result["explanation"] = result.get("explanation", "") + "; scope_decision no reconocido: %s" % str(scope_decision_manifest)

    # 7. Verificación de referencias de DB (operación/resultado) si se solicita
    if db_op_path and db_op_result_id:
        try:
            c = sqlite3.connect("file:%s?mode=ro" % db_op_path, uri=True)
            row_op = c.execute("SELECT result_id FROM results WHERE result_id=? LIMIT 1", (db_op_result_id,)).fetchone()
            c.close()
            result["referencia_result_id"] = db_op_result_id
            result["referencia_db_op_id"] = manifest_dict.get("operation_id")
            # No reemplazar la decisión por esta verificación; solo documentar.
            if not row_op:
                result["explanation"] = result.get("explanation", "") + "; referencia DB no encontrada para result_id=%s" % db_op_result_id
        except Exception as exc:
            result["explanation"] = result.get("explanation", "") + "; error leyendo referencia DB: %s" % str(exc)

    # 8. Comparación con hash esperado del registro (si se pasa)
    if hash_esperado_registro and computed_hash:
        if computed_hash != hash_esperado_registro:
            result["decision"] = result.get("decision", "INSUFFICIENT")
            # Si ya estaba REJECTED, no sobrescribir; si no, actualizar a REJECTED
            if result.get("explanation", "").startswith("hash del manifest") or result.get("explanation", "").startswith("manifest"):
                pass  # mantener REJECTED existente
            else:
                result["decision"] = "REJECTED"
                result["explanation"] = result.get("explanation", "") + "; hash esperado del registro (%s...) no coincide con hash calculado (%s...)" % (str(hash_esperado_registro)[:16], computed_hash[:16])

    # 9. TOCTOU: capturar snapshot de identidad del archivo en el momento de la validación
    result["file_identity_snapshot"] = result.get("archivo_identity")

    # Si ninguna verificación falló y tenemos un hash consistente y archivo existente, marcar PASS
    # Pero si hay duplicados o hashes inconsistentes, debe seguir REJECTED (ya establecido)
    if result.get("decision") not in ("REJECTED", "INVALID") and result.get("hash_computado") and result.get("explanation", "") == "":
        result["decision"] = "PASS"
        result["explanation"] = "vínculo manifest→artefacto verificado: hash independiente coincide con manifest; archivo existente; sin inconsistencias. TOCTOU detectado (snapshot capturado) pero NO prevenido."
    elif result.get("decision") == "INSUFFICIENT" and len(str(result.get("explanation", ""))) > 0 and not result.get("explanation", "").startswith("manifest inexistente") and not result.get("explanation", "").startswith("inconsistencia"):
        # Si hay solo una nota de ausencia (no rechazo fuerte), documentar
        if result.get("hash_computado") and result.get("hash_declarado") is not None:
            result["explanation"] = (result.get("explanation", "") + "; validación parcial: archivo y hash presentes; no hay referencia DB o scope esperado para confirmar.")
    return result

def validar_cambio_snapshot(path_actual, snapshot_esperado):
    """Comprobar si el archivo ha cambiado respecto al snapshot (TOCTOU: detección, no prevención)."""
    try:
        st = os.stat(path_actual)
        snapshot_real = {"dev": st.st_dev, "ino": st.st_ino, "size": st.st_size, "mtime_ns": st.st_mtime_ns}
        return snapshot_real == snapshot_esperado, snapshot_real
    except Exception:
        return False, None
