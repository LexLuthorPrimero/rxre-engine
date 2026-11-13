#!/usr/bin/env python3
"""REGRESSION 080 — contrato de integridad de results.raw_json.
Protege el contrato entre `core/store.py` (integridad_referencia),
`core/hash.py` (hash_file/verify_integrity) y `audit/debugfs/evidence_identity_066.py`
(verificar_ref) frente al caso 077 (`sha256_ref` clave no reconocida).

No modifica contrato de produccion. No usa .rxre/storage/. Solo lectura + DB temporal.
"""
import sys, os, tempfile, json, sqlite3
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
for p in (str(REPO / "tools" / "rxre"), str(REPO / "audit" / "debugfs")):
    if p not in sys.path:
        sys.path.insert(0, p)
from core.store import integridad_referencia, conectar, buscar, explicar, investigacion
from core.hash import hash_file

# El verificador de evidencia vive fuera del paquete rxre; se importa por ruta
from evidence_identity_066 import verificar_ref


def _tmp_db():
    d = tempfile.mkdtemp(prefix="rxre_reg_080_")
    return os.path.join(d, "test_contract.sqlite3")


def test_contrato_hash_canonico_archivo_intacto_es_proven():
    """C1: archivo intacto + sha256_file_ref => PROVEN."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"reference_artifact_for_regression_080")
        art_path = f.name
    db = _tmp_db()
    c = conectar(db)
    h = hash_file(art_path)
    raw = json.dumps({"sha256_file_ref": h, "origen": "regression_080", "scope": "rx550"})
    c.execute("INSERT INTO results (result_id,type,value,source,file,status,raw_json,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("res_c1", "EVIDENCE", "ref_c1", "audit/debugfs/080", art_path, "PROVEN", raw, "2026-10-20T11:00:00"))
    c.commit()
    # integridad_referencia con clave canonica
    res = integridad_referencia(art_path, raw)
    assert res["estado"] == "PROVEN", f"C1 esperado PROVEN, obtuvo {res['estado']} (key={raw})"
    # verificar_ref con clave canonica
    vr = verificar_ref(c, "res_c1")
    assert vr["status"] == "PROVEN", f"C1 verificar_ref PROVEN, obtuvo {vr['status']}"
    # buscar recupera
    bu = buscar(c, archivo=os.path.basename(art_path))
    assert bu["status"] == "ok", f"C1 buscar ok, obtuvo {bu['status']}"
    # limpiar
    c.close(); os.unlink(db); os.unlink(art_path); os.rmdir(os.path.dirname(db))


def test_contrato_clave_desconocida_es_no_verificable():
    """C2: archivo intacto + sha256_ref (clave desconocida) => NO_VERIFICABLE, NO MODIFICADO."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"reference_artifact_for_regression_080")
        art_path = f.name
    db = _tmp_db()
    c = conectar(db)
    h = hash_file(art_path)
    # clave NO reconocida: sha256_ref (como en 077)
    raw = json.dumps({"sha256_ref": h, "origen": "regression_080_bad_key", "scope": "rx550"})
    c.execute("INSERT INTO results (result_id,type,value,source,file,status,raw_json,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("res_c2", "EVIDENCE", "ref_c2", "audit/debugfs/080", art_path, "PROVEN", raw, "2026-10-20T11:00:00"))
    c.commit()
    res = integridad_referencia(art_path, raw)
    assert res["estado"] == "NO_VERIFICABLE", f"C2 esperado NO_VERIFICABLE por clave, obtuvo {res['estado']}"
    # No debe ser MODIFICADO (archivo no alterado)
    assert res["estado"] != "MODIFICADO", f"C2 NO debe ser MODIFICADO por clave incorrecta (archivo intacto)"
    vr = verificar_ref(c, "res_c2")
    assert vr["status"] == "DIVERGENTE", f"C2 verificar_ref DIVERGENTE, obtuvo {vr['status']}"
    # El archivo sigue intacto (hash coincide); la clave es la divergencia
    assert hash_file(art_path) == h
    c.close(); os.unlink(db); os.unlink(art_path); os.rmdir(os.path.dirname(db))


def test_contrato_archivo_inexistente_es_ausente():
    """C3: archivo inexistente + hash declarado => AUSENTE."""
    db = _tmp_db()
    c = conectar(db)
    art_path = "/tmp/nonexistent_path_080_missing_file.txt"
    h = "0" * 64
    raw = json.dumps({"sha256_file_ref": h, "origen": "regression_080", "scope": "rx550"})
    c.execute("INSERT INTO results (result_id,type,value,source,file,status,raw_json,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("res_c3", "EVIDENCE", "ref_c3", "audit/debugfs/080", art_path, "PROVEN", raw, "2026-10-20T11:00:00"))
    c.commit()
    res = integridad_referencia(art_path, raw)
    assert res["estado"] == "AUSENTE", f"C3 esperado AUSENTE, obtuvo {res['estado']}"
    vr = verificar_ref(c, "res_c3")
    assert vr["status"] == "AUSENTE", f"C3 verificar_ref AUSENTE, obtuvo {vr['status']}"
    c.close(); os.unlink(db); os.rmdir(os.path.dirname(db))


def test_contrato_archivo_alterado_es_modificado():
    """C4: archivo alterado + hash original declarado => MODIFICADO."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"original_content_for_regression_080")
        art_path = f.name
    h_original = hash_file(art_path)
    # alterar contenido sin cambiar ruta ni ID
    with open(art_path, "ab") as f:
        f.write(b"\nALTERED_CONTENT_080")
    db = _tmp_db()
    c = conectar(db)
    # registra con hash del archivo ORIGINAL (como si hubiera sido registrado antes de alterar)
    raw = json.dumps({"sha256_file_ref": h_original, "origen": "regression_080", "scope": "rx550"})
    c.execute("INSERT INTO results (result_id,type,value,source,file,status,raw_json,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("res_c4", "EVIDENCE", "ref_c4", "audit/debugfs/080", art_path, "PROVEN", raw, "2026-10-20T11:00:00"))
    c.commit()
    res = integridad_referencia(art_path, raw)
    assert res["estado"] == "MODIFICADO", f"C4 esperado MODIFICADO, obtuvo {res['estado']}"
    # verificador debe detectar MODIFICADO (hash obsoleto)
    vr = verificar_ref(c, "res_c4")
    assert vr["status"] == "MODIFICADO", f"C4 verificar_ref MODIFICADO, obtuvo {vr['status']}"
    c.close(); os.unlink(db); os.unlink(art_path); os.rmdir(os.path.dirname(db))


def test_contrato_estado_epistemico_no_promovido_por_integridad():
    """C5: integridad fisica PROVEN no convierte NOT_DETERMINED a PROVEN."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"ref_for_epistemic_080")
        art_path = f.name
    db = _tmp_db()
    c = conectar(db)
    h = hash_file(art_path)
    # registro de evidencia con C4 no aplica; registramos referencia y luego claim con NOT_DETERMINED
    raw_ref = json.dumps({"sha256_file_ref": h, "origen": "regression_080_ep", "scope": "rx550"})
    c.execute("INSERT INTO results (result_id,type,value,source,file,status,raw_json,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("res_ep_ref", "EVIDENCE", "ref_ep", "audit/debugfs/080", art_path, "PROVEN", raw_ref, "2026-10-20T11:00:00"))
    # claim NOT_DETERMINED con gap HUECO_DE_EVIDENCIA que referencia el archivo intacto
    c.execute("INSERT INTO research (kind,status,text,gap_kind,refs_json,session,target,timestamp) VALUES (?,?,?,?,?,?,?,?)",
              ("hypothesis", "NOT_DETERMINED",
               "Actividad fisica UVD/VCN no observada (NOT_DETERMINED); archivo de evidencia integro no cambia el estado",
               "HUECO_DE_EVIDENCIA",
               json.dumps(["res_ep_ref"]),
               "RXRE-TEST-080", "rx550", "2026-10-20T11:00:00"))
    c.commit()
    # integridad de referencia es PROVEN (archivo intacto + clave correcta)
    ir = integridad_referencia(art_path, raw_ref)
    assert ir["estado"] == "PROVEN", f"C5 integridad debe ser PROVEN, obtuvo {ir['estado']}"
    # explicar de referencia
    expl = explicar(c, "res_ep_ref")
    assert expl["status"] == "ok" and expl["integridad"]["estado"] == "PROVEN"
    # investigacion debe recuperar la hipotesis con NOT_DETERMINED, sin alterar a PROVEN
    inv = investigacion(c, session="RXRE-TEST-080", target="rx550")
    entries = inv.get("entradas", [])
    assert len(entries) == 1, f"C5 debe recuperar 1 entrada, obtuvo {len(entries)}"
    entry = entries[0]
    assert entry["kind"] == "hypothesis", f"C5 kind hypothesis, obtuvo {entry['kind']}"
    assert entry["status"] == "NOT_DETERMINED", f"C5 status NOT_DETERMINED preservado, obtuvo {entry['status']}"
    assert entry.get("gap_kind") == "HUECO_DE_EVIDENCIA"
    # no se convierte en PROVEN por integridad
    c.close(); os.unlink(db); os.unlink(art_path); os.rmdir(os.path.dirname(db))


if __name__ == "__main__":
    for t in [test_contrato_hash_canonico_archivo_intacto_es_proven,
              test_contrato_clave_desconocida_es_no_verificable,
              test_contrato_archivo_inexistente_es_ausente,
              test_contrato_archivo_alterado_es_modificado,
              test_contrato_estado_epistemico_no_promovido_por_integridad]:
        try:
            t()
            print("PASS", t.__name__)
        except Exception as exc:
            print("FAIL", t.__name__, "-", type(exc).__name__, str(exc)[:80])
            sys.exit(1)
