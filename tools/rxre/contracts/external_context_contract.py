#!/usr/bin/env python3
"""RXRE-MISSION-248 — CONTRATO DE CONTEXTO EXTERNO (aislado, no productivo).
No modifica core/store.py ni evidence_integrity.py; no activa op:claim.

Uso: proporciona context externo verificable (operation_id + manifest + artifact + scope)
para evaluar autenticidad y compatibilidad de scope sin depender exclusivamente de DB_ISO.
"""
import sqlite3, os, sys, json
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.core.evidence_integrity import validate_evidence_path

DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"


def verificar_contexto_externo(
    operation_id: str = None,
    manifest_path: str = None,
    artifact_path: str = None,
    scope_claim: str = None,
    db_op_path: str = DB_OP,
    resolver_refs=None,
) -> dict:
    """
    Verifica contexto externo sin inventar semantica.
    Devuelve:
      - COMPATIBLE: referencia en DB_OP coincide con manifest y artifact, y scope es consistente con contexto de operacion.
      - INCOMPATIBLE: evidencia contradictoria (hash manifest != artifact, operation_id no coincide con manifest, o scope incompatible con contexto).
      - INDETERMINATE: falta operacion, manifest, artifact, o hash; o scope no puede evaluarse sin claim previo ni contexto de operacion.
    No escribe; no invoca op:claim.
    """
    # --- 1) Operacion / referencia ---
    if not operation_id:
        return {"estado":"INDETERMINATE","motivo":"falta operation_id; no se puede vincular procedimiento con manifest/artifact","frontera":"contexto"}
    try:
        op = sqlite3.connect(db_op_path)
        row = op.execute("SELECT result_id, operation_id, type, file, scope, raw_json FROM results WHERE operation_id=? LIMIT 1", (operation_id,)).fetchone()
        op.close()
    except Exception as exc:
        return {"estado":"INDETERMINATE","motivo":"error al consultar DB_OP: %s"%str(exc),"frontera":"contexto"}
    if not row:
        return {"estado":"INDETERMINATE","motivo":"operation_id '%s' no encontrado en DB_OP; no hay contexto de ejecución verificable"%operation_id,"frontera":"referencia"}
    result_id, op_op, op_type, op_file, op_scope, raw_json = row

    # --- 2) Manifest ---
    if manifest_path is None or not os.path.exists(manifest_path):
        return {"estado":"INDETERMINATE","motivo":"falta manifest E2E o no existe: %s"%(manifest_path or "None"),"frontera":"integridad"}
    int_res = validate_evidence_path(manifest_path, art_path=artifact_path)
    if not int_res.get("ok"):
        return {"estado":"INCOMPATIBLE","motivo":"manifest E2E fallido: %s; no se vincula con artefacto"%str(int_res.get("errors")),"frontera":"integridad","detalle_integridad":int_res}

    # --- 3) Vinculo manifest -> artefacto (hash) ---
    manifest = json.load(open(manifest_path))
    manifest_art_path = manifest.get("artefacto_path") or manifest.get("arte_facto_path") or manifest.get("artifact_path")
    manifest_hash = manifest.get("artefacto_hash_sha256") or manifest.get("hash_sha256","")
    if artifact_path:
        # Verificar que el artefacto declarado coincide con manifest
        if manifest_art_path and manifest_art_path != artifact_path:
            return {"estado":"INCOMPATIBLE","motivo":"manifest declara artefacto %s pero se inspecciona %s"%(manifest_art_path, artifact_path),"frontera":"autenticidad"}
        # Verificar hash real
        import hashlib
        with open(artifact_path,"rb") as f:
            real_hash = hashlib.sha256(f.read()).hexdigest()
        if manifest_hash and not (manifest_hash == real_hash or (len(manifest_hash)>=8 and real_hash.startswith(manifest_hash))):
            return {"estado":"INCOMPATIBLE","motivo":"hash del artefacto observado (%s...) no coincide con manifest (%s...)"%(real_hash[:16], manifest_hash[:16]),"frontera":"autenticidad"}

    # --- 4) Vinculo referencia (DB_OP) -> manifest ---
    # El manifest debe estar asociado con la misma operación (procedencia) o con el mismo hash de resultado.
    db_op_hash = None
    try:
        meta = json.loads(raw_json or "{}")
        db_op_hash = meta.get("hash") or meta.get("artefacto_hash_sha256")
    except Exception:
        pass
    manifest_hash_full = manifest_hash or ""
    if db_op_hash and manifest_hash_full:
        # Reutiliza el contrato existente de coincidencia de hash (tolera truncamiento)
        from rxre.contracts.evidence_claim_verification import _coincide_hash
        if not _coincide_hash(manifest_hash_full, db_op_hash) and not _coincide_hash(db_op_hash, manifest_hash_full):
            return {"estado":"INCOMPATIBLE","motivo":"hash DB_OP (%s...) no coincide con manifest (%s...)"%(db_op_hash[:16], manifest_hash_full[:16]),"frontera":"autenticidad","detalle":"referencia operativa y manifest divergen en artefacto"}
    # Si DB_OP no tiene hash (raro para res_real_001, que sí lo tiene) pero manifest sí -> indeterminado (falta verificación cruzada completa, pero no contradicción)
    # Si DB_OP sí y manifest sí y coinciden -> compatible (falta solo scope)

    # --- 5) Scope (contexto de ejecución) ---
    # El scope del claim debe ser consistente con el contexto de ejecución si existe.
    # Como DB_OP results no declaran scope para res_real_001 (scope=None), no podemos comparar.
    # Si scope_claim y scope de operacion (si estuviera) coinciden -> compatible por contexto.
    # Si difieren -> incompatible (contradicción demostrada).
    # Si faltan datos -> indeterminado.
    op_scope = op_scope  # de DB_OP (puede ser None)
    if scope_claim is not None and scope_claim.strip() != "":
        if op_scope is not None and op_scope.strip() != "" and op_scope != scope_claim:
            return {"estado":"INCOMPATIBLE","motivo":"scope claim (%s) contradice scope de operacion DB_OP (%s)"%(scope_claim, op_scope),"frontera":"scope","detalle":"contexto de ejecucion diverge"}
        # Si op_scope es None o coincide -> no se demuestra incompatibilidad; es compatible si resto pasa
    # Si scope_claim es None o vacío -> falta campo obligatorio; no se declara incompatible por ausencia, pero tampoco se confirma compatible por contexto
    # La regla: COMPATIBLE solo cuando hay respaldo de referencia + integridad + autenticidad + (scope coincidente o no contradicho)

    # --- Resultado ---
    # Si llegamos aquí: referencia resuelve, manifest validado, hash coincide (o al menos no contradice), integridad ok.
    # El alcance es indeterminado si op_scope es None o falta claim previo; compatible si coinciden.
    if op_scope is None or (scope_claim is not None and op_scope == scope_claim):
        # Si scope_claim es vacío -> no se afirma compatible por contexto, pero tampoco incompatible; mantenemos indeterminado para evitar invento
        if scope_claim and op_scope == scope_claim:
            return {"estado":"COMPATIBLE","motivo":"contexto externo verificado: operacion, manifest, artifact, autenticidad y scope coinciden","frontera":"contexto","operation_id":operation_id,"result_id":result_id}
        else:
            return {"estado":"INDETERMINATE","motivo":"autenticidad e integridad verificadas; scope: op_scope=%s vs claim=%s (no contradicho pero contexto no completo para COMPATIBLE sin claim previo)"%(op_scope, scope_claim),"frontera":"scope","operation_id":operation_id,"result_id":result_id}
    else:
        # Ya cubierto arriba como INCOMPATIBLE
        return {"estado":"INDETERMINATE","motivo":"contexto parcial; verificacion de referencia/integridad/autenticidad confirmada; scope pendiente de contexto independiente","frontera":"scope","operation_id":operation_id,"result_id":result_id}


# Pruebas aisladas del contrato
if __name__ == "__main__":
    import tempfile, json, hashlib
    # Fixture: manifest E2E real, referencia res_real_001, artifact real, operation_id real
    res = verificar_contexto_externo(
        operation_id="op_real_001",
        manifest_path="/tmp/e2e_233_strace.json",
        artifact_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
        scope_claim="scope_246",
        db_op_path="/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3",
    )
    print("A (op_real_001 + manifest + artifact + scope_246):", res["estado"], res["frontera"], res.get("motivo","")[:70])
    # B: operación inexistente
    res_b = verificar_contexto_externo(
        operation_id="op_inexistente_246",
        manifest_path="/tmp/e2e_233_strace.json",
        artifact_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
        scope_claim="scope_246",
    )
    print("B (op inexistente):", res_b["estado"], res_b["frontera"], res_b.get("motivo","")[:70])
    # C: manifest alterado (hash incorrecto)
    bad = tempfile.mktemp(suffix=".json")
    with open("/tmp/e2e_233_strace.json") as f: d=json.load(f)
    d["artefacto_hash_sha256"]="0"*64
    with open(bad,"w") as f: json.dump(d,f)
    res_c = verificar_contexto_externo(
        operation_id="op_real_001",
        manifest_path=bad,
        artifact_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
        scope_claim="scope_246",
    )
    print("C (manifest alterado):", res_c["estado"], res_c["frontera"], res_c.get("motivo","")[:70])
    # D: scope distinto que podría ser compatible según contexto pero sin claim previo (indeterminado)
    res_d = verificar_contexto_externo(
        operation_id="op_real_001",
        manifest_path="/tmp/e2e_233_strace.json",
        artifact_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
        scope_claim="scope_distinct",
    )
    print("D (scope distinto, contexto real):", res_d["estado"], res_d["frontera"], res_d.get("motivo","")[:70])
    # E: sin manifest
    res_e = verificar_contexto_externo(
        operation_id="op_real_001",
        manifest_path=None,
        artifact_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
        scope_claim="scope_246",
    )
    print("E (sin manifest):", res_e["estado"], res_e["frontera"], res_e.get("motivo","")[:70])
