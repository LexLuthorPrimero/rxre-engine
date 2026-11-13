#!/usr/bin/env python3
"""RXRE-154: contrato / carga de search y _load.
Distinguish: funciona / no interpretable / vacio genuino."""
import unittest, sys, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools/rxre")
from commands.handlers import _load

class SearchLoad154(unittest.TestCase):
    def test_handler_search_ok(self):
        from commands import handlers as _H
        env, rc = _H.HANDLERS["search"]({"target":"VM_CONTEXT0_CNTL","max_hits":1,"timeout":300,"probe_timeout":60})
        self.assertEqual(rc, 0, "search debe salir 0 con recurso presente")
        self.assertEqual(env.get("status"), "ok")
        self.assertGreaterEqual(len(env.get("results") or []), 1)

    def test_load_json_valid(self):
        d = _load('{"hits":[],"query":"t"}', "")
        self.assertIsNotNone(d)
        self.assertEqual(d["query"], "t")

    def test_load_empty_string_is_none(self):
        self.assertIsNone(_load("", ""))

if __name__ == "__main__":
    unittest.main(verbosity=2)
