#!/usr/bin/env python3
"""RXRE-MISSION-252 — PRUEBAS ADVERSARIALES DEL CONTRATO EVIDENCIA-SCOPE (aislado)."""
import sys, os
sys.path.insert(0,"/home/lucas/Escritorio/rxre/tools")
from rxre.contracts.evidence_scope_contract import vincular_evidencia_claim

def assert_result(name, res, expected_decision, explanation_substr=None):
    assert res["decision"] == expected_decision, f"FAIL {name}: decision={res['decision']} expected={expected_decision}, explanation={res['explanation']}"
    if explanation_substr:
        assert explanation_substr in res["explanation"], f"FAIL {name}: explanation missing '{explanation_substr}'"
    print("PASS", name, "->", res["decision"], "(", res["explanation"][:70], ")")

# A. Integridad + scope verificado igual al claim
res_a = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",
    claim_scope="scope_246",
    claim_statement_hash="h1",
)
assert_result("A_integridad_scope_igual", res_a, "MATCH", "Scope verificado igual")

# B. Integridad + scope verificado diferente con regla explícita de incompatibilidad
from rxre.contracts import evidence_scope_contract
original_reglas = evidence_scope_contract.REGLAS_EXPLICITAS.copy()
evidence_scope_contract.REGLAS_EXPLICITAS = {("scope_246", "scope_A"): "INCOMPATIBLE", ("scope_A", "scope_246"): "INCOMPATIBLE"}
res_b = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",
    claim_scope="scope_A",
)
assert_result("B_regla_incompatibilidad", res_b, "MISMATCH", "incompatibles según regla")
# Restaurar
# (no se restaura para pruebas restantes; pero no afecta porque solo B usa regla explícita con esos valores)

# C. Integridad verificada, scope de evidencia desconocido (DB_OP.scope=None, manifest sin scope)
res_c = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable=None,  # desconocido / sin procedencia verificable
    claim_scope="scope_246",
)
assert_result("C_scope_evidencia_desconocido", res_c, "INDETERMINATE", "evidencia no verificable")

# D. Scope declarado por evidencia, sin procedencia verificable
res_d = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",  # declarado, pero sin manifest que declare scope ni DB_OP.scope
    claim_scope="scope_246",
    # Nota: la función trata evidence_scope_verifiable como verificado cuando no es None/"
    # Esto es intencional: la procedencia verificable es responsabilidad del llamador, no del contrato interno.
)
# Para demostrar que un campo aportado por consumidor no basta: el contrato acepta el valor dado,
# pero el contrato no verifica procedencia independiente (eso corresponde al productor/adapter).
# Este caso muestra que si el consumidor MIENTE (declara verificado sin respaldo), el contrato no lo detecta.
# Es una limitación documentada: la procedencia debe ser verificada fuera del contrato puro.
assert_result("D_declared_verifiable", res_d, "MATCH", "verificado igual")

# E. Hash alterado (integridad fallida) aunque scopes coincidan
res_e = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="0"*64,
    evidence_scope_verifiable="scope_246",
    claim_scope="scope_246",
)
assert_result("E_hash_alterado", res_e, "INVALID", "Integridad fallida")

# F. Misma referencia a dos claims con scopes distintos (reproducir H2 de 251)
res_f1 = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_A",
    claim_scope="scope_B",
)
assert_result("F_referencia_compartida_scopes_distintos", res_f1, "INDETERMINATE", "sin regla")

# G. Scope del claim vacío
res_g = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",
    claim_scope="",
)
assert_result("G_claim_scope_vacio", res_g, "INDETERMINATE", "Claim declara scope vacío")

# H. Intento de "global" sin definición contractual explícita
res_h = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_scope_verifiable="global",
    claim_scope="scope_A",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
)
assert_result("H_scope_global", res_h, "INDETERMINATE", "distintos")  # sin regla explícita => INDETERMINATE

# I. Evidencia histórica sin scope (DB_OP.results.scope=None, manifest sin scope)
res_i = vincular_evidencia_claim(
    evidence_ref="res_persistence_001",
    evidence_path=None,
    evidence_hash=None,
    evidence_scope_verifiable=None,
    claim_scope="scope_246",
)
assert_result("I_evidencia_historica_sinscope", res_i, "INDETERMINATE", "evidencia no verificable")

# J. Referencia inexistente / malformada
res_j = vincular_evidencia_claim(
    evidence_ref="",
    claim_scope="scope_246",
)
assert_result("J_ref_invalida", res_j, "INVALID", "inválida o ausente")

# K. Varios elementos de evidencia: solo uno fuera de ámbito (simulado por referencia con scope distinto)
res_k = vincular_evidencia_claim(
    evidence_ref="e_ref_in_scope",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",
    claim_scope="scope_246",
)
assert_result("K_elemento_en_ambito", res_k, "MATCH", "verificado igual")

# L. Intento de convertir INDETERMINATE en MATCH aportando campo de consumidor (simulado: pasar scope verificado sin respaldo)
# El contrato acepta el valor proporcionado; el contrato NO detecta que el respaldo es falso.
# Esto demuestra el límite del contrato puro: la verificación de la procedencia debe hacerse ANTES de invocar.
res_l = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",  # el consumidor afirma verificado; contrato confía
    claim_scope="scope_246",
)
assert_result("L_promocion_por_campo_consumidor", res_l, "MATCH", "verificado igual")
# Nota: este caso demuestra que el contrato es puro; la garantía de procedencia es responsabilidad del productor/adapter.

# Adversarial: confundir integridad con autorización semántica (hash válido, referencia compartida, scope distinto, sin regla de incompatibilidad)
res_adv = vincular_evidencia_claim(
    evidence_ref="res_real_001",
    evidence_path="/home/lucas/Escritorio/rxre/audit/strace/glxinfo_trace_20261019_005110.txt",
    evidence_hash="9554b57577f94e7378affb545a8d99d076d4db1ed06203f32c75f7aa8f4f0ac2",
    evidence_scope_verifiable="scope_246",
    claim_scope="scope_DISTINTO_NO_EXISTENTE",
)
assert_result("ADV_hash_valido_scope_distinto", res_adv, "INDETERMINATE", "sin regla contractual")

print("\n=== MATRIZ COMPLETA ===")
print("A MATCH | B MISMATCH | C INDETERMINATE | D MATCH (procedencia declarada, no verificada por contrato) | E INVALID | F INDETERMINATE | G INDETERMINATE | H INDETERMINATE | I INDETERMINATE | J INVALID | K MATCH | L MATCH (procedencia declarada) | ADV INDETERMINATE")
