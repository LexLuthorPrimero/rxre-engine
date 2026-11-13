#!/usr/bin/env python3
"""RXRE-MISSION-308 — GATE DE AUTORIZACIÓN EJECUTABLE (aislado).

Propietario: auditoría (nuevo). NO modifica componentes protegidos, bases ni permisos.

El gate evalúa un PAQUETE TÉCNICO (M307) y una CONCESIÓN EXPLÍCITA (grant) y
devuelve un estado entre:
    BLOCKED                        -> faltan condiciones necesarias
    READY_FOR_EXPLICIT_AUTHORIZATION -> paquete completo, sin permiso de ejecución
    AUTHORIZED                     -> concesión explícita, verificada y acotada al alcance
    REJECTED                       -> concesión inválida/incompleta/contradictoria/fuera de alcance

Reglas duras:
  * LaUNCHER de este archivo NO es una concesión; un grant escrito por el propio
    proceso/agente NO cuenta como autoridad (el verificador debe estar configurado
    fuera de banda y sus claves en archivo legible solo por el servicio).
  * El gate NUNCA declara despliegue: `deployment_state` es siempre "NOT_DEPLOYED".
  * A1..A4 son una unidad coordinada: un grant parcial -> REJECTED (ventana insegura).
  * Fallo cerrado: datos ausentes/ambiguos/falsificados/inconsistentes -> REJECTED
    (o BLOCKED si no hay concesión que evaluar).
"""
import datetime
import hashlib
import json
import os
import re

REPO = "/home/lucas/Escritorio/rxre"
PACKAGE_PATH = os.path.join(REPO, "audit/debugfs/RXRE-MISSION-307-AUTHORIZATION-INTEGRATION-PACKAGE.md")
PACKAGE_ID = "M307"
CONTRACT_PATH = os.path.join(REPO, "audit/debugfs/RXRE-MISSION-306-UNIFIED-VERIFIED-AUTHORITY.md")

# ------------------------------------------------------------------ paquetes
# Alcance aprobado por el paquete M307 (secciones 5 y 6). Fuente: M307.
AUTHORIZATIONS = {
    "DBOP_SCHEMA_M290": {
        "label": "A1",
        "depends_on": [],
        "scope": [
            "DDL en DB_OP: tabla verificacion_resultado + indices + TRIGGER avanzado",
            "TRIGGER avanzado exige decision_contract=VERIFIED y verified_scope=VERIFIED",
            "TRIGGER avanzado exige row_hash_reference == results.row_hash",
            "TRIGGER avanzado exige evidencia en findings/execution_events y audit_log",
            "Solo DB_OP y copia de regresion; DB_ISO intacto",
        ],
        "forbidden": [
            "DELETE/UPDATE de filas historicas",
            "modificar filas existentes de results",
            "cualquier escritura sobre DB_ISO",
        ],
        "acceptance": ["T-schema-1", "T-schema-2", "T-schema-3", "T-schema-4"],
        "rollback": "restaurar backup verificado (sqlite3 .backup/.restore); DDL reversible por backup",
    },
    "DBOP_WRITER_M290": {
        "label": "A2",
        "depends_on": ["DBOP_SCHEMA_M290", "DB_AUTH_ACTOR_M294", "DBOP_ACCESS_M295"],
        "scope": [
            "store.py delega en unified_verified_contract (evaluar_transicion/persistir_con_autoridad)",
            "store.py no acepta scope_decision/verified_scope del caller",
            "machine.py no escribe verificacion_resultado",
            "rechazos registrados en audit_log",
        ],
        "forbidden": [
            "cambiar semantica de M285/M301/M303",
            "reescribir filas historicas",
            "eliminar machine.py",
        ],
        "acceptance": ["T-writer-1", "T-writer-2", "T-writer-3", "T-writer-4"],
        "rollback": "revertir diff de store.py/machine.py; sin cambio de estado de base",
    },
    "DB_AUTH_ACTOR_M294": {
        "label": "A3",
        "depends_on": ["DBOP_ACCESS_M295"],
        "scope": [
            "verificacion de uid efectivo del emisor (os.getuid/getpwuid)",
            "identidad de servicio autenticada, separada del actor declarado por el caller",
            "atestación HMAC con clave del servicio, clave en archivo 0600",
            "audit_log con uid, timestamp, operation_id, evidence_ref",
        ],
        "forbidden": [
            "aceptar actor/uid declarado por el caller como autoridad",
            "usar HMAC como prueba de veracidad semantica",
            "afirmar no-repudio legal (HMAC es simetrica)",
        ],
        "acceptance": ["T-auth-1", "T-auth-2", "T-auth-3", "T-auth-4"],
        "rollback": "desactivar verificacion de identidad (revertir diff); sin cambio de esquema",
    },
    "DBOP_ACCESS_M295": {
        "label": "A4",
        "depends_on": [],
        "scope": [
            "permisos de DB_OP: chmod 640, chown servicio:rwgroup",
            "clave de atestación: archivo 0600 propiedad del servicio",
            "modulos: no escribibles por el cliente",
            "sqlite3_authorizer: denegar INSERT/UPDATE/DELETE fuera del modulo autorizado",
            "uid de servicio dedicado",
        ],
        "forbidden": [
            "cambiar permisos globales del sistema",
            "abrir DB_OP a todos los usuarios",
            "degradar permisos a la espera de integracion",
        ],
        "acceptance": ["T-access-1", "T-access-2", "T-access-3", "T-access-4"],
        "rollback": "restaurar chmod/chown previos (estado previo registrado antes de cambiar)",
    },
}
REQUIRED_ALL = sorted(AUTHORIZATIONS.keys())

# Activos que el gate inspecciona (solo lectura) para el informe auditable.
INSPECTED = {
    "DB_OP": os.path.join(REPO, ".rxre/storage/rxre.sqlite3"),
    "DB_ISO": "/tmp/rxre_289_iso.sqlite3",
    "core/store.py": os.path.join(REPO, "tools/rxre/core/store.py"),
    "api/machine.py": os.path.join(REPO, "tools/rxre/api/machine.py"),
    "core/evidence_integrity.py": os.path.join(REPO, "tools/rxre/core/evidence_integrity.py"),
    "core/verification_record.py": os.path.join(REPO, "tools/rxre/core/verification_record.py"),
    "contracts/scope_provenance_contract.py": os.path.join(REPO, "tools/rxre/contracts/scope_provenance_contract.py"),
    "core/unified_verified_contract.py": os.path.join(REPO, "tools/rxre/core/unified_verified_contract.py"),
    "package/M307": PACKAGE_PATH,
    "contract/M306": CONTRACT_PATH,
}

# ------------------------------------------------------------------ utilidades
def sha256_file(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value):
    if not value or not isinstance(value, str):
        return None
    txt = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------ verificador
def default_verifier(grant, ctx):
    """Verificador por defecto: NO existe autoridad de concesion en este entorno.

    Devuelve (ok, motivo). Nunca devuelve ok=True: el gate debe fallar cerrado
    cuando no hay un verificador autenticado configurado fuera de banda.
    """
    return False, ("INSUFFICIENT: no hay mecanismo autenticado de concesion configurado "
                   "(sin clave publica/de servicio, sin transporte autenticado, sin "
                   "autoridad de concessión identificada en este entorno)")


# ------------------------------------------------------------------ gate
def evaluate(grant=None, package_path=PACKAGE_PATH, now=None, verifier=None,
             inspected=None):
    """Evalua el paquete y (opcionalmente) una concesion explicita.
    Funcion pura: sin escrituras, sin estado persistente, idempotente."""
    now_dt = _parse_iso(now) if now else datetime.datetime.now(datetime.timezone.utc)
    res = {
        "gate": "M308",
        "package_id": PACKAGE_ID,
        "evaluated_at": now_dt.replace(microsecond=0).isoformat(),
        "state": "BLOCKED",
        "authorized": False,
        "execution_permit_for_integration": False,
        "deployment_permit": False,
        "deployment_state": "NOT_DEPLOYED",
        "notice": ("Este resultado NO es un despliegue, NO autoriza produccion por si mismo "
                   "y NO cierra el bypass de store.py."),
        "reasons": [],
        "pending_conditions": [],
        "evidence": {},
        "grant": None,
    }

    # --- 1. paquete tecnico ---
    pkg_hash = sha256_file(package_path)
    res["evidence"]["package_sha256"] = pkg_hash
    if pkg_hash is None:
        res["state"] = "BLOCKED"
        res["reasons"].append("BLOCKED: paquete M307 no encontrado (%s)" % package_path)
        res["pending_conditions"].append("Paquete tecnico M307 disponible y verificado")
        return res
    res["evidence"]["observed_assets"] = {
        k: sha256_file(v) for k, v in (inspected or INSPECTED).items()
    }
    con_hash = sha256_file(CONTRACT_PATH)
    res["evidence"]["contract_M306_sha256"] = con_hash

    required_pre = [
        "Paquete M307 disponible y verificado (hash=%s)" % pkg_hash[:16],
        "Contrato M306 disponible (hash=%s)" % (con_hash[:16] if con_hash else "N/A"),
        "A1..A4 con alcance, rollback, pruebas de aceptacion y dependencias definidos",
        "Verificador de concesion autenticado configurado fuera de banda",
    ]

    # --- 2. sin concesion: READY si el paquete esta completo ---
    if grant is None:
        res["state"] = "READY_FOR_EXPLICIT_AUTHORIZATION"
        res["reasons"].append("No hay concesion explicita: el paquete tecnico es propuesta, no permiso")
        res["pending_conditions"].extend(required_pre)
        res["pending_conditions"].append("Concesion explicita, verificada y acotada para A1..A4 (unidad coordinada)")
        return res

    res["grant"] = {"present": True, "grant_id": grant.get("grant_id") if isinstance(grant, dict) else None}

    # --- 3. concesion malformada -> REJECTED (fallo cerrado) ---
    if not isinstance(grant, dict):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: concesion ausente o de tipo invalido")
        return res
    required_fields = ["grant_id", "package_id", "package_sha256", "authorizations",
                        "grantor", "issued_at", "state"]
    missing = [f for f in required_fields if f not in grant or grant.get(f) in (None, "")]
    if missing:
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: concesion incompleta; campos ausentes: %s" % ", ".join(missing))
        res["pending_conditions"].extend(required_pre)
        return res

    # 3.1 paquete referenciado
    if grant.get("package_id") != PACKAGE_ID:
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: la concesion apunta a otro paquete (%s != %s)" % (grant.get("package_id"), PACKAGE_ID))
        return res
    if str(grant.get("package_sha256", "")).lower() != str(pkg_hash).lower():
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: hash del paquete modificado tras la aprobacion "
                              "(concesion=%s..., actual=%s...)" % (str(grant.get("package_sha256"))[:16], str(pkg_hash)[:16]))
        res["pending_conditions"].append("Re-emitir la concesion contra el hash vigente del paquete M307")
        return res

    # 3.2 estado de la concesion (caducada / revocada)
    gstate = str(grant.get("state", "")).upper()
    if gstate in ("REVOKED", "CANCELLED", "REVOCADA"):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: concesion revocada (%s)" % gstate)
        return res
    if gstate not in ("ACTIVE", "VIGENTE", "GRANTED"):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: estado de concesion desconocido (%s)" % gstate)
        return res
    exp = _parse_iso(grant.get("expires_at"))
    if exp is not None and exp < now_dt:
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: concesion caducada (expires_at=%s)" % exp.isoformat())
        return res
    issued = _parse_iso(grant.get("issued_at"))
    if issued is None:
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: issued_at ausente o no parseable")
        return res
    if issued > now_dt:
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: issued_at en el futuro (%s)" % issued.isoformat())
        return res

    # 3.3 identificador de concesion
    if not re.match(r"^[A-Za-z0-9_.:-]{4,128}$", str(grant.get("grant_id", ""))):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: grant_id invalido")
        return res

    # 3.4 autorizante
    grantor = grant.get("grantor")
    if not isinstance(grantor, dict) or not grantor.get("id") or not grantor.get("role"):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: grantor sin id/role verificable")
        res["pending_conditions"].append("Identidad del autorizante (id, rol) y mecanismo de verificacion")
        return res

    # 3.5 autorizaciones concedidas: unidad coordinada
    granted = grant.get("authorizations")
    if not isinstance(granted, dict):
        res["state"] = "REJECTED"
        res["reasons"].append("REJECTED: bloque authorizations invalido")
        return res
    granted_ids = sorted(granted.keys())
    if granted_ids != REQUIRED_ALL:
        faltan = [a for a in REQUIRED_ALL if a not in granted_ids]
        extra = [a for a in granted_ids if a not in AUTHORIZATIONS]
        res["state"] = "REJECTED"
        res["reasons"].append(
            "REJECTED: concesion parcial/ambigua; A1..A4 deben concederse como unidad coordinada "
            "(faltan=%s, sobran=%s)" % (faltan or "-", extra or "-"))
        res["pending_conditions"].append("Concesion completa de A1..A4 (ventana insegura si es parcial)")
        return res

    # 3.6 dependencias satisfied
    for aid, spec in AUTHORIZATIONS.items():
        for dep in spec["depends_on"]:
            if dep not in granted:
                res["state"] = "REJECTED"
                res["reasons"].append("REJECTED: dependencia no satisfecha (%s -> %s)" % (aid, dep))
                return res

    # 3.7 alcance: subconjunto exacto del alcance aprobado
    for aid, spec in AUTHORIZATIONS.items():
        entry = granted.get(aid)
        if not isinstance(entry, dict):
            res["state"] = "REJECTED"
            res["reasons"].append("REJECTED: autorizacion %s sin detalle de alcance" % aid)
            return res
        granted_scope = entry.get("scope")
        if not isinstance(granted_scope, list) or not granted_scope:
            res["state"] = "REJECTED"
            res["reasons"].append("REJECTED: %s sin lista de alcance" % aid)
            return res
        allowed = set(spec["scope"])
        for item in granted_scope:
            if item not in allowed:
                res["state"] = "REJECTED"
                res["reasons"].append("REJECTED: alcance ampliado en %s: '%s' no pertenece al alcance aprobado" % (aid, item))
                res["pending_conditions"].append("Alcance de la concesion identico al alcance aprobado del paquete M307")
                return res
        forbidden = set(entry.get("forbidden_extra") or [])
        if forbidden:
            res["state"] = "REJECTED"
            res["reasons"].append("REJECTED: %s declara permisos extra no previstos" % aid)
            return res
        ac = entry.get("acceptance")
        if ac is not None and sorted(ac) != sorted(spec["acceptance"]):
            res["state"] = "REJECTED"
            res["reasons"].append("REJECTED: criterios de aceptacion divergentes en %s" % aid)
            return res

    # --- 4. autenticacion de la concesion ---
    vfn = verifier or default_verifier
    try:
        ok, motivo = vfn(grant, res)
    except Exception as exc:  # fallo cerrado
        ok, motivo = False, "REJECTED: verificador lanzo excepcion (%s)" % str(exc)[:120]
    if not ok:
        res["state"] = "BLOCKED"
        res["reasons"].append(motivo)
        res["pending_conditions"].extend(required_pre)
        res["pending_conditions"].append("Verificacion criptografica de la concesion por autoridad externa")
        return res

    # --- 5. concession verificada y acotada ---
    res["state"] = "AUTHORIZED"
    res["authorized"] = True
    res["execution_permit_for_integration"] = True   # M307 §6 (pasos 2-6), NO despliegue
    res["deployment_permit"] = False
    res["deployment_state"] = "NOT_DEPLOYED"
    res["reasons"].append("Concesion explicita verificada, completa (A1..A4) y acotada al paquete M307 (%s)" % pkg_hash[:16])
    res["pending_conditions"].extend([
        "Ejecutar la secuencia M307 §6 sobre copia de regresion de DB_OP",
        "Validar T-schema-*/T-writer-*/T-auth-*/T-access-* y registrar evidencia",
        "Concesion de despliegue separada (no incluida en este gate): el gate no autoriza despliegue",
    ])
    return res


# ------------------------------------------------------------------ informe
def render_report(res):
    L = []
    L.append("# RXRE-MISSION-308 — INFORME DEL GATE DE AUTORIZACIÓN")
    L.append("")
    L.append("> **AVISO**: este informe es una evaluación técnica de un gate. "
             "No es una concesión, no autoriza producción y no representa despliegue.")
    L.append("")
    L.append("- gate: `%s`" % res.get("gate"))
    L.append("- paquete: `%s` (`sha256=%s`)" % (res.get("package_id"), (res.get("evidence", {}).get("package_sha256") or "N/A")[:16]))
    L.append("- evaluado: `%s`" % res.get("evaluated_at"))
    L.append("- **estado: `%s`**" % res.get("state"))
    L.append("- `authorized`: `%s` | `execution_permit_for_integration`: `%s` | `deployment_permit`: `%s` | `deployment_state`: `%s`" % (
        res.get("authorized"), res.get("execution_permit_for_integration"),
        res.get("deployment_permit"), res.get("deployment_state")))
    L.append("")
    L.append("## Motivos")
    for r in res.get("reasons", []):
        L.append("- %s" % r)
    L.append("")
    L.append("## Condiciones pendientes")
    if res.get("pending_conditions"):
        for c in res["pending_conditions"]:
            L.append("- [ ] %s" % c)
    else:
        L.append("- (ninguna registrada por el gate)")
    L.append("")
    L.append("## Evidencia (hashes, solo lectura)")
    for k, v in sorted((res.get("evidence", {}).get("observed_assets") or {}).items()):
        L.append("- `%s`: `%s`" % (k, v))
    L.append("")
    L.append("## Nota de confianza")
    L.append("- La presente evaluación no constituye concesión ni permiso de producción.")
    return "\n".join(L) + "\n"


def write_report(res, path):
    with open(path, "w") as f:
        f.write(render_report(res))
    return path
