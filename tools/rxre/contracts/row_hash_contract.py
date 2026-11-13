#!/usr/bin/env python3
"""Contrato de integridad de fila (row_hash) — M275 ENSAYO REVERSIBLE.
No autoriza; solo define la representación canónica y verificación.
No modifica DB_OP; se usa con copias aisladas.
Un hash válido NO prueba autorización, ni verdad semántica.
"""
import sqlite3, json, hashlib

FORMAT_VERSION = "rxre/rowhash/v1"

# Campos cubiertos por row_hash (excluido el propio row_hash para evitar autorreferencia)
CAMPOS_RESULTADOS = [
    "result_id","operation_id","type","value","source","file","line",
    "scope","tool","tool_version","status","raw_json","timestamp"
]
CAMPOS_OPERACIONES = [
    "operation_id","request_id","contract_ver","operacion","capability","question","target",
    "scope","status","n_results","request_json","response_json","target_pci","timestamp","duracion_s"
]
# A futuro, tras migración reversible (no aplicada aún en DB_OP):
CAMPOS_OPERACIONES_POST_MIG = CAMPOS_OPERACIONES + [
    "declared_scope","authorized_scope","auth_decision","auth_actor","auth_timestamp"
]

def canonicalizar_dict(d):
    """Representación canónica v1 — DEBE coincidir byte a byte con `core/store.py::registrar`.
    store.py usa: json.dumps(campos_result, sort_keys=True, default=str)
    -> separadores por defecto (', ', ': '), ensure_ascii=True, default=str.
    Any otro formato produce un hash distinto y la verificación sería MISMATCH (falso positivo)."""
    return json.dumps(d, sort_keys=True, default=str)

def proyectar_fila(conn, tabla, pk_col, pk_val, campos):
    """Proyecta la fila excluyendo row_hash (si está en campos, se omite)."""
    cols = [c for c in campos if c != "row_hash" and c != "rowhash" and c in [r[1] for r in conn.execute("PRAGMA table_info(%s)"%tabla)]]
    # Si alguna columna falta de la tabla (pre-migración), se ignora — garantiza compatibilidad.
    cursor = conn.execute("SELECT %s FROM %s WHERE %s = ?" % (", ".join(cols), tabla, pk_col), (pk_val,))
    row = cursor.fetchone()
    if row is None:
        return None
    d = {cols[i]: row[i] for i in range(len(cols))}
    # Tratar None → None (json.dumps lo convierte en null); números/numeros
    # No redondear floats; preservar representación Python por defecto.
    return d

def calcular_row_hash(conn, tabla, pk_col, pk_val, campos=CAMPOS_RESULTADOS):
    d = proyectar_fila(conn, tabla, pk_col, pk_val, campos)
    if d is None:
        return None
    canon = canonicalizar_dict(d)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()

def verificar_row_hash(conn, tabla, pk_col, pk_val, campos=CAMPOS_RESULTADOS):
    """Retorna tupla (status, expected_or_observed, message).
    Status: MATCH / MISMATCH / ABSENT / NOT_COMPUTED."""
    # Leer valor actual (si existe)
    try:
        cur = conn.execute("SELECT %s FROM %s WHERE %s = ?" % ("row_hash", tabla, pk_col), (pk_val,))
        row = cur.fetchone()
        if row is None:
            return ("ABSENT", None, "fila inexistente")
        current = row[0]
    except sqlite3.OperationalError:
        # columna row_hash podría no existir (pre-migración o reversión)
        current = None
        if current is None:
            # Intentar calcular de todos modos para demostrar que la fila existe; pero sin column no hay comparación
            pass
    if current is None or current == "":
        return ("ABSENT", None, "row_hash vacío o columna ausente; hash no poblado")
    expected = calcular_row_hash(conn, tabla, pk_col, pk_val, campos)
    if expected is None:
        return ("NOT_COMPUTED", current, "no se pudo proyectar fila")
    if expected == current:
        return ("MATCH", current, "hash coincide con representación canónica v1; NO implica autorización ni veracidad semántica")
    else:
        return ("MISMATCH", (current, expected), "representación modificada o corrupción")

# Política de filas históricas sin evidencia (no retroactivas)
POLITICA_HISTORICA = "NO_BACKFILL: filas existentes sin evidencia de scope mantienen scope=NULL; row_hash se calcula solo si se requiere integración futura con autorización contemporánea; nunca se asigna scope retroactivo."
