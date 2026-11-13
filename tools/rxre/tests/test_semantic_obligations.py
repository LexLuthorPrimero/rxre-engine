#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from rxre.semantic import semantic_obligations

PROOF = """(set-logic BV)
(set-option :produce-models true)
; 32-bit bit-vector obligation:
; exists x in BV32 such that x * 256 mod 2^32 != x << 8
(declare-const x (_ BitVec 32))
(assert (not (= (bvmul x (_ bv256 32))
                (bvshl x (_ bv8 32)))))
(check-sat)
"""

CONTROL = """(set-logic BV)
(set-option :produce-models true)
(declare-const x (_ BitVec 32))
(assert (not (= (bvmul x (_ bv256 32))
                (bvmul x (_ bv25 32)))))
(check-sat)
(get-model)
"""


def test_identifies_expected_obligations(tmp_path):
    proof = tmp_path / 'proof.smt2'
    control = tmp_path / 'control.smt2'
    proof.write_text(PROOF, encoding='utf-8')
    control.write_text(CONTROL, encoding='utf-8')

    proof_info = semantic_obligations.inspect_formula(str(proof))
    assert proof_info['obligation_id'] == 'proof_xmul256_shl8'
    assert proof_info['expected_solver_result'] == 'unsat'
    assert proof_info['structure_errors'] == []

    control_info = semantic_obligations.inspect_formula(str(control))
    assert control_info['obligation_id'] == 'counterexample_xmul256_vs_xmul25'
    assert control_info['expected_solver_result'] == 'sat'
    assert control_info['structure_errors'] == []


def test_rejects_vacuous_or_wrong_width_extreme_obligations(tmp_path):
    vacuous = tmp_path / 'vacuous.smt2'
    wrong_width = tmp_path / 'wrong_width.smt2'
    vacuous.write_text('(set-logic BV)\n(assert false)\n(check-sat)\n', encoding='utf-8')
    wrong_width.write_text(PROOF.replace('BitVec 32', 'BitVec 64').replace('bv256 32', 'bv256 64').replace('bv8 32', 'bv8 64'), encoding='utf-8')

    assert semantic_obligations.inspect_formula(str(vacuous))['obligation_id'] is None
    assert semantic_obligations.inspect_formula(str(wrong_width))['obligation_id'] is None
