#!/usr/bin/env python3
"""M415 — pruebas del arreglo de compatibilidad `store.registrar()` ↔ esquema.

Se ejecuta sobre COPIAS. Las bases protegidas (`rxre.sqlite3`,
`tools/rxre/storage/rxre.sqlite3`) solo se abren en modo lectura y se verifica
al final que su sha256 no cambio.

Uso:
    python3 tools/rxre/tests/test_m415_store_compat.py
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
for p in (os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "rxre")):
    if p not in sys.path:
        sys.path.insert(0, p)

from rxre.core import store                      # noqa: E402
from rxre.core import store_compat as sc         # noqa: E402
from rxre.core.claim_evaluator import evaluate_claim_evaluator  # noqa: E402
from rxre.evaluadores_ejecutables import (       # noqa: E402
    evaluar_idempotencia, evaluar_las_7_v3)

PROTEGIDA = os.path.join(ROOT, "rxre.sqlite3")
PROTEGIDA_STORAGE = os.path.join(ROOT, "tools", "rxre", "storage", "rxre.sqlite3")
HUELLA_INICIAL = {PROTEGIDA: sc.sha256_file(PROTEGIDA)}
if os.path.isfile(PROTEGIDA_STORAGE):
    HUELLA_INICIAL[PROTEGIDA_STORAGE] = sc.sha256_file(PROTEGIDA_STORAGE)

_TMP = tempfile.mkdtemp(prefix="m415_test_", dir="/tmp/opencode")

PASS: list = []
FAIL: list = []


def check(nombre, condicion, detalle=""):
    if condicion:
        PASS.append(nombre)
        print("PASS %s" % nombre)
    else:
        FAIL.append((nombre, detalle))
        print("FAIL %s %s" % (nombre, detalle))


def _copia(nombre):
    destino = os.path.join(_TMP, nombre)
    r = sc.migrar_copia(PROTEGIDA, destino)
    assert r["status"] == "PROVEN", r
    return destino, r


def _req(**kw):
    base = {"capability": "m415.test", "question": "q", "target": PROTEGIDA,
            "scope": "static_inspection", "request_id": "t", "contract_version": "M415"}
    base.update(kw)
    return base


def _resultado(rid, valor="v", tipo="T"):
    return {"result_id": rid, "type": tipo, "value": valor, "source": "m415",
            "scope": "static_inspection", "tool": "probe", "tool_version": "1",
            "status": "ok", "location": {"file": PROTEGIDA, "line": 0}}


# --------------------------------------------------------------------------
# 1-4: deteccion, migracion, invariantes, idempotencia
# --------------------------------------------------------------------------
def test_01_deteccion_columnas_faltantes():
    c = sqlite3.connect("file:%s?mode=ro" % PROTEGIDA, uri=True)
    try:
        faltan = sc.columnas_faltantes(c)
        total = sum(len(v) for v in faltan.values())
        check("01_detecta_8_columnas_faltantes", total == 8, faltan)
        check("01_operations_5", len(faltan.get("operations", [])) == 5,
              faltan.get("operations"))
        check("01_results_3", len(faltan.get("results", [])) == 3,
              faltan.get("results"))
    finally:
        c.close()


def test_02_migracion_equivale_a_base_creada_desde_cero():
    destino, r = _copia("t02.sqlite3")
    check("02_migracion_PROVEN", r["status"] == "PROVEN", r.get("reason"))
    check("02_anade_exactamente_8", r["columnas_anadidas_total"] == 8,
          r["columnas_anadidas"])

    # La migracion debe producir la MISMA forma que el DDL de store.py.
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(store.DDL)
    c = sqlite3.connect("file:%s?mode=ro" % destino, uri=True)
    try:
        for tabla, cols in sc.COLUMNAS_FALTANTES.items():
            esperado = {r2[1]: {"type": r2[2], "notnull": r2[3],
                                "default": r2[4], "pk": r2[5]}
                        for r2 in fresh.execute("PRAGMA table_info(%s)" % tabla)
                        if r2[1] in dict(cols)}
            actual = {r2[1]: {"type": r2[2], "notnull": r2[3],
                              "default": r2[4], "pk": r2[5]}
                      for r2 in c.execute("PRAGMA table_info(%s)" % tabla)
                      if r2[1] in dict(cols)}
            check("02_%s_identico_al_DDL" % tabla, esperado == actual,
                  {"esperado": esperado, "actual": actual})
    finally:
        c.close()
        fresh.close()


def test_03_datos_preexistentes_intactos():
    destino, r = _copia("t03.sqlite3")
    check("03_hash_filas_igual", r["antes"]["sha256"] == r["despues"]["sha256"],
          {"antes": r["antes"]["sha256"], "despues": r["despues"]["sha256"]})
    check("03_conteo_filas_igual",
          r["antes"]["filas_total"] == r["despues"]["filas_total"],
          (r["antes"]["filas_total"], r["despues"]["filas_total"]))
    check("03_invariantes_ok", r["invariantes_ok"] is True, r.get("problemas"))
    check("03_integridad_ok", r["integridad"]["integrity_check"] == "ok",
          r["integridad"])
    # datos concretos que no deben cambiar
    c = sqlite3.connect("file:%s?mode=ro" % destino, uri=True)
    try:
        check("03_operations_siguen_2",
              c.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 2)
        check("03_results_siguen_3",
              c.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 3)
    finally:
        c.close()


def test_04_migracion_idempotente():
    destino, r1 = _copia("t04.sqlite3")
    r2 = sc.migrar_copia(destino, os.path.join(_TMP, "t04b.sqlite3"))
    check("04_segunda_pasada_0_columnas",
          r2["status"] == "PROVEN" and r2["columnas_anadidas_total"] == 0,
          r2.get("reason"))
    check("04_segunda_pasada_no_cambia_datos",
          r2["antes"]["sha256"] == r2["despues"]["sha256"],
          (r2["antes"]["sha256"], r2["despues"]["sha256"]))
    check("04_no_repite_procedencia",
          r2["meta_compat"].get("store_compat_added_json")
          == r1["meta_compat"].get("store_compat_added_json"),
          r2["meta_compat"])


# --------------------------------------------------------------------------
# 5-8: persistencia, recuperacion, integridad, datos incompatibles
# --------------------------------------------------------------------------
def test_05_registrar_y_recuperar_con_row_hash():
    c, info = sc.abrir_copia_migrada(PROTEGIDA,
                                     os.path.join(_TMP, "t05.sqlite3"))
    try:
        env = {"status": "ok", "operation": "m415",
               "results": [_resultado("res_m415_a", "uno"),
                           _resultado("res_m415_b", "dos", "U"),
                           _resultado("res_m415_c", "tres", "V")]}
        reg = sc.registrar_verificado(c, _req(), env, 0.01)
        check("05_registrar_PROVEN", reg["status"] == "PROVEN", reg)
        check("05_3_recuperados", reg["recuperados"] == 3, reg["recuperados"])
        check("05_row_hash_verified", reg["row_hash_verified"] is True)
        check("05_operacion_explica_3", reg["resultados_en_operacion"] == 3,
              reg["resultados_en_operacion"])
        check("05_conectar_crea_tablas_conocidas",
              "edges" in (info["objetos_creados_por_store_conectar"]
                          .get("table", [])),
              info["objetos_creados_por_store_conectar"])
        # recuperacion con conexion NUEVA (independiente del escritor)
    finally:
        c.close()
    c2 = store.conectar(os.path.join(_TMP, "t05.sqlite3"))
    try:
        rec = store.recuperar_evidencia_resultados(
            c2, ["res_m415_a", "res_m415_b", "res_m415_c"])
        check("05_recuperacion_independiente", len(rec) == 3, list(rec))
        # `recuperar_evidencia_resultados` devuelve
        # {result_id: {result: {...}, operation: {...}, op_id: ...}} y los
        # alias (`result_value`) viven DENTRO de `result`.
        check("05_forma_anidada",
              set(rec["res_m415_b"]) >= {"result", "operation", "op_id"},
              sorted(rec["res_m415_b"]))
        check("05_valores_releidos",
              rec["res_m415_b"]["result"]["result_value"] == "dos",
              rec["res_m415_b"]["result"].get("result_value"))
        check("05_op_id_releido",
              rec["res_m415_b"]["op_id"] == reg["operation_id"],
              (rec["res_m415_b"].get("op_id"), reg["operation_id"]))
    finally:
        c2.close()


def test_06_append_only_no_sobrescribe():
    c, _ = sc.abrir_copia_migrada(PROTEGIDA,
                                  os.path.join(_TMP, "t06.sqlite3"))
    try:
        rid = "res_m415_dup"
        r1 = sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [_resultado(rid, "primero")]})
        r2 = sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [_resultado(rid, "segundo-NO-DEBE-PISAR")]})
        h1 = r1["hashes"][rid]["row_hash"]
        h2 = r2["hashes"][rid]["row_hash"]
        filas = c.execute("SELECT COUNT(*) FROM results WHERE result_id=?",
                          (rid,)).fetchone()[0]
        valor = c.execute("SELECT value FROM results WHERE result_id=?",
                          (rid,)).fetchone()[0]
        colision = c.execute("SELECT COUNT(*) FROM audit_log WHERE "
                             "action='collision' AND entity_id=?",
                             (rid,)).fetchone()[0]
        check("06_mismo_row_hash", h1 == h2, (h1, h2))
        check("06_una_sola_fila", filas == 1, filas)
        check("06_valor_original_intacto", valor == "primero", valor)
        check("06_colision_auditada", colision >= 1, colision)
    finally:
        c.close()


def test_07_hash_alterado_detectado():
    ruta = os.path.join(_TMP, "t07.sqlite3")
    c, _ = sc.abrir_copia_migrada(PROTEGIDA, ruta)
    try:
        sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [_resultado("res_m415_tamper", "x")]})
        # alteracion directa que el trigger no cubre (UPDATE esta prohibido,
        # asi que se desactiva el trigger solo en esta copia de prueba)
        c.execute("DROP TRIGGER trg_results_no_update")
        c.execute("UPDATE results SET value='ALTERADO' WHERE result_id=?",
                  ("res_m415_tamper",))
        c.commit()
    finally:
        c.close()
    c2 = store.conectar(ruta)
    try:
        try:
            store.recuperar_evidencia_resultados(c2, ["res_m415_tamper"])
            detectado = False
        except Exception:
            detectado = True
        check("07_row_hash_alterado_detectado", detectado)
    finally:
        c2.close()


def test_08_datos_incompatibles_no_corrompen():
    c, _ = sc.abrir_copia_migrada(PROTEGIDA,
                                  os.path.join(_TMP, "t08.sqlite3"))
    try:
        antes = c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        # (a) resultado sin result_id: se ignora, la operacion se registra
        reg = sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [{"value": "sin-id", "type": "T"}]})
        despues = c.execute("SELECT COUNT(*) FROM results").fetchone()[0]
        check("08_sin_result_id_no_inserta", antes == despues, (antes, despues))
        check("08_operacion_si_registrada", bool(reg["operation_id"]))
        # (b) payload no serializable: no revienta (default=str) y se relee
        reg2 = sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [{**_resultado("res_m415_bytes", "b"),
                                     "raw": {"conjunto": {1, 2, 3},
                                             "bytes": b"\x00\x01"}}]})
        check("08_payload_no_serializable_ok", reg2["status"] == "PROVEN",
              reg2)
        # (c) valor de 5000 chars: se trunca a 4000 y el row_hash sigue cuadrando
        reg3 = sc.registrar_verificado(
            c, _req(), {"status": "ok", "operation": "m415",
                        "results": [_resultado("res_m415_largo", "x" * 5000)]})
        largo = c.execute("SELECT LENGTH(value) FROM results WHERE result_id=?",
                          ("res_m415_largo",)).fetchone()[0]
        check("08_valor_truncado_a_4000", largo == 4000, largo)
        check("08_row_hash_tras_truncado", reg3["row_hash_verified"] is True)
        # (d) request vacio: no revienta, usa defaults
        reg4 = sc.registrar_verificado(
            c, {}, {"status": "", "results": [_resultado("res_m415_vacio")]})
        check("08_request_vacio_ok", reg4["status"] == "PROVEN", reg4)
    finally:
        c.close()


# --------------------------------------------------------------------------
# 9-11: rollback y proteccion de las bases reales
# --------------------------------------------------------------------------
def test_09_rollback_restaura_snapshot():
    ruta = os.path.join(_TMP, "t09.sqlite3")
    c, _ = sc.abrir_copia_migrada(PROTEGIDA, ruta)
    check("09_partimos_de_migrada", sc.es_compatible(c))
    sc.registrar_verificado(
        c, _req(), {"status": "ok", "operation": "m415",
                    "results": [_resultado("res_m415_rollback", "z")]})
    c.close()

    # snapshot = la base ORIGINAL protegida (copia limpia, sin migrar)
    snapshot = os.path.join(_TMP, "t09_snapshot.sqlite3")
    src = sqlite3.connect("file:%s?mode=ro" % PROTEGIDA, uri=True)
    dst = sqlite3.connect(snapshot)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    r = sc.deshacer(ruta, snapshot)
    check("09_rollback_PROVEN", r["status"] == "PROVEN", r)
    check("09_contenido_igual_al_snapshot",
          r["huella_destino"] == r["huella_snapshot"],
          (r["huella_destino"], r["huella_snapshot"]))
    c2 = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
    try:
        existe = c2.execute("SELECT COUNT(*) FROM results WHERE result_id=?",
                            ("res_m415_rollback",)).fetchone()[0]
        cols = [x[1] for x in c2.execute("PRAGMA table_info(operations)")]
        check("09_fila_nueva_desaparece", existe == 0, existe)
        check("09_columnas_migradas_revertidas",
              "declared_scope" not in cols, cols)
    finally:
        c2.close()


def test_10_rechaza_migrar_protegida_en_sitio():
    r = sc.migrar_copia(PROTEGIDA, PROTEGIDA)
    check("10_mismo_archivo_BLOCKED", r["status"] == "BLOCKED", r)
    r2 = sc.migrar_copia(os.path.join(_TMP, "t03.sqlite3"), PROTEGIDA)
    check("10_destino_protegido_BLOCKED",
          r2["status"] == "BLOCKED"
          and "PROHIBIDA" in r2.get("reason", ""), r2)
    r3 = sc.migrar_copia(PROTEGIDA, PROTEGIDA_STORAGE)
    check("10_storage_protegida_BLOCKED", r3["status"] == "BLOCKED", r3)
    # asegurar_esquema sobre la protegida (solo lectura) debe negarse
    c = sqlite3.connect("file:%s?mode=ro" % PROTEGIDA, uri=True)
    try:
        try:
            sc.asegurar_esquema(c)
            negado = False
        except PermissionError:
            negado = True
        check("10_asegurar_esquema_negado", negado)
    finally:
        c.close()
    # destino existente: no se sobrescribe evidencia
    existente = os.path.join(_TMP, "t03.sqlite3")
    r4 = sc.migrar_copia(PROTEGIDA, existente)
    check("10_destino_existente_BLOCKED", r4["status"] == "BLOCKED", r4)


def test_11_bases_protegidas_intactas():
    for ruta, huella in HUELLA_INICIAL.items():
        actual = sc.sha256_file(ruta)
        check("11_intacta_%s" % os.path.basename(os.path.dirname(ruta)) or ruta,
              actual == huella, (huella[:16], actual[:16]))
        c = sqlite3.connect("file:%s?mode=ro" % ruta, uri=True)
        try:
            cols = [x[1] for x in c.execute("PRAGMA table_info(operations)")]
        finally:
            c.close()
        check("11_sin_migrar_%s" % os.path.basename(ruta),
              "declared_scope" not in cols)


# --------------------------------------------------------------------------
# 12-13: los evaluadores discriminan
# --------------------------------------------------------------------------
def test_12_evaluador_idempotencia_discrimina():
    ok = evaluar_idempotencia(digest_a="a" * 64, digest_b="a" * 64,
                              origen=PROTEGIDA,
                              workdir=os.path.join(_TMP, "t12a"))
    check("12_positivo_PROVEN", ok["estado"] == "PROVEN", ok["checks"])

    malo = evaluar_idempotencia(digest_a="a" * 64, digest_b="b" * 64,
                                origen=PROTEGIDA,
                                workdir=os.path.join(_TMP, "t12b"))
    check("12_negativo_PROVEN_ABSENT", malo["estado"] == "PROVEN_ABSENT",
          malo["checks"])
    check("12_negativo_senala_el_check",
          "experimento_mismo_digest" in malo["fallan"], malo["fallan"])

    sin_medir = evaluar_idempotencia(digest_a=None, digest_b=None,
                                     origen=PROTEGIDA,
                                     workdir=os.path.join(_TMP, "t12c"))
    check("12_sin_medir_NOT_DETERMINED",
          sin_medir["estado"] == "NOT_DETERMINED", sin_medir["checks"])

    # un origen inexistente falla de forma medible, no silenciosa
    roto = evaluar_idempotencia(digest_a="a", digest_b="a",
                                origen="/nonexistent/m415.sqlite3",
                                workdir=os.path.join(_TMP, "t12d"))
    check("12_origen_inexistente_no_es_PROVEN",
          roto["estado"] == "PROVEN_ABSENT", roto["estado"])


def test_13_evaluador_las_7_v3_discrimina():
    real = evaluar_las_7_v3()
    check("13_suite_real_PROVEN", real["estado"] == "PROVEN", real)
    check("13_resumen_7_de_7",
          real["detalle"].get("resumen", "").startswith("RESUMEN: 7/7"),
          real["detalle"].get("resumen"))

    # (a) suite ausente => NOT_DETERMINED (no False): no se pudo medir
    ausente = evaluar_las_7_v3(suite=os.path.join(_TMP, "no_existe.py"))
    check("13_suite_ausente_NOT_DETERMINED",
          ausente["estado"] == "NOT_DETERMINED", ausente["estado"])

    # (b) suite que declara solo 3 mutaciones => cobertura incompleta => ABSENT
    fuente = open(sc_suite(), "r", encoding="utf-8").read()
    parcial = os.path.join(_TMP, "mutacion_parcial.py")
    with open(parcial, "w", encoding="utf-8") as fh:
        fh.write(fuente.replace('"V3-7_ACCEPTED_CON_AUTORIDAD_DECLARADA"',
                                '"OTRA_COSA"'))
    r = evaluar_las_7_v3(suite=parcial)
    check("13_cobertura_incompleta_no_PROVEN",
          r["estado"] == "PROVEN_ABSENT", r["checks"])
    check("13_cobertura_detectada",
          r["checks"].get("mutaciones_cubren_las_7") is False, r["checks"])


def sc_suite():
    return os.path.join(ROOT, "tools", "rxre", "tests",
                        "test_arquitectura_v3_03_mutacion.py")


# --------------------------------------------------------------------------
def main() -> int:
    pruebas = [
        test_01_deteccion_columnas_faltantes,
        test_02_migracion_equivale_a_base_creada_desde_cero,
        test_03_datos_preexistentes_intactos,
        test_04_migracion_idempotente,
        test_05_registrar_y_recuperar_con_row_hash,
        test_06_append_only_no_sobrescribe,
        test_07_hash_alterado_detectado,
        test_08_datos_incompatibles_no_corrompen,
        test_09_rollback_restaura_snapshot,
        test_10_rechaza_migrar_protegida_en_sitio,
        test_12_evaluador_idempotencia_discrimina,
        test_13_evaluador_las_7_v3_discrimina,
        test_11_bases_protegidas_intactas,
    ]
    print("=== M415: compatibilidad store.registrar() <-> esquema ===")
    for p in pruebas:
        try:
            p()
        except Exception:
            FAIL.append((p.__name__, "excepcion"))
            print("FAIL %s (excepcion)" % p.__name__)
            traceback.print_exc()
    print()
    print("=== RESUMEN M415: %d PASS, %d FAIL ===" % (len(PASS), len(FAIL)))
    for nombre, detalle in FAIL:
        print("  FAIL %s: %s" % (nombre, detalle))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
