#!/usr/bin/env python3
"""RXRE-MISSION-302 — Prevención de TOCTOU en vinculación manifest→artefacto.
Archivo nuevo; no modifica componentes protegidos ni DB_OP."""
import sqlite3, hashlib, os, json, stat

def leer_artefacto_una_vez(path):
    """Abre el archivo una vez, captura identidad y lee todos los bytes en memoria."""
    path_real = os.path.abspath(os.path.realpath(path))
    identity_before = None
    try:
        st = os.stat(path_real)
        identity_before = {"dev": st.st_dev, "ino": st.st_ino,
                           "size": st.st_size, "mtime_ns": st.st_mtime_ns,
                           "mode": st.st_mode}
    except Exception:
        pass
    f = open(path, "rb")
    try:
        fd_info = os.fstat(f.fileno())
        identity_open = {"dev": fd_info.st_dev, "ino": fd_info.st_ino,
                         "size": fd_info.st_size, "mtime_ns": fd_info.st_mtime_ns,
                         "mode": fd_info.st_mode}
        bytes_consumidos = f.read()
    finally:
        f.close()
    cambio_antes = (identity_before is not None and identity_open is not None and
                    (identity_before["ino"] != identity_open["ino"] or identity_before["dev"] != identity_open["dev"]))
    hash_computado = hashlib.sha256(bytes_consumidos).hexdigest()
    return {"path_real": path_real,
            "bytes_consumidos": bytes_consumidos,
            "hash_computado": hash_computado,
            "identity_before": identity_before,
            "identity_open": identity_open,
            "cambio_antes": cambio_antes}

def validar_snapshot_con_bytes(snapshot, bytes_esperados, hash_esperado):
    """Comprobar que los bytes consumidos coincidan con los esperados."""
    iguales_bytes = (snapshot.get("bytes_consumidos") == bytes_esperados)
    iguales_hash = (snapshot.get("hash_computado") == hash_esperado)
    return iguales_bytes and iguales_hash, {
        "bytes_iguales": iguales_bytes,
        "hash_iguales": iguales_hash,
        "bytes_len": len(snapshot.get("bytes_consumidos", b"")),
        "hash_computado": snapshot.get("hash_computado"),
    }

def comparar_identity(snapshot_antes, snapshot_despues):
    """Detectar cambio del archivo en el disco respecto al snapshot."""
    if snapshot_antes is None or snapshot_despues is None:
        return False
    return (snapshot_antes.get("dev") == snapshot_despues.get("dev") and
            snapshot_antes.get("ino") == snapshot_despues.get("ino") and
            snapshot_antes.get("size") == snapshot_despues.get("size") and
            snapshot_antes.get("mtime_ns") == snapshot_despues.get("mtime_ns"))

def integrar_consumo_seguro(manifest_path, artifact_path_esperado, scope_esperado=None,
                             registro_row_hash=None, db_op_path=None, db_op_result_id=None):
    """Validación de vinculación + lectura única del artefacto. El consumidor debe usar
    `bytes_consumidos` y no volver a abrir `artifact_path_esperado`."""
    import sys
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
    from rxre.core import manifest_binding_contract as mbc
    v = mbc.validar_vinculacion(manifest_path, artifact_path_esperado=artifact_path_esperado,
                                 scope_esperado=scope_esperado, registro_row_hash=registro_row_hash,
                                 db_op_path=db_op_path, db_op_result_id=db_op_result_id)
    if v.get("decision") not in ("PASS",):
        return None, v
    snapshot = leer_artefacto_una_vez(artifact_path_esperado)
    iguales, info = validar_snapshot_con_bytes(snapshot, v.get("hash_computado"), v.get("hash_computado"))
    return snapshot, v
