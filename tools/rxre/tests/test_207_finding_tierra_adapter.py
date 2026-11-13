#!/usr/bin/env python3
"""RXRE-207 — Prueba aislada del adaptador finding -> TIERRA.
Base /tmp, fixtures sintéticos identificados, sin tocar zonas protegidas.
"""
import sqlite3, tempfile, os, sys, shutil, json
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.adapters.adapter_finding_tierra import convertir_finding_a_tierra, ejecutar_adaptador, AdapterError, claim_id_de
from rxre.arquitectura import TIERRA

TMP = tempfile.mkdtemp(prefix="rxre207_")
DB = os.path.join(TMP, "tierra_207.sqlite3")
FAILURES = []

def v(name, cond, detail=""):
    if cond:
        print("PASS", name)
    else:
        print("FAIL", name, "::", detail)
        FAILURES.append(name)

# --- Fixture resolver (simula verificación de referencias existentes) ---
VALID_REFS = {"res_207_e1", "res_207_e2", "res_207_bad"}

def resolver(r):
    return r in VALID_REFS

# --- Setup grafo aislado ---
g = TIERRA.Grafo(DB)

# ===================================================================
# CASO 1: Conversión válida con evidencia existente (PROVEN)
# ===================================================================
find1 = {
    "finding_id": "finding_207_f1",
    "claim": "El acceso al nodo DRM renderD128 confirma la operacion de la RX 550",
    "epistemic": "PROVEN",
    "object_hash": "sha256:aabbccddeeff00112233445566778899aabbccddeeff00112233445566778899",
    "scope": "rx550_drm_access",
    "falsification_test": "romper el acceso y verificar que el nodo no aparece tras desactivar driver",
    "evidence_ids": ["res_207_e1", "res_207_e2"],
    "derivation_refs": ["deriv_207_1"],
    "contradiction_refs": [],
    "limitations": ["no se afirma ejecucion interna sin UMR"],
    "provenance": {"producer": "adapter_207_fixtures", "version": "v1.0", "date": "2026-10-21"},
}
res1 = ejecutar_adaptador(g, find1, resolver_refs=resolver, autorizacion=True)
claim1 = res1["claim_id"]
v("1a_claim_creado", res1["estado"] == "ok" and claim1.startswith("clm_"), res1)
# Lectura real de TIERRA
cl = g.leer(claim1)
v("1b_claim_leido", cl is not None and cl["epistemic_state"] == "PROVEN", cl["epistemic_state"] if cl else None)
# Evidencia verificada (hash)
ev_ids = cl.get("evidence_refs") or []
v("1c_evidencia_presente", len(ev_ids) >= 2, str(len(ev_ids)))
for ev in ev_ids:
    fila = g.leer_evidencia(ev, verificar=True)
    v("1d_hash_verificado_%s" % ev[:6], fila.get("hash_verificado") is True, fila.get("hash_verificado"))
# Procedencia conservada dentro de la evidencia de tipo observation
obs_ev = g.db.execute("SELECT evidence_id FROM evidence WHERE claim_id=? AND kind='observation'", (claim1,)).fetchone()
v("1e_observacion_evidencia", obs_ev is not None, obs_ev)

# ===================================================================
# CASO 2: Referencia inexistente -> rechazo explícito
# ===================================================================
find_bad = dict(find1, finding_id="finding_207_bad")
find_bad["evidence_ids"] = ["res_207_bad", "res_inexistente_999"]
try:
    ejecutar_adaptador(g, find_bad, resolver_refs=resolver, autorizacion=True)
    v("2_referencia_inexistente_rechazada", False, "deberia haber fallado")
except AdapterError as e:
    v("2_referencia_inexistente_rechazada", "res_inexistente_999" in str(e) or "inexistente" in str(e).lower(), str(e))

# ===================================================================
# CASO 3: Rechazo de campo obligatorio ausente (falsification_test)
# ===================================================================
for missing_key in ("falsification_test", "object_hash", "scope"):
    f_bad = dict(find1, finding_id="finding_207_%s" % missing_key)
    f_bad[missing_key] = None
    try:
        ejecutar_adaptador(g, f_bad, resolver_refs=resolver, autorizacion=True)
        v("3_%s_ausente_rechazado" % missing_key, False, "no rechazo")
    except AdapterError as e:
        reason_ok = missing_key in str(e) or "falta" in str(e)
        v("3_%s_ausente_rechazado" % missing_key, reason_ok, str(e))

# ===================================================================
# CASO 4: PROVEN_ABSENT conservado (sin elevación artificial)
# ===================================================================
find_abs = dict(find1, finding_id="finding_207_abs",
                    claim="Observacion contradictoria: acceso al nodo DRM sin confirmacion de ejecucion interna",
                    epistemic="PROVEN_ABSENT", evidence_ids=[])
res_abs = ejecutar_adaptador(g, find_abs, resolver_refs=resolver, autorizacion=True)
cl_abs = g.leer(res_abs["claim_id"])
v("4a_proven_absent_conservado", cl_abs is not None and cl_abs["epistemic_state"] == "PROVEN_ABSENT", cl_abs.get("epistemic_state") if cl_abs else None)
# PROVEN_ABSENT no requiere refs; pero si los hay no debe elevar a PROVEN
find_abs2 = dict(find_abs, finding_id="finding_207_abs2", evidence_ids=["res_207_e1"])
res_abs2 = ejecutar_adaptador(g, find_abs2, resolver_refs=resolver, autorizacion=True)
cl_abs2 = g.leer(res_abs2["claim_id"])
v("4b_proven_absent_no_elevado", cl_abs2["epistemic_state"] == "PROVEN_ABSENT", cl_abs2.get("epistemic_state"))

# ===================================================================
# CASO 5: PARTIAL con refs no se convierte en PROVEN
# ===================================================================
find_partial = dict(find1, finding_id="finding_207_p", claim="Observacion parcial del acceso DRM (caso 5)", scope="rx550_c5", epistemic="PARTIAL",
                    evidence_ids=["res_207_e1"], falsification_test="test_fals")
res_p = ejecutar_adaptador(g, find_partial, resolver_refs=resolver, autorizacion=True)
cl_p = g.leer(res_p["claim_id"])
v("5_partial_no_elevado", cl_p["epistemic_state"] == "PARTIAL", cl_p.get("epistemic_state"))

# ===================================================================
# CASO 6: Procedencia e identidad del hallazgo original preservada
# ===================================================================
# El hallazgo original tiene finding_id y provenance; la evidencia de
# tipo 'observation' debe contenerlos.
ob_id = g.db.execute("SELECT evidence_id FROM evidence WHERE claim_id=? AND kind='observation'", (claim1,)).fetchone()[0]
ev_obs = g.leer_evidencia(ob_id, verificar=True)
payload = json.loads(ev_obs["payload"]) if isinstance(ev_obs["payload"], str) else ev_obs.get("payload", {})
# El payload es canonizado; recuperamos de la fila
v("6a_procedencia_preservada", payload.get("rxre_finding_id") == "finding_207_f1", payload.get("rxre_finding_id"))
# Identidad: claim_id determinista; repetir produce MISMO id (idempotencia)
res_repeat = ejecutar_adaptador(g, find1, resolver_refs=resolver, autorizacion=True)
v("6b_idempotencia_mismo_id", res_repeat["estado"] == "ya_existia" and res_repeat["claim_id"] == claim1, res_repeat)

# ===================================================================
# CASO 7: Contradicción tiene que ser aportada explícitamente
# ===================================================================
find_ctr = dict(find1, finding_id="finding_207_ctr", claim="Contradiccion intencional en acceso DRM (caso 7)", scope="rx550_c7", contradiction_refs=["ctr_001"])
try:
    ejecutar_adaptador(g, find_ctr, resolver_refs=resolver, autorizacion=True)
    v("7_contradicion_sin_statement_rechazado", False, "deberia fallar")
except AdapterError as e:
    v("7_contradicion_sin_statement_rechazado", "statement" in str(e).lower() or "contradiccion" in str(e).lower(), str(e))
# Ahora con statement explicito
find_ctr_ok = dict(find_ctr, contradiction_statements=[{"statement":"Contradiccion: el acceso es solo lectura, no escritura", "severity":"alta"}])
res_ctr = ejecutar_adaptador(g, find_ctr_ok, resolver_refs=resolver,
                          contradiction_statements=[{"statement":"Contradiccion: acceso no confirma ejecucion interna", "severity":"media"}], autorizacion=True)
# Verificar que la contradicción quedó registrada y el claim la referencia
contrad_rows = g.db.execute("SELECT contradiction_id FROM contradictions WHERE claim_id=?", (res_ctr["claim_id"],)).fetchall()
v("7b_contradicion_registrada", len(contrad_rows) >= 1, str(len(contrad_rows)))

# ===================================================================
# CASO 8: Fallo transaccional sin registros parciales (real)
# ===================================================================
# Se fuerza un fallo DENTRO de la transaccion: dos contradicciones con el
# mismo enunciado producen el mismo `contradiction_id` -> violacion de PK
# -> excepcion -> ROLLBACK. Debe quedar CERO rastro del claim.
find_fail = dict(find1, finding_id="finding_207_fail",
                 claim="Claim con fallo transaccional (caso 8)", scope="rx550_c8",
                 contradiction_refs=["ctr_008"],
                 evidence_ids=["res_207_e1"])
cid_esperado = claim_id_de(find_fail["claim"], find_fail["object_hash"],
                            find_fail["scope"])
try:
    ejecutar_adaptador(g, find_fail, resolver_refs=resolver,
                       contradiction_statements=[
                           {"statement": "misma contradiccion duplicada", "severity": "media"},
                           {"statement": "misma contradiccion duplicada", "severity": "media"}], autorizacion=True)
    v("8a_fallo_transaccional_ocurre", False, "deberia haber fallado")
except Exception as e:
    v("8a_fallo_transaccional_ocurre", True, type(e).__name__)
v("8b_sin_claim_parcial", g.leer(cid_esperado) is None,
  "quedo un claim parcial: %r" % (g.leer(cid_esperado),))
ev_left = g.db.execute("SELECT count(*) FROM evidence WHERE claim_id=?", (cid_esperado,)).fetchone()[0]
v("8c_sin_evidencia_parcial", ev_left == 0, "evidencias huerfanas: %d" % ev_left)
ctr_left = g.db.execute("SELECT count(*) FROM contradictions WHERE claim_id=?", (cid_esperado,)).fetchone()[0]
v("8d_sin_contradiccion_parcial", ctr_left == 0, "contradicciones huerfanas: %d" % ctr_left)
# El resto del grafo sigue intacto (el fallo no arrastro otros claims)
v("8e_claims_previos_intactos", g.leer(claim1) is not None and g.leer(claim1)["epistemic_state"] == "PROVEN",
  str(g.leer(claim1)))

# ===================================================================
# CASO 9: Consulta posterior reconstruye afirmacion + evidencia
# ===================================================================
# Ya verificado en 1b/1c; añadimos reconstrucción completa
reconstruido = {
    "claim": g.leer(claim1),
    "evidencia_ids": g.leer(claim1).get("evidence_refs") if g.leer(claim1) else [],
    "observacion_evidencia": g.db.execute("SELECT evidence_id FROM evidence WHERE claim_id=? AND kind='observation'", (claim1,)).fetchone(),
}
v("9a_reconstruccion_completa", reconstruido["claim"] is not None,
  "claim=%s evidencia=%d obs=%r" % (reconstruido["claim"]["id"] if reconstruido["claim"] else None,
                                   len(reconstruido["evidencia_ids"]), reconstruido["observacion_evidencia"]))

# ===================================================================
# Limpieza temporal
# ===================================================================
shutil.rmtree(TMP, ignore_errors=True)

print("\n=== RESULTADO 207 ===")
print("PASS" if not FAILURES else "FAILURES -> %s" % FAILURES)
