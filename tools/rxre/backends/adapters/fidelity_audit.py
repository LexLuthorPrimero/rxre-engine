"""RXRE-LXXXII / M1222 — Lector independiente de evidencia de fidelidad persistida.

Audita filas `operations` de la copia operativa (`operativo.sqlite3`, M416)
EXCLUSIVAMENTE en modo de solo lectura (``mode=ro``). NO escribe, NO crea
tablas, NO migra, NO renombra, NO borra. NO depende de ``fidelity_scope``,
``fidelity_gate`` ni ``dispatch``; la lógica de validación se re-implementa
aquí de forma independiente (las dependencias compartidas son, a lo sumo:
los contratos de dominio v1/v2 como DATOS, el esquema de ``operations`` e
inventario de librería estándar).

Estatutos devueltos:
  PASS              — evidencia presente y coherente con el artefacto/ejecución.
  INVALID           — evidencia presente pero inconsistente o manipulada.
  UNKNOWN_EVIDENCE  — la operación persistida NO contiene bloque ``fidelity``
                      (fila anterior a LXXXI); nada se asume ni se reconstruye.
  NOT_DETERMINED    — integridad interna verificable pero no se puede vincular
                      el artefacto pedido (p.ej. ``artifact_path`` inaccesible).
  BLOCKED           — precondición externa ausente (base ilegible, esquema
                      inesperado). Falla cerrada, sin dictamen semántico.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
_RXRE = os.path.join(_REPO, "tools", "rxre")
V1_PATH = os.path.join(_RXRE, "decompiler", "fidelity_domain_v1.json")
V2_PATH = os.path.join(_RXRE, "decompiler", "fidelity_domain_v2.json")
DOMAINS = {"v1": V1_PATH, "v2": V2_PATH}
OPERATIV_DEFAULT = "/tmp/opencode/m416_operativo/operativo.sqlite3"
_PREC = {"FAITHFUL": 1, "PARTIAL": 2, "UNSUPPORTED": 3, "INVALID": 4}


def _sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _worst(verdicts: List[str]) -> str:
    best = "FAITHFUL"
    for v in verdicts:
        if _PREC.get(v, 4) > _PREC[best]:
            best = v
    return best


def _open_ro(db_path: str) -> sqlite3.Connection:
    if not os.path.isfile(db_path):
        raise FileNotFoundError(db_path)
    return sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)


def listar_decompile(db_path: str = OPERATIV_DEFAULT, limit: int = 50) -> List[Dict[str, Any]]:
    """Lista de solo inspección: filas binary.decompile (sin cargar response_json)."""
    try:
        c = _open_ro(db_path)
    except Exception as exc:  # noqa: BLE001
        return [{"status": "BLOCKED", "reason": "operativo inaccesible: %s" % exc}]
    try:
        rows = c.execute(
            "SELECT operation_id, capability, target, timestamp, status "
            "FROM operations WHERE capability='binary.decompile' "
            "ORDER BY timestamp DESC LIMIT ?", (int(limit),)).fetchall()
    except sqlite3.Error as exc:
        return [{"status": "BLOCKED", "reason": "esquema inesperado: %s" % exc}]
    finally:
        c.close()
    return [{"operation_id": r[0], "capability": r[1], "target": r[2],
             "timestamp": r[3], "status": r[4]} for r in rows]


def auditar(operation_id: str, *,
            db_path: str = OPERATIV_DEFAULT,
            artifact_path: Optional[str] = None) -> Dict[str, Any]:
    """Audita una operación persistida. SOLO LECTURA. Nunca muta decisiones."""
    out = {
        "operation_id": operation_id,
        "db_path": db_path,
        "audit_source": "operativo.sqlite3 (mode=ro)",
        "status": None,
        "checks": {},
        "problems": [],
        "artifact_sha256": None,
        "artifact_accept": None,
        "function_accept": None,
        "gate_accept": None,
        "verdict": None,
        "execution_id": None,
        "domain": None,
        "contract_version": None,
    }
    # --- precondición externa
    try:
        c = _open_ro(db_path)
    except Exception as exc:  # noqa: BLE001
        out["status"] = "BLOCKED"
        out["problems"].append("OPERATIVO_INACCESIBLE:%s" % exc)
        return out
    try:
        try:
            row = c.execute(
                "SELECT response_json FROM operations WHERE operation_id=?",
                (operation_id,)).fetchone()
        except sqlite3.Error as exc:
            out["status"] = "BLOCKED"
            out["problems"].append("SCHEMA_INESPERADO:%s" % exc)
            return out
    finally:
        c.close()
    if row is None:
        out["status"] = "INVALID"
        out["problems"].append("OPERATION_ID_NOT_FOUND")
        return out

    try:
        d = json.loads(row[0])
    except (ValueError, TypeError) as exc:
        out["status"] = "INVALID"
        out["problems"].append("RESPONSE_JSON_UNPARSEABLE:%s" % exc)
        return out
    if not isinstance(d, dict):
        out["status"] = "INVALID"
        out["problems"].append("RESPONSE_JSON_NOT_AN_OBJECT")
        return out

    fid = d.get("fidelity")
    if fid is None:
        out["status"] = "UNKNOWN_EVIDENCE"
        out["problems"].append("NO_FIDELITY_BLOCK (fila pre-LXXXI o sin selección)")
        return out
    if not isinstance(fid, dict):
        out["status"] = "INVALID"
        out["problems"].append("FIDELITY_NOT_AN_OBJECT")
        return out

    problems = out["problems"]
    checks = out["checks"]

    # --- envelope mínimo
    for k in ("execution_id", "timestamp_utc", "selection", "domain_hash",
              "verdict", "summary", "gate"):
        if k not in fid:
            problems.append("MISSING_FIDELITY_KEY:%s" % k)
    eid = fid.get("execution_id") or ""
    checks["execution_id_wellformed"] = (
        isinstance(eid, str) and len(eid) == 16
        and all(ch in "0123456789abcdef" for ch in eid))
    if not checks["execution_id_wellformed"]:
        problems.append("EXECUTION_ID_MALFORMED")
    out["execution_id"] = eid or None

    # --- dominio y binding del contrato
    sel = fid.get("selection") or {}
    name = sel.get("name")
    out["domain"] = name
    out["contract_version"] = fid.get("contract_version")
    checks["domain_name_known"] = name in DOMAINS
    if name in DOMAINS:
        checks["domain_hash_matches_file"] = fid.get("domain_hash") == _sha256_file(DOMAINS[name])
    else:
        checks["domain_hash_matches_file"] = False
    if not checks["domain_hash_matches_file"]:
        problems.append("DOMAIN_HASH_MISMATCH")

    # --- vinculación artefacto (envelope: precheck <-> scope)
    pref = (d.get("precheck") or {}).get("input_hash")
    out["artifact_sha256"] = pref
    scope = fid.get("scope") or {}
    art_in_scope = (scope.get("selection") or {}).get("artifact_hash")
    checks["artifact_binding_envelope"] = bool(pref) and pref == art_in_scope
    if not checks["artifact_binding_envelope"]:
        problems.append("ARTIFACT_BINDING_MISMATCH(precheck vs scope)")
    # Propagar el veredicto (LXXXII): lo que el envelope declara.
    out["verdict"] = fid.get("verdict")
    if artifact_path is not None:
        if not os.path.isfile(artifact_path):
            out["status"] = "NOT_DETERMINED"
            out["checks"]["artifact_file_sha256"] = "unverifiable (artifact inaccesible)"
            out["problems"].append("ARTIFACT_PATH_INACCESSIBLE:%s" % artifact_path)
            return out
        checks["artifact_file_sha256"] = _sha256_file(artifact_path) == pref
        if checks["artifact_file_sha256"] is not True:
            problems.append("ARTIFACT_FILE_SHA256_MISMATCH")
    else:
        checks["artifact_file_sha256"] = "not_requested"

    # --- inventario de bloques (lo que el envelope conserva)
    funcs = scope.get("functions") or []
    summ = fid.get("summary") or {}
    labels = [f.get("label") for f in funcs]
    starts_ends = [(f.get("start_addr"), f.get("end_addr")) for f in funcs]
    checks["no_duplicate_functions"] = len(labels) == len(set(labels))
    if not checks["no_duplicate_functions"]:
        problems.append("DUPLICATE_FUNCTION_INVENTORY")
    bad_ranges = [f for f in funcs
                  if not (isinstance(f.get("start_addr"), str) and isinstance(f.get("end_addr"), str)
                          and f["start_addr"] < f["end_addr"])]
    checks["ranges_wellformed"] = not bad_ranges
    if bad_ranges:
        problems.append("MALFORMED_RANGE_INVENTORY")

    # duplicados de rango exacto en inventario persistido
    seen = {}
    for f in funcs:
        key = (f.get("start_addr"), f.get("end_addr"))
        if key in seen:
            problems.append("DUPLICATE_BLOCK_RANGE:%s" % (key,))
        seen[key] = True

    # --- summary vs inventario
    if isinstance(summ, dict):
        nb = summ.get("n_blocks")
        checks["summary_n_blocks_matches_inventory"] = nb == len(funcs)
        if nb != len(funcs):
            problems.append("SCOPE_FUNCTIONS_DEFLATED(n_blocks=%s;inventory=%d)" % (nb, len(funcs)))
        for k in ("FAITHFUL", "PARTIAL", "UNSUPPORTED", "INVALID"):
            obs = sum(1 for f in funcs if f.get("verdict") == k)
            checks["summary_%s_count" % k.lower()] = summ.get(k) == obs
            if summ.get(k) != obs:
                problems.append("SUMMARY_COUNT_MISMATCH:%s(summary=%s;observed=%d)" % (k, summ.get(k), obs))

    # --- worst-wins recalculado desde EL INVENTARIO persistido
    verdicts = [f.get("verdict") for f in funcs]
    recomputed = _worst(verdicts) if verdicts else None
    checks["global_verdict_worst_wins"] = all(v in _PREC for v in verdicts) and recomputed == fid.get("verdict")
    if recomputed != fid.get("verdict"):
        problems.append("GLOBAL_VERDICT_INCOMPATIBLE_WITH_INVENTORY(persisted=%s;recomputed=%s)" % (
            fid.get("verdict"), recomputed))
    if scope.get("verdict") not in (None, fid.get("verdict")):
        problems.append("SCOPE_VERDICT_DIVERGES_FROM_GATE_VERDICT")

    # --- decisiones independiente: gate.accept y artifact_accept
    gate = fid.get("gate") or {}
    accept = gate.get("accept")
    out["gate_accept"] = accept
    checks["gate_fail_closed"] = (accept is True) == (fid.get("verdict") == "FAITHFUL")
    if accept is True and fid.get("verdict") != "FAITHFUL":
        problems.append("GATE_ACCEPT_TRUE_WITH_NONFAITHFUL_VERDICT")
    art_accept = scope.get("artifact_accept")
    out["artifact_accept"] = art_accept
    if scope:
        if art_accept is not True and art_accept is not False:
            problems.append("ARTIFACT_ACCEPT_NOT_BOOLEAN")
        if (art_accept is True) != (accept is True):
            problems.append("ARTIFACT_ACCEPT_DIVERGES_FROM_GATE")

    # --- function_accept coherente con el inventario
    fa = scope.get("function_accept") or {}
    out["function_accept"] = fa
    label_set = set(labels)
    if fa and set(fa) != label_set:
        problems.append("FUNCTION_ACCEPT_KEYS_DIVERGE_FROM_INVENTORY")
    for lbl, ok in fa.items():
        match = next((f for f in funcs if f.get("label") == lbl), None)
        if match is not None and (match.get("verdict") == "FAITHFUL") != bool(ok):
            problems.append("FUNCTION_ACCEPT_INCONSISTENT:%s" % lbl)

    # --- resultado
    if problems:
        out["status"] = "INVALID"
    elif all(v is True or v == "not_requested" for v in checks.values()):
        out["status"] = "PASS"
    else:
        out["status"] = "INVALID"
        out["problems"].append("CHECK_FALSE_WITHOUT_PROBLEM (internal audit defect)")
    return out


def auditar_para_agua(operation_id: str, **kw) -> Dict[str, Any]:
    """Frontera explícita para AGUA: un dict plano, sin dependencias ocultas.

    AGUA recibe: estado ( PASS|INVALID|UNKNOWN_EVIDENCE|NOT_DETERMINED|BLOCKED ),
    veredicto, decisiones, evidencia de vinculación. NUNCA recibe autoridad:
    este dict no se persiste ni modifica claims, TIERRA ni registros.
    """
    a = auditar(operation_id, **kw)
    agua = {
        "PASS": "ok",
        "INVALID": "violation",
        "UNKNOWN_EVIDENCE": "not_proven",
        "NOT_DETERMINED": "not_proven",
        "BLOCKED": "violation",
    }.get(a["status"], "not_proven")
    return {
        "operation_id": a["operation_id"],
        "agua": agua,
        "status": a["status"],
        "verdict": a["verdict"],
        "gate_accept": a["gate_accept"],
        "artifact_accept": a["artifact_accept"],
        "function_accept": a["function_accept"],
        "execution_id": a["execution_id"],
        "domain": a["domain"],
        "problems": a["problems"],
        "nota": ("auditoria SOLO LECTURA del registro persistido; no autoriza "
                 "consumo, ejecucion ni promocion. DB_AUTH_ACTOR_M294 BLOCKED."),
    }
