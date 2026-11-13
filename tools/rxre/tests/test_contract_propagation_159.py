#!/usr/bin/env python3
"""RXRE-159: propagacion del contrato publico en api/machine.py.

Verifica que la superficie publica conserve los campos autenticos que las
capas internas producen:
  - `ops` declara `capabilities` (catalogo real, no inventado);
  - `query` expone `operation_id` real y `relations_summary` real;
  - `relation` expone `relations_summary` coherente con sus resultados;
  - los casos vacios y de error mantienen su semantica (no se rellenan).

No depende de bases personales: usa la base por defecto del paquete
(tools/rxre/storage/), igual que la superficie publica.
"""
import json
import os
import subprocess
import sys
import unittest

MACHINE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "api", "machine.py")


def run(op):
    p = subprocess.run([sys.executable, MACHINE], input=json.dumps(op) + "\n",
                       capture_output=True, text=True, timeout=600)
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    assert lines, "machine no devolvio respuesta para %r" % (op,)
    return json.loads(lines[0])


class Propagacion159(unittest.TestCase):
    def test_ops_declara_capabilities_reales(self):
        env = run({"op": "ops"})
        self.assertEqual(env.get("status"), "ok")
        self.assertTrue(env.get("capabilities"),
                        "ops debe declarar las capacidades disponibles")
        self.assertIsInstance(env.get("capabilities"), list)
        self.assertTrue(env.get("results"), "ops debe listar operaciones")

    def test_query_expone_operation_id_real(self):
        env = run({"op": "query", "target": "0000:01:00.0",
                   "question": "quien escribe VM_CONTEXT0_CNTL"})
        self.assertEqual(env.get("status"), "ok")
        oid = env.get("operation_id")
        self.assertTrue(oid, "query debe exponer operation_id consultable")
        self.assertIsInstance(oid, str)

    def test_query_expone_relations_summary_real(self):
        env = run({"op": "query", "target": "0000:01:00.0",
                   "question": "quien escribe VM_CONTEXT0_CNTL"})
        rs = env.get("relations_summary")
        self.assertIsInstance(rs, dict, "query debe exponer relations_summary")
        self.assertIn("WRITES", rs)

    def test_relation_coherente_con_sus_resultados(self):
        env = run({"op": "query", "target": "0000:01:00.0",
                   "question": "quien escribe VM_CONTEXT0_CNTL"})
        nodo = None
        for a in env.get("aristas", []) or []:
            if a.get("tipo") == "WRITES":
                nodo = a.get("src")
                break
        if nodo is None:
            self.skipTest("la consulta no produjo aristas WRITES en este entorno")
        rel = run({"op": "relation", "clase": "writers", "nodo": nodo})
        self.assertEqual(rel.get("status"), "ok")
        rs = rel.get("relations_summary")
        self.assertIsInstance(rs, dict)
        self.assertEqual(rs.get("WRITES"), len(rel.get("results") or []))

    def test_relation_vacio_no_se_rellena(self):
        rel = run({"op": "relation", "clase": "writers",
                   "nodo": "NODO_QUE_NO_EXISTE_99999"})
        self.assertEqual(rel.get("status"), "empty")
        self.assertEqual(rel.get("results"), [])
        self.assertEqual((rel.get("relations_summary") or {}).get("WRITES"), 0)

    def test_explain_ok_y_empty_conservan_contrato(self):
        # Control de regresion: el contrato `results` no se altera.
        env = run({"op": "query", "target": "0000:01:00.0",
                   "question": "quien escribe VM_CONTEXT0_CNTL"})
        rid = (env.get("results") or [{}])[0].get("result_id")
        if not rid:
            self.skipTest("sin resultados para explicar")
        e = run({"op": "explain", "result_id": rid})
        self.assertEqual(e.get("status"), "ok")
        self.assertTrue(e.get("results"))
        e2 = run({"op": "explain", "result_id": "res_no_existe_000"})
        self.assertEqual(e2.get("status"), "empty")
        self.assertEqual(e2.get("results"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
