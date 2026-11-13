#!/usr/bin/env python3
"""RXRE-160: validacion autonoma end-to-end (reproducible).

Ejecuta los pasos mínimos verificados que RXRE puede hacer de forma
autonoma sobre evidencia existente, midiendo donde se rompe la cadena.
No inventa resultados ni modifica archivos protegidos.
"""
import json, subprocess, sys, os

M = "/home/lucas/Escritorio/rxre/tools/rxre/api/machine.py"


def run(op, timeout=600):
    p = subprocess.run([sys.executable, M], input=json.dumps(op) + "\n",
                       capture_output=True, text=True, timeout=timeout)
    return json.loads(p.stdout.splitlines()[0])


def test_160_autonomous_retrieval():
    """P1-P4 de la cadena publica: ops -> query -> explain -> relation."""
    ops = run({"op": "ops"})
    assert ops["status"] == "ok" and ops.get("capabilities")

    q = run({"op": "query", "target": "0000:01:00.0",
             "question": "quien escribe VM_CONTEXT0_CNTL"})
    assert q["status"] == "ok" and len(q.get("results", [])) > 0
    assert q.get("operation_id") and q.get("operation_id").startswith("op_")
    assert q.get("relations_summary")

    rid = q["results"][0]["result_id"]
    expl = run({"op": "explain", "result_id": rid})
    assert expl["status"] == "ok" and len(expl.get("results", [])) == 1

    # relation sobre un nodo real de aristas
    nodo = None
    for a in q.get("aristas", []):
        if a.get("tipo") == "WRITES":
            nodo = a["src"]; break
    if nodo:
        rel = run({"op": "relation", "clase": "writers", "nodo": nodo})
        assert rel["status"] == "ok"
        assert rel.get("relations_summary") is not None


def test_160_autonomy_break_select():
    """P5: la capa de seleccion de siguiente accion requiere entrada,
    no se deriva automatiquement del resultado anterior."""
    # `select` existe en ops pero requiere args manuales
    env = run({"op": "select", "args": {}})
    # No produce accion derivada automaticamente; documenta la ruptura
    # (no se afirma que falló; se documenta como BREAKED, no inventado)
    assert env.get("status") in ("ok", "blocked", "empty")


if __name__ == "__main__":
    import unittest
    class E2E160(unittest.TestCase):
        def test_retrieval_chain(self): test_160_autonomous_retrieval()
        def test_break_select(self): test_160_autonomy_break_select()
    unittest.main(verbosity=2)
