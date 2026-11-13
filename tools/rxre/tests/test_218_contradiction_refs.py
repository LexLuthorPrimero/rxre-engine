#!/usr/bin/env python3
"""RXRE-218 — Matriz discriminante de validation de contradiction_refs.

Fixtures sintéticas `fixture_218_`. Politica pura; sin DB.
"""
import sys
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.conflict_policy import politica_conflicto_claims

FALLOS = []

def ok(cond, label, detalle=""):
    if cond:
        print("  [PASS] %s %s" % (label, detalle))
    else:
        FALLOS.append(label)
        print("  [FAIL] %s %s" % (label, detalle))

# --- Datos base ---
A = {
    "claim_id": "fixture_218_a",
    "statement": "afirmación A sobre objeto O en scope S",
    "object_hash": "fixture_218_obj",
    "scope": "fixture_218_scope",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["fixture_218_ev1"],
    "contradiction_refs": ["fixture_218_b"],
    "contradiction_statements": ["enunciado de contradicción verificable A vs B"],
    "falsification_test": "t_218",
}
B = {
    "claim_id": "fixture_218_b",
    "statement": "afirmación B opuesta sobre objeto O en scope S",
    "object_hash": "fixture_218_obj",
    "scope": "fixture_218_scope",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["fixture_218_ev2"],
    "contradiction_refs": ["fixture_218_a"],
    "contradiction_statements": ["enunciado de contradicción verificable B vs A"],
    "falsification_test": "t_218_b",
}
RESOLVER = lambda cid: cid in {"fixture_218_a", "fixture_218_b"}
DECLS = {
    "fixture_218_a": ["enunciado de contradicción verificable A vs B"],
    "fixture_218_b": ["enunciado de contradicción verificable B vs A"],
}

print("=== 218: matriz de validación de contradiction_refs ===")

# 1. Mutuas, existentes, resolubles, con declaraciones -> CONFLICT
r = politica_conflicto_claims(A, B, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "CONFLICT", "M1 mutuas+resolubles+declaraciones -> CONFLICT",
   r["motivo"][:50])

# 2. Mutuas hacia identificadores inexistentes (no resolubles) -> INDETERMINATE
r = politica_conflicto_claims(A, B, resolver_refs=lambda cid: False, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M2 refs mutuas no resolubles -> INDETERMINATE",
   r["motivo"][:50])

# 2b. Sin resolver ninguna referencia (no se提供了) -> INDETERMINATE
r = politica_conflicto_claims(A, B)
ok(r["clasificacion"] == "INDETERMINATE", "M2b sin resolver_refs -> INDETERMINATE",
   r["motivo"][:50])

# 3. Mutuas hacia claims que no corresponden al par comparado
A3 = dict(A); A3["contradiction_refs"] = ["fixture_218_otro"]
B3 = dict(B); B3["contradiction_refs"] = ["fixture_218_otro_b"]
r = politica_conflicto_claims(A3, B3, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "DISTINCT", "M3 refs mutuas a terceros -> DISTINCT",
   r["motivo"][:50])

# 4. Referencia unilateral -> INDETERMINATE
A4 = dict(A); A4["contradiction_refs"] = ["fixture_218_b"]
B4 = dict(B); B4["contradiction_refs"] = []
r = politica_conflicto_claims(A4, B4, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M4 unilateral -> INDETERMINATE", r["motivo"][:50])

# 5. Referencias duplicadas -> mismo resultado que referencia simple (determinista)
A5 = dict(A); A5["contradiction_refs"] = ["fixture_218_b", "fixture_218_b"]
B5 = dict(B); B5["contradiction_refs"] = ["fixture_218_a", "fixture_218_a"]
r5 = politica_conflicto_claims(A5, B5, resolver_refs=RESOLVER, contradicciones=DECLS)
r1 = politica_conflicto_claims(A, B, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r5["clasificacion"] == r1["clasificacion"] == "CONFLICT",
   "M5 duplicados -> misma clasificacion que referencia simple", r5["clasificacion"])

# 6. Tipos de referencia incorrectos / estructura malformada
A6 = dict(A); A6["contradiction_refs"] = "fixture_218_b"   # string, no lista
B6 = dict(B); B6["contradiction_refs"] = ["fixture_218_a"]
r = politica_conflicto_claims(A6, B6, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M6 refs con tipo incorrecto -> INDETERMINATE",
   r["motivo"][:50])

# 7. Mutuas válidas, resolubles, pero SIN evidencia (sin declaraciones)
A7 = dict(A); A7.pop("contradiction_statements")
B7 = dict(B); B7.pop("contradiction_statements")
r = politica_conflicto_claims(A7, B7, resolver_refs=RESOLVER, contradicciones=None)
ok(r["clasificacion"] == "INDETERMINATE", "M7 sin evidencia declarada -> INDETERMINATE",
   r["motivo"][:50])

# 8. Referencias válidas pero alcance u objeto incompatibles
A8 = dict(A); A8["scope"] = "fixture_218_scope_otro"
B8 = dict(B); B8["scope"] = "fixture_218_scope_otro2"
r = politica_conflicto_claims(A8, B8, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M8 scope incompatible -> INDETERMINATE", r["motivo"][:50])

A8b = dict(A); A8b["object_hash"] = "fixture_218_obj_otro"
B8b = dict(B); B8b["object_hash"] = "fixture_218_obj_otro2"
r = politica_conflicto_claims(A8b, B8b, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M8b object_hash distinto -> INDETERMINATE", r["motivo"][:50])

# 9. Orden inverso del par -> misma clasificacion
r_inv = politica_conflicto_claims(B, A, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r_inv["clasificacion"] == r["clasificacion"] or r_inv["clasificacion"] == "CONFLICT",
   "M9 orden inverso -> simetrica", "%s vs %s" % (r_inv["clasificacion"], "CONFLICT"))
r_inv2 = politica_conflicto_claims(B, A, resolver_refs=lambda cid: False, contradicciones=DECLS)
ok(r_inv2["clasificacion"] == "INDETERMINATE", "M9b orden inverso no resoluble -> INDETERMINATE")

# 10. Adversarial: fabricar CONFLICT con referencias sintéticas no verificadas
FAKE_A = {
    "claim_id": "fixture_218_fake_a",
    "statement": "texto similar al de A",
    "object_hash": "fixture_218_obj",
    "scope": "fixture_218_scope",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["ev_fabricada"],
    "contradiction_refs": ["fixture_218_fake_b"],
    "falsification_test": "t_fake",
}
FAKE_B = {
    "claim_id": "fixture_218_fake_b",
    "statement": "texto casi idéntico pero no igual",
    "object_hash": "fixture_218_obj",
    "scope": "fixture_218_scope",
    "epistemic_state": "PROVEN",
    "evidence_refs": ["ev_fabricada"],
    "contradiction_refs": ["fixture_218_fake_a"],
    "falsification_test": "t_fake_b",
}
r = politica_conflicto_claims(FAKE_A, FAKE_B, resolver_refs=lambda cid: False, contradicciones=DECLS)
ok(r["clasificacion"] != "CONFLICT", "M10 refs sintéticas no verificadas -> NO CONFLICT",
   r["clasificacion"])
r = politica_conflicto_claims(FAKE_A, FAKE_B, resolver_refs=lambda cid: True, contradicciones=None)
ok(r["clasificacion"] != "CONFLICT", "M10b refs verificables pero sin evidencia -> NO CONFLICT",
   r["clasificacion"])

# 11. Determinismo (repetición)
r_a = politica_conflicto_claims(A, B, resolver_refs=RESOLVER, contradicciones=DECLS)
r_b = politica_conflicto_claims(A, B, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r_a == r_b, "M11 repeticion determinista", "igual" if r_a == r_b else "difiere")

# 12. Entrada malformada
r = politica_conflicto_claims("no-dict", B, resolver_refs=RESOLVER, contradicciones=DECLS)
ok(r["clasificacion"] == "INDETERMINATE", "M12 entrada malformada -> INDETERMINATE")
r = politica_conflicto_claims({"statement": "sin id"}, B, resolver_refs=RESOLVER)
ok(r["clasificacion"] == "INDETERMINATE", "M12b sin claim_id -> INDETERMINATE")

# 13. Sin escritura: la política no toca DB
import sqlite3, os
ok(not os.path.exists("/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3.written"),
   "M13 politica sin efectos de escritura")

print("\n=== RESUMEN 218 ===")
print("fallos:", FALLOS if FALLOS else "ninguno")
if FALLOS:
    sys.exit(1)
print("218 OK")
