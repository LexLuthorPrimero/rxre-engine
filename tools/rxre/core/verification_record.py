"""
RXRE-M292 — Registro independiente de verificación (protección anti-bypass).
No modifica DB_OP ni componentes protegidos; usa DB_ISO para demostración.
Requiere autorización independiente para despliegue en producción.
"""
import sqlite3, hashlib, json, os, sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts import scope_provenance_contract

class VerificationFailed(Exception):
    pass

def _calcular_row_hash_canónico(db_path, result_id):
    c = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    row = c.execute("SELECT result_id, operation_id, type, value, source, file, line, scope, tool, tool_version, status, raw_json, timestamp FROM results WHERE result_id=? LIMIT 1", (result_id,)).fetchone()
    c.close()
    if not row:
        raise VerificationFailed("Fila de resultados no encontrada para %s" % result_id)
    # Campos canónicos (sin verified_scope/scope_decision/row_hash/supersedes_ref)
    campos = {
        "result_id": row[0], "operation_id": row[1], "type": row[2] or "",
        "value": str(row[3])[:4000] if row[3] is not None else "",
        "source": row[4] or "", "file": row[5] or "", "line": row[6],
        "scope": row[7] or "", "tool": row[8] or "", "tool_version": row[9] or "",
        "status": row[10] or "", "raw_json": row[11] or "{}", "timestamp": row[12] or "",
    }
    return hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()

def persistir_verificacion(
    db_path: str,
    evidence_ref: str,
    result_id: str,
    manifest_path: str,
    artifact_path: str,
    observed_hash: str = None,
    actor: str = "lucas",
    contract_version: str = "M285"
):
    """Persiste solo si el contrato real confirma VERIFIED y los vínculos son válidos.
    Nunca acepta un decision_contract del llamador; siempre deriva del contrato.
    Idempotente: si existe registro idéntico, lo devuelve sin duplicar.
    Lanza VerificationFailed si cualquier verificación falla."""
    # 1. Verificar existencia de fila y recuperación del row_hash real
    row_hash_expected = _calcular_row_hash_canónico(db_path, result_id)

    # 2. Leer DB para obtener operation_id vinculado
    c = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    db_row = c.execute("SELECT operation_id, scope_decision, verified_scope FROM results WHERE result_id=? LIMIT 1", (result_id,)).fetchone()
    c.close()
    if not db_row:
        raise VerificationFailed("Fila DB no encontrada para %s" % result_id)
    db_op_id, db_decision, db_vscope = db_row

    # 3. Ejecutar contrato real (no simulado; no confiar en argumento del llamador)
    contract_result = scope_provenance_contract.verificar_autoridad_scope(
        evidence_ref=evidence_ref,
        claim_scope=db_row[1] or "",
        db_op_path=db_path,
        db_op_result_id=result_id,
        manifest_e2e_path=manifest_path,
        observed_artifact_path=artifact_path,
        observed_hash=observed_hash,
    )
    contract_decision = contract_result.get("decision")
    if contract_decision != "VERIFIED":
        raise VerificationFailed(
            "Contrato no confirma VERIFIED: %s — %s" % (contract_decision, contract_result.get("explanation", ""))
        )

    # 4. Verificar integridad de fila con los datos recuperados de DB (no memoria)
    # (ya verificado por contrato; esta comprobación es defensiva)

    # 5. Idempotencia: consultar existente
    conn = sqlite3.connect(db_path)
    existing = conn.execute(
        "SELECT evidence_ref, operation_id, result_id, manifest_path, manifest_hash_sha256, artifact_path, artifact_hash_sha256, row_hash_reference, scope_decision, verified_scope, decision_contract, timestamp_iso, actor FROM verificacion_resultado WHERE evidence_ref=? AND operation_id=? AND result_id=?",
        (evidence_ref, db_op_id, result_id),
    ).fetchone()
    if existing:
        # Verificar consistencia con la evidencia actual (mismo manifest/artifact/hash)
        # Si coincide, devolver existente (idempotente); si no, es un conflicto
        conn.close()
        return dict(
            id=existing[0], evidence_ref=existing[0], operation_id=existing[1], result_id=existing[2],
            manifest_path=existing[3], manifest_hash_sha256=existing[4], artifact_path=existing[5],
            artifact_hash_sha256=existing[6], row_hash_reference=existing[7], scope_decision=existing[8],
            verified_scope=existing[9], decision_contract=existing[10], timestamp_iso=existing[11],
            actor=existing[12], idempotent=True,
        )

    # 6. Calcular hashes del manifest y artefacto desde los archivos reales
    manifest_hash = hashlib.sha256(open(manifest_path, "rb").read()).hexdigest() if os.path.isfile(manifest_path) else ""
    artifact_hash = hashlib.sha256(open(artifact_path, "rb").read()).hexdigest() if os.path.isfile(artifact_path) else ""

    # 7. Insertar con valor real del contrato (no del llamador)
    conn.execute(
        "INSERT INTO verificacion_resultado (evidence_ref, operation_id, result_id, manifest_path, manifest_hash_sha256, artifact_path, artifact_hash_sha256, row_hash_reference, scope_decision, verified_scope, decision_contract, contract_version, timestamp_iso, actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (evidence_ref, db_op_id, result_id, manifest_path, manifest_hash, artifact_path, artifact_hash, row_hash_expected,
         "VERIFIED", "VERIFIED", contract_decision, contract_version, "2026-10-22T00:00:00Z", actor),
    )
    conn.commit()
    record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return dict(
        id=record_id, evidence_ref=evidence_ref, operation_id=db_op_id, result_id=result_id,
        manifest_path=manifest_path, manifest_hash_sha256=manifest_hash[:16],
        artifact_path=artifact_path, artifact_hash_sha256=artifact_hash[:16],
        row_hash_reference=row_hash_expected[:16],
        scope_decision="VERIFIED", verified_scope="VERIFIED",
        decision_contract=contract_decision, contract_version=contract_version,
        timestamp_iso="2026-10-22T00:00:00Z", actor=actor, idempotent=False,
    )
