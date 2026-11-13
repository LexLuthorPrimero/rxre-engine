#!/usr/bin/env python3
"""RXRE-MISSION-283 — REFUTACIÓN ADVERSARIAL DE scope_provenance_contract.
Aislamiento total: DB_ISO propia + copias manipuladas de manifiestos en /tmp.
NO escribe en DB_OP. NO modifica store.py / machine.py / evidence_integrity.py.
Clasifica cada caso: PROVEN / REFUTED / INSUFFICIENT / NOT_DETERMINED.
"""
import sys, os, json, sqlite3, hashlib, shutil
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import store
from rxre.core import e2e_manifest_producer as prod
from rxre.contracts import scope_provenance_contract as spc

DB_ISO = "/tmp/rxre_283_iso.sqlite3"
TMP = "/tmp/rxre_283_adv"
ART_A = "/home/lucas/Escritorio/rxre/audit/artefactos/verificacion_282_20261022.txt"
ART_B = "/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt"
HASH_A = hashlib.sha256(open(ART_A, "rb").read()).hexdigest()
HASH_B = hashlib.sha256(open(ART_B, "rb").read()).hexdigest()

RESULTADOS = []

def registrar(nombre):
    for s in ("", "-wal", "-shm"):
        p = DB_ISO + s
        if os.path.exists(p): os.remove(p)
    return store.conectar(DB_ISO)

def op(c, op_scope, res_id, art, h, actor="lucas", decision="APPROVED", ts="2026-10-22T00:00:00Z"):
    req = {"op": "claim", "target": "adv", "scope": op_scope,
           "scope_authorization": {"decision": decision, "actor": actor, "timestamp": ts, "scope": op_scope}}
    env = {"status": "ok", "op": "claim", "results": [
        {"result_id": res_id, "type": "adv", "value": "v", "source": "adv",
         "location": {"file": art, "line": 0}, "scope": op_scope, "tool": "adv", "tool_version": "1",
         "status": "ok", "raw_json": {"hash": h}, "timestamp": "2026-10-22T00:00:00Z"}]}
    return store.registrar(c, req, env, 0.0)

def registrar_manifiesto(db, op_id, res_id, destino):
    r = prod.generar_manifest_e2e(db, op_id, res_id, destino, "e2e_adv")
    return r["status"] == "WRITTEN"

def caso(letra, nombre, precond, alteracion, decision_esperada, decision_observada, explicacion):
    refutado = (decision_observada == "VERIFIED" and decision_esperada != "VERIFIED")
    clase = "REFUTED" if refutado else ("PROVEN" if decision_observada == decision_esperada else "INSUFFICIENT")
    RESULTADOS.append({"caso": letra, "nombre": nombre, "precondiciones": precond,
                        "alteracion": alteracion, "esperado": decision_esperada,
                        "observado": decision_observada, "acepto": decision_observada,
                        "clase": clase, "explicacion": explicacion})
    print("[%s-%s] esperado=%s observado=%s -> %s" % (letra, clase, decision_esperada, decision_observada, nombre))

def main():
    os.makedirs(TMP, exist_ok=True)
    c = registrar("x")
    op1 = op(c, "scope_adv", "res_adv_1", ART_A, HASH_A)
    op2 = op(c, "scope_adv", "res_adv_2", ART_B, HASH_B)   # MISMO scope, artefacto distinto
    op3 = op(c, "scope_adv_other", "res_adv_3", ART_A, HASH_A)  # scope distinto
    c.close()
    m1 = TMP + "/mf1.json"; m2 = TMP + "/mf2.json"; m3 = TMP + "/mf3.json"
    assert registrar_manifiesto(DB_ISO, op1, "res_adv_1", m1)
    assert registrar_manifiesto(DB_ISO, op2, "res_adv_2", m2)
    assert registrar_manifiesto(DB_ISO, op3, "res_adv_3", m3)

    # A. Manifiesto íntegro de OTRA operación (mismo scope)
    d = spc.verificar_autoridad_scope("ref_A", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m2)
    caso("A", "Manifiesto de otra operacion (mismo scope)", "DB res_adv_1 + manifest de op2",
         "manifest_e2e_path=m2 (op2/res_adv_2)", "REJECTED/INDETERMINATE", d["decision"],
         "explanation=%s" % d["explanation"])

    # B. Manifiesto con mismo alcance y hash pero otro resultado
    mf = json.load(open(m1)); mf2 = dict(mf); mf2["result_id"] = "res_adv_2"
    mb = TMP + "/mf1_result2.json"; json.dump(mf2, open(mb, "w"), indent=2, sort_keys=True)
    d = spc.verificar_autoridad_scope("ref_B", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=mb)
    caso("B", "Manifiesto con mismo scope/hash pero result_id distinto", "DB res_adv_1 + mf1 alterado",
         "mf1.result_id := res_adv_2", "REJECTED/INDETERMINATE", d["decision"], d["explanation"])

    # C. Hash válido de artefacto distinto al referenciado por la fila
    d = spc.verificar_autoridad_scope("ref_C", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1,
                                      observed_artifact_path=ART_B, observed_hash=HASH_B)
    caso("C", "Hash valido de artefacto distinto al de la fila", "DB res_adv_1 + mf1",
         "observed_artifact_path=ART_B, observed_hash=HASH_B", "REJECTED/INDETERMINATE", d["decision"],
         d["explanation"])

    # D. Alcance declarado coincidente, autorización de otra operación
    d = spc.verificar_autoridad_scope("ref_D", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    d2 = spc.verificar_autoridad_scope("ref_D", claim_scope="scope_adv", db_op_path=DB_ISO,
                                       db_op_result_id="res_adv_3", manifest_e2e_path=m1)
    caso("D", "Autorizacion perteneciente a otra operacion", "DB res_adv_3 (scope_adv_other) + mf1 (scope_adv)",
         "db_op_result_id=res_adv_3, manifest=m1(scope_adv)", "REJECTED/INDETERMINATE", d2["decision"],
         d2["explanation"])

    # E. Autorización válida pero actor/timestamp/alcance alterado en la BD
    c2 = sqlite3.connect(DB_ISO)
    c2.execute("UPDATE operations SET auth_actor='attacker', auth_timestamp='1999-01-01T00:00:00Z' WHERE operation_id=?", (op1,))
    c2.commit(); c2.close()
    d = spc.verificar_autoridad_scope("ref_E", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    caso("E", "Actor/timestamp de autorizacion alterado en BD", "DB res_adv_1 + mf1",
         "operations.auth_actor='attacker', auth_timestamp='1999-01-01'", "REJECTED/INDETERMINATE", d["decision"],
         d["explanation"])

    # F. Manifiesto duplicado/ambiguo para la misma operación
    d = spc.verificar_autoridad_scope("ref_F", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    dup = TMP + "/mf1_dup.json"; shutil.copy(m1, dup)
    d2 = spc.verificar_autoridad_scope("ref_F", claim_scope="scope_adv", db_op_path=DB_ISO,
                                       db_op_result_id="res_adv_1", manifest_e2e_path=dup)
    caso("F", "Manifiesto duplicado (ambiguedad no detectada)", "DB res_adv_1 + mf1 y copia identica",
         "dos manifiestos identicos para misma operacion", "INDETERMINATE/REJECTED",
         d["decision"] if d["decision"] == d2["decision"] else "AMBIGUO(%s/%s)" % (d["decision"], d2["decision"]),
         d["explanation"])

    # G. Campos ausentes, referencias inexistentes, tipos inválidos
    g1 = spc.verificar_autoridad_scope("", claim_scope="scope_adv", db_op_path=DB_ISO, db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    g2 = spc.verificar_autoridad_scope("ref_G", claim_scope="scope_adv", db_op_path=DB_ISO, db_op_result_id="res_inexistente_283", manifest_e2e_path=m1)
    g3 = spc.verificar_autoridad_scope("ref_G", claim_scope="scope_adv", db_op_path=DB_ISO, db_op_result_id="res_adv_1", manifest_e2e_path=TMP + "/no_existe.json")
    g4 = spc.verificar_autoridad_scope(123, claim_scope="scope_adv", db_op_path=DB_ISO, db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    caso("G", "Campos ausentes / refs inexistentes / tipos invalidos", "4 subcasos",
         "evidence_ref vacio / result_id inexistente / manifest inexistente / evidence_ref entero",
         "INVALID/REJECTED", "|".join([g1["decision"], g2["decision"], g3["decision"], g4["decision"]]),
         "g2=%s" % g2["explanation"])

    # H. Hash del artefacto alterado despues de generar el manifiesto
    art_h = TMP + "/art_h.txt"; shutil.copy(ART_A, art_h)
    mh = TMP + "/mf_h.json"
    c3 = registrar("h")
    oph = op(c3, "scope_adv_h", "res_adv_h", art_h, hashlib.sha256(open(art_h, "rb").read()).hexdigest())
    c3.close()
    assert registrar_manifiesto(DB_ISO, oph, "res_adv_h", mh)
    with open(art_h, "a") as f: f.write("\nALTERADO\n")
    d = spc.verificar_autoridad_scope("ref_H", claim_scope="scope_adv_h", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_h", manifest_e2e_path=mh)
    caso("H", "Artefacto alterado despues de generar el manifiesto", "artefacto copiado + mf_h",
         "artefacto modificado post-manifiesto", "REJECTED/INDETERMINATE", d["decision"], d["explanation"])

    # I. verified_scope / scope_decision vacios o contradictorios
    c4 = sqlite3.connect(DB_ISO)
    c4.execute("UPDATE results SET scope_decision='CONFLICT' WHERE result_id='res_adv_1'")
    c4.commit(); c4.close()
    d = spc.verificar_autoridad_scope("ref_I", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    caso("I", "scope_decision contradictorio en la fila", "DB res_adv_1 (scope_decision=CONFLICT) + mf1",
         "results.scope_decision := 'CONFLICT'", "REJECTED/INDETERMINATE", d["decision"], d["explanation"])

    # J. Manifiesto correcto pero row_hash de la fila incorrecto
    c5 = sqlite3.connect(DB_ISO)
    c5.execute("UPDATE results SET row_hash='0'*64 WHERE result_id='res_adv_1'")
    c5.commit(); c5.close()
    d = spc.verificar_autoridad_scope("ref_J", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m1)
    caso("J", "row_hash de la fila incorrecto", "DB res_adv_1 (row_hash=000..0) + mf1",
         "results.row_hash := '0'*64", "REJECTED/INDETERMINATE", d["decision"], d["explanation"])

    # K. DB y manifiesto coherentes por separado, sin relacion causal demostrable
    d = spc.verificar_autoridad_scope("ref_K", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=m2)
    caso("K", "Fuentes coherentes pero sin relacion causal demostrable", "DB res_adv_1 + mf2 (otra op)",
         "manifest de operacion distinta, mismo scope", "REJECTED/INDETERMINATE", d["decision"], d["explanation"])

    # L (extra). Solo DB, sin manifiesto -> §5 del contrato
    d = spc.verificar_autoridad_scope("ref_L", claim_scope="scope_adv", db_op_path=DB_ISO,
                                      db_op_result_id="res_adv_1", manifest_e2e_path=None)
    caso("L", "Solo fuente operativa (sin manifiesto)", "DB res_adv_1, manifest=None",
         "manifest_e2e_path=None", "INDETERMINATE/REJECTED", d["decision"], d["explanation"])

    json.dump(RESULTADOS, open("/tmp/rxre_283_resultados.json", "w"), indent=2, sort_keys=True)
    refutados = [r for r in RESULTADOS if r["clase"] == "REFUTED"]
    print("\n=== M283 RESUMEN ===")
    print("casos: %d | REFUTED: %d | PROVEN: %d | INSUFFICIENT: %d" %
          (len(RESULTADOS), len(refutados),
           len([r for r in RESULTADOS if r["clase"] == "PROVEN"]),
           len([r for r in RESULTADOS if r["clase"] == "INSUFFICIENT"])))
    for r in RESULTADOS:
        print("  %s: %-55s esperado=%-22s observado=%s" % (r["caso"], r["nombre"][:55], r["esperado"], r["observado"]))

if __name__ == "__main__":
    main()
