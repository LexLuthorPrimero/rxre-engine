#!/usr/bin/env python3
"""RXRE-M316 — AUTORIDAD DE PRUEBA (AISLADA / NO PRODUCCIÓN).
Emite y verifica autorizaciones firmadas con una clave Ed25519 de PRUEBA.
Separación emisor/ejecutor: el emisor usa su propia clave privada; el ejecutor
solo conoce la clave pública y NO puede emitir autorizaciones aceptadas.
NO es autoridad real (DB_AUTH_ACTOR_M294 / DBOP_ACCESS_M295 pendientes)."""
import os, sys, json, hashlib, time, getpass, secrets

if "/home/lucas/Escritorio/rxre/tools" not in sys.path:
    sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.prototype.m316 import ed25519_ref

TEST_PRIVATE_KEY_FILE = "/tmp/rxre_316_test_authority_priv.bin"
TEST_PUBLIC_KEY_FILE = "/tmp/rxre_316_test_authority_pub.bin"


def identidad_del_sistema():
    """Identidad del proceso obtenida del SISTEMA (no de un campo autodeclarado)."""
    try:
        usuario = getpass.getuser()
    except Exception:
        usuario = "uid:%s" % os.getuid()
    return {"usuario": usuario, "uid": os.getuid(), "pid": os.getpid()}


def _claves_de_prueba():
    if not os.path.isfile(TEST_PRIVATE_KEY_FILE):
        priv = secrets.token_bytes(32)
        with open(TEST_PRIVATE_KEY_FILE, "wb") as f:
            f.write(priv)
        os.chmod(TEST_PRIVATE_KEY_FILE, 0o600)
    with open(TEST_PRIVATE_KEY_FILE, "rb") as f:
        priv = f.read()
    pub = ed25519_ref.publickey(priv)
    with open(TEST_PUBLIC_KEY_FILE, "wb") as f:
        f.write(pub)
    return priv, pub


def issue_authorization(operation_id, scope, manifest_hash_sha256, nonce,
                        actor_override=None, ttl_s=3600, issued_at=None):
    """Emite autorización de PRUEBA. El actor autorizado se obtiene del sistema
    salvo `actor_override` (usado solo para probar el caso adversarial 'actor distinto')."""
    priv, pub = _claves_de_prueba()
    ident = identidad_del_sistema()
    actor = actor_override if actor_override else ident["usuario"]
    now = time.time()
    payload = {
        "authority_type": "TEST_PROTOTYPE_M316",
        "authority_reference": "RXRE-MISSION-316-ISOLATED-TRUST-PROTOTYPE",
        "actor": actor,
        "actor_source": "system:uid:%s" % ident["uid"],
        "issuer_uid": ident["uid"],
        "operation_id": operation_id,
        "scope": scope,
        "manifest_hash_sha256": manifest_hash_sha256,
        "nonce": nonce,
        "issued_at_epoch": now if issued_at is None else issued_at,
        "expires_at_epoch": (now if issued_at is None else issued_at) + ttl_s,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
    sig = ed25519_ref.sign(payload_bytes, priv)
    return {"payload": payload,
            "signature_hex": sig.hex(),
            "public_key_hex": pub.hex(),
            "algorithm": "Ed25519_REF_M316_PROTOTYPE",
            "authority": "TEST_PROTOTYPE_NOT_PRODUCTION"}


def verify_authorization(auth, expected_operation_id, expected_scope, expected_manifest_hash,
                          now=None, public_key_expected=None):
    """Verificación de la autorización de PRUEBA.
    Rechaza: estructura inválida, firma malformada, actor no coincidente con la identidad
    del proceso, operación distinta, alcance distinto, hash de manifiesto distinto,
    caducada, emitida en el futuro, autoridad de tipo desconocido."""
    now = time.time() if now is None else now
    out = {"decision": "REJECTED", "explanation": "", "checks": {}}
    if not isinstance(auth, dict) or "payload" not in auth or "signature_hex" not in auth:
        out["explanation"] = "estructura de autorización incompleta"; return out
    payload = auth.get("payload") or {}
    try:
        sig = bytes.fromhex(auth.get("signature_hex", ""))
        pub = bytes.fromhex(auth.get("public_key_hex", ""))
    except Exception:
        out["explanation"] = "firma o clave malformada"; return out
    if len(sig) != 64:
        out["explanation"] = "longitud de firma inválida (%d)" % len(sig); return out
    if len(pub) != 32:
        out["explanation"] = "longitud de clave pública inválida (%d)" % len(pub); return out
    if public_key_expected is not None and pub != public_key_expected:
        out["explanation"] = "clave pública no corresponde a la autoridad de prueba"; return out
    # firma: verificación criptográfica real Ed25519 (RFC 8032)
    payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
    sig_ok = ed25519_ref.verify(message=payload_bytes, signature=sig, pk=pub)
    out["checks"]["firma_criptografica_ed25519"] = sig_ok
    if not sig_ok:
        out["explanation"] = "firma Ed25519 no verificada (payload alterado o clave publica ajena)"
        return out
    # actor: debe coincidir con la identidad del SISTEMA del proceso ejecutor
    ident = identidad_del_sistema()
    if payload.get("actor") != ident["usuario"]:
        out["explanation"] = "actor de la autorización (%s) no coincide con la identidad del proceso (%s)" % (
            payload.get("actor"), ident["usuario"])
        out["checks"]["actor_coincide"] = False
        return out
    out["checks"]["actor_coincide"] = True
    # tipo de autoridad
    if payload.get("authority_type") != "TEST_PROTOTYPE_M316":
        out["explanation"] = "tipo de autoridad desconocido"; return out
    # operación / alcance / manifest
    if payload.get("operation_id") != expected_operation_id:
        out["explanation"] = "operación no coincide (autorización no reutilizable para otra operación)"; return out
    if payload.get("scope") != expected_scope:
        out["explanation"] = "alcance incorrecto"; return out
    if payload.get("manifest_hash_sha256") != expected_manifest_hash:
        out["explanation"] = "hash de manifiesto no coincide"; return out
    # caducidad
    if float(payload.get("expires_at_epoch", 0)) < now:
        out["explanation"] = "autorización caducada"; return out
    if float(payload.get("issued_at_epoch", 0)) > now + 5:
        out["explanation"] = "autorización emitida en el futuro"; return out
    # nonce (identificador único)
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or len(nonce) < 8:
        out["explanation"] = "nonce ausente o insuficiente"; return out
    out["checks"]["nonce"] = nonce
    out["decision"] = "PROVISIONAL_AUTHORITY_PROTOTYPE"
    out["explanation"] = ("autorización de prueba válida (PROTOTYPE M316): estructura, actor del sistema, "
                          "operación, alcance, manifest, caducidad y nonce verificados. "
                          "NO es autoridad de producción (DB_AUTH_ACTOR_M294 / DBOP_ACCESS_M295 pendientes).")
    return out
