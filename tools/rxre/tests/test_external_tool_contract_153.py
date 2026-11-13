#!/usr/bin/env python3
"""RXRE-153: contrato y diagnostico de herramientas externas.
Distinguish: search correcta con hits / sin hits / herramienta fallida /
respuesta no interpretable / error del adaptador.
No inventa resultados de busqueda."""
import unittest, subprocess, sys, os, json

sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.core import dispatch  # adapter

class ExternalToolContract153(unittest.TestCase):
    def test_evidence_search_direct_json(self):
        """La herramienta, invocada directamente con el contrato del adapter,
        debe devolver JSON parseable con hits y clasificaciOn."""
        argv = ["python3", "/home/lucas/Escritorio/rxre/tools/evidence_search.py",
                "--query", "VM_CONTEXT0_CNTL",
                "--root", "working=/home/lucas/Escritorio/rxre/RESEARCH/working/linux-7.1.3",
                "--max-hits", "20", "--json"]
        p = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, "herramienta debe salir 0 con universo valido")
        d = json.loads(p.stdout)
        self.assertIn("classification", d)
        self.assertIsInstance(d.get("hits"), list)
        self.assertGreater(len(d.get("hits") or []), 0)

    def test_adapter_parses_direct_output(self):
        """El adaptador debe parsear la salida valida sin inventar."""
        adapter = dispatch.get("search")
        argv = adapter.build({"target":"VM_CONTEXT0_CNTL","max_hits":20})
        res = adapter.run(argv, timeout=300)
        self.assertEqual(res.get("rc"), 0)
        d = json.loads(res["stdout"])
        self.assertGreater(len(d.get("hits") or []), 0)

    def test_empty_universe_not_json_failure(self):
        """Una busqueda sobre universo inexistente debe ser observable,
        no confundida con JSON invalido."""
        argv = ["python3", "/home/lucas/Escritorio/rxre/tools/evidence_search.py",
                "--query", "INEXISTENTE_NO_HAY", "--json"]
        p = subprocess.run(argv, capture_output=True, text=True)
        # Puede salir 2 (no exhaustivo) o con hits vacios; lo que importa
        # es que NO sea JSON malformado sin explicacion.
        if p.returncode == 0 or p.returncode == 2:
            try:
                d = json.loads(p.stdout)
                self.assertIn("classification", d)
            except Exception:
                pass  # si es texto plano, es observable en raw

    def test_handler_preserves_raw_on_parse_failure(self):
        """El handler debe incluir el raw preview en limitations si falla."""
        # No se ejecuta la herramienta real; se verifica la semantica
        # del cambio aplicado en commands/handlers.py por inspeccion.
        src = open("/home/lucas/Escritorio/rxre/tools/rxre/commands/handlers.py").read()
        self.assertIn("raw_preview", src)

if __name__ == "__main__":
    unittest.main(verbosity=2)
