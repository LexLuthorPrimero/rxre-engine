#!/usr/bin/env python3
"""RXRE-M335 — Proveedor de confianza MÍNIMO (administrativo). NO auto-provisiona.
Requiere confirmación explícita. Escribe fuera del repo por defecto. Rechaza rutas inseguras.
Solo para uso por el propietario/administrador legítimo.
"""
import argparse, json, os, stat, sys, hashlib, hmac
from datetime import datetime, timezone

REPO = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, REPO + "/m326_isolated/scripts")
import m326_auth_verifier as av

def _secure_write(path, data_bytes, mode=0o600):
    # crear con umask restrictivo, comprobar que no es symlink
    if os.path.lexists(path):
        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            raise SystemExit("REFUSE: %s es symlink" % path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data_bytes)
    finally:
        os.close(fd)
    os.chmod(path, mode)
    st = os.stat(path)
    if st.st_mode & 0o077:
        raise SystemExit("REFUSE: permisos no restrictivos tras escritura: %o" % (st.st_mode & 0o777))
    return path

def main():
    ap = argparse.ArgumentParser(description="Provisionar confianza operativa para RXRE (solo administrador)")
    ap.add_argument("--store", default="/tmp/rxre_auth_provisioned/identities.json", help="Ruta fuera del repo")
    ap.add_argument("--issuer-key", default="/etc/rxre/issuer.key", help="Clave del emisor (fuera repo)")
    ap.add_argument("--service-key", default="/tmp/rxre_306_work/servicio.key", help="Clave de servicio M306")
    ap.add_argument("--issuer-id", default="rxre-admin-issuer")
    ap.add_argument("--executor-id", default="rxre-runner")
    ap.add_argument("--operation", default="op_m333_strace_ref_new")
    ap.add_argument("--scope", default="static_inspection")
    ap.add_argument("--provisioned-by", required=True)
    ap.add_argument("--confirm", action="store_true", help="Confirmación explícita OBLIGATORIA")
    args = ap.parse_args()

    if not args.confirm:
        raise SystemExit("REFUSE: falta --confirm. Este script NO se auto-ejecuta.")
    if args.store.startswith(REPO) or args.issuer_key.startswith(REPO):
        raise SystemExit("REFUSE: claves/almacén NO deben estar dentro del repositorio")
    if args.issuer_key == args.service_key:
        raise SystemExit("REFUSE: claves distintas obligatorias")

    os.makedirs(os.path.dirname(args.store), mode=0o700, exist_ok=True)
    os.makedirs(os.path.dirname(args.issuer_key), mode=0o700, exist_ok=True)
    os.makedirs(os.path.dirname(args.service_key), mode=0o700, exist_ok=True)

    # generar claves criptográficamente seguras
    issuer_key = os.urandom(32)
    service_key = os.urandom(32)
    _secure_write(args.issuer_key, issuer_key, 0o600)
    _secure_write(args.service_key, service_key, 0o600)

    store = {
        "auth_contract_version": av.AUTH_CONTRACT_VERSION,
        "provisioned_by": args.provisioned_by,
        "provisioned_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "fixture": False,
        "synthetic": False,
        "issuers": {
            args.issuer_id: {
                "key_path": args.issuer_key,
                "key_sha256": hashlib.sha256(issuer_key).hexdigest(),
                "operations": [args.operation],
                "scopes": [args.scope],
            }
        },
        "executors": {
            args.executor_id: {
                "uid": os.geteuid(),
                "operations": [args.operation],
                "scopes": [args.scope],
            }
        },
        "used_nonces": []
    }
    _secure_write(args.store, json.dumps(store, indent=2).encode(), 0o600)

    # validación inmediata
    req = {
        "contract_version": av.AUTH_CONTRACT_VERSION,
        "request_id": "req-m335-provision-check-001",
        "issuer": args.issuer_id,
        "executor": args.executor_id,
        "operation": args.operation,
        "scope": args.scope,
        "issued_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": "2099-01-01T00:00:00Z",
        "nonce": "nonce-m335-provision-check-" + os.urandom(4).hex(),
    }
    sig = av.sign_request(req, issuer_key)
    res = av.verify_operational_request(req, sig, store_path=args.store, fixture=False)
    print(json.dumps({
        "store": args.store,
        "issuer_key": args.issuer_key,
        "service_key": args.service_key,
        "issuer_key_sha256": hashlib.sha256(issuer_key).hexdigest(),
        "service_key_sha256": hashlib.sha256(service_key).hexdigest(),
        "uid_efectivo": os.geteuid(),
        "verify_result": {"status": res.get("status"), "operational": res.get("operational"), "reason": res.get("reason")}
    }, indent=2))
    return 0 if res.get("status") == "AUTHORIZED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
