#!/usr/bin/env python3
"""RXRE-MISSION-303 — Instantánea estable de evidencia.
Captura una única secuencia de bytes, calcula su hash sobre esa misma secuencia,
valida el manifiesto contra ese hash y entrega al consumidor únicamente esos bytes.
Archivo nuevo; no modifica contratos protegidos, core/store.py, machine.py ni core/evidence_integrity.py."""
import hashlib, json, os, sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import manifest_binding_contract as mbc


class EvidenceSnapshot:
    """Contiene exclusivamente los bytes capturados y su identidad. El consumidor
    NO debe reabrir la ruta original: debe usar `bytes_consumidos`."""
    def __init__(self, bytes_consumidos, hash_capturado, identity_before, identity_open,
                 artifact_path, manifest_path=None, scope_esperado=None,
                 hash_esperado_manifest=None, hash_esperado_registro=None,
                 decision=None, explanation=""):
        self.bytes_consumidos = bytes_consumidos
        self.hash_capturado = hash_capturado
        self.identity_before = identity_before
        self.identity_open = identity_open
        self.artifact_path = artifact_path
        self.manifest_path = manifest_path
        self.scope_esperado = scope_esperado
        self.hash_esperado_manifest = hash_esperado_manifest
        self.hash_esperado_registro = hash_esperado_registro
        self.decision = decision
        self.explanation = explanation

    def __bool__(self):
        return self.decision == "PASS" and bool(self.bytes_consumidos)


def capturar_evidencia(artifact_path, mutador=None):
    """Abre el descriptor UNA vez y lee los bytes inmediatamente.
    El hash se calcula sobre esos mismos bytes (nunca sobre una segunda lectura).
    `mutador` es un punto de inyección determinista (solo pruebas): se invoca con el
    descriptor ya abierto y antes de la lectura, para simular cambios concurrentes."""
    path_real = os.path.abspath(os.path.realpath(artifact_path))
    identity_before = None
    try:
        st = os.stat(path_real)
        identity_before = {"dev": st.st_dev, "ino": st.st_ino, "size": st.st_size,
                           "mtime_ns": st.st_mtime_ns, "mode": st.st_mode}
    except Exception:
        pass
    f = open(artifact_path, "rb")
    try:
        fd = os.fstat(f.fileno())
        identity_open = {"dev": fd.st_dev, "ino": fd.st_ino, "size": fd.st_size,
                         "mtime_ns": fd.st_mtime_ns, "mode": fd.st_mode}
        # Punto de inyección determinista (solo pruebas): el mutador actúa con el
        # descriptor ya abierto y antes de la lectura (cambio concurrente controlado).
        if mutador is not None:
            mutador(path_real, f)
        h = hashlib.sha256()
        buf = bytearray()
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            buf.extend(chunk)
            h.update(chunk)
        bytes_consumidos = bytes(buf)
        hash_capturado = h.hexdigest()
    finally:
        f.close()
    return EvidenceSnapshot(bytes_consumidos, hash_capturado, identity_before,
                            identity_open, artifact_path)


def _hash_esperado_del_manifest(manifest_path):
    """Extrae el hash declarado por el manifest (fuente de verdad del vínculo)."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
    except Exception:
        return None
    return (m.get("artefacto_hash_sha256") or m.get("hash_sha256") or
            (m.get("hash_fuentes") or {}).get("plano") or
            (m.get("hash_fuentes") or {}).get("anidado"))


def validar_y_capturar(manifest_path, artifact_path, scope_esperado=None,
                        hash_esperado_registro=None, db_op_path=None,
                        db_op_result_id=None):
    """Operación única: validar el manifest, capturar los bytes y comprobar la igualdad
    `hash(bytes_consumidos) == hash_esperado_del_manifest` y `== hash_esperado_registro`.
    Devuelve (snapshot, dict) con la decisión final."""
    hash_manifest = _hash_esperado_del_manifest(manifest_path)
    snap = capturar_evidencia(artifact_path)
    snap.manifest_path = manifest_path
    snap.scope_esperado = scope_esperado
    snap.hash_esperado_manifest = hash_manifest
    snap.hash_esperado_registro = hash_esperado_registro

    # (1) Igualdad fundamental: bytes capturados == bytes validados
    hash_bytes = snap.hash_capturado
    if hash_manifest is None:
        snap.decision = "INSUFFICIENT"
        snap.explanation = "manifest sin hash de artefacto: no se puede validar el vinculo"
        return snap, {"decision": snap.decision, "explanation": snap.explanation,
                      "hash_manifest": hash_manifest, "hash_capturado": hash_bytes,
                      "bytes_len": len(snap.bytes_consumidos)}
    if hash_bytes != hash_manifest:
        snap.decision = "REJECTED"
        snap.explanation = ("bytes capturados (hash=%s) NO coinciden con el hash esperado del "
                            "manifest (hash=%s): la fuente cambio durante la captura o el manifest "
                            "no describe estos bytes" % (hash_bytes[:16], hash_manifest[:16]))
        return snap, {"decision": snap.decision, "explanation": snap.explanation,
                      "hash_manifest": hash_manifest, "hash_capturado": hash_bytes,
                      "bytes_len": len(snap.bytes_consumidos)}
    if hash_esperado_registro and hash_bytes != hash_esperado_registro:
        snap.decision = "REJECTED"
        snap.explanation = ("bytes capturados (hash=%s) NO coinciden con el hash esperado por el "
                            "registro (hash=%s)" % (hash_bytes[:16], hash_esperado_registro[:16]))
        return snap, {"decision": snap.decision, "explanation": snap.explanation,
                      "hash_manifest": hash_manifest, "hash_capturado": hash_bytes,
                      "bytes_len": len(snap.bytes_consumidos)}

    # (2) Validación de vinculación completa (M301) sobre el MISMO archivo
    v = mbc.validar_vinculacion(manifest_path, artifact_path_esperado=artifact_path,
                                 scope_esperado=scope_esperado,
                                 hash_esperado_registro=hash_esperado_registro,
                                 db_op_path=db_op_path, db_op_result_id=db_op_result_id)
    if v.get("decision") != "PASS":
        snap.decision = "REJECTED" if v.get("decision") in ("REJECTED", "INVALID") else v.get("decision")
        snap.explanation = "validacion de vinculacion no superada: %s (%s)" % (v.get("decision"), v.get("explanation", "")[:140])
        return snap, {"decision": snap.decision, "explanation": snap.explanation,
                      "hash_manifest": hash_manifest, "hash_capturado": hash_bytes,
                      "bytes_len": len(snap.bytes_consumidos), "validacion": v}

    # (3) Consistencia de referencia: el archivo fisico actual debe ser el MISMO objeto
    #     (dev, ino) que el descriptor de captura; si no, la referencia no es inequivoca.
    identidad_actual = None
    try:
        st = os.stat(artifact_path)
        identidad_actual = {"dev": st.st_dev, "ino": st.st_ino}
    except Exception:
        pass
    cambio_referencia = False
    if identidad_actual and snap.identity_open:
        cambio_referencia = (identidad_actual["ino"] != snap.identity_open["ino"] or
                             identidad_actual["dev"] != snap.identity_open["dev"])
    snap.decision = "PASS" if not cambio_referencia else "PASS_PARTIAL"
    snap.explanation = ("bytes capturados == bytes validados (hash=%s, %d bytes); archivo fisico "
                        "identico al descriptor de captura" % (hash_bytes[:16], len(snap.bytes_consumidos))) \
        if not cambio_referencia else \
        ("bytes capturados == bytes validados (hash=%s); el archivo fisico fue reemplazado despues "
         "de la captura: bytes estables pero referencia no inequivoca (limite documentado)" % hash_bytes[:16])
    return snap, {"decision": snap.decision, "explanation": snap.explanation,
                  "hash_manifest": hash_manifest, "hash_capturado": hash_bytes,
                  "bytes_len": len(snap.bytes_consumidos),
                  "cambio_referencia": cambio_referencia, "validacion": v}


def consumir_bytes(snapshot):
    """Entrega al consumidor EXCLUSIVAMENTE los bytes capturados y validados.
    No se reabre ninguna ruta. Devuelve (bytes, hash)."""
    if snapshot is None or not snapshot.bytes_consumidos:
        return None, None
    return snapshot.bytes_consumidos, snapshot.hash_capturado


def crear_instantanea_privada(snapshot, destino):
    """Crea una copia privada inmutable de los bytes capturados (para consumidores que
    exigen una ruta). El consumidor debe usar ESTA ruta, no la original mutable."""
    if snapshot is None or not snapshot.bytes_consumidos:
        return None
    with open(destino, "wb") as f:
        f.write(snapshot.bytes_consumidos)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(destino, 0o400)
    except Exception:
        pass
    return destino
