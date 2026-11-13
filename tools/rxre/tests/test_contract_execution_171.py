#!/usr/bin/env python3
"""RXRE 171: contrato público execution (evidencia de ejecución)."""
import unittest, sys, json, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools/rxre")
import core.store as s
from api import machine

class TestExecutionContract171(unittest.TestCase):
    def test_op_execution_exists_in_handler(self):
        self.assertIn("execution", machine.HANDLERS)

    def test_execution_query_returns_events_not_fabricated(self):
        res = machine.HANDLERS["execution"]({"op":"execution","limit":3})
        self.assertIn(res["status"], ["ok", "blocked", "empty"])
        if res["status"] == "ok":
            self.assertTrue(len(res.get("events", [])) <= int(res.get("filters_applied",{}).get("limit", 10)))
            for ev in res.get("events", []):
                self.assertEqual(ev.get("physical_device_execution"), "NOT_DETERMINED")
                self.assertIn("API_CALL_OBSERVED", ev.get("niveles_observados", []))
                # artifact_sha256: ausente (None) o VERIFICADO explicitamente via provenance
                # de la ingesta publica (174). Nunca inferido: si esta presente, es
                # un sha256 de 64 hex (evidencia explicita del ingest).
                sha = ev.get("artifact_sha256")
                if sha is not None:
                    self.assertRegex(sha, r"^[0-9a-f]{64}$")
                    self.assertTrue(ev.get("provenance_detail"), "hash sin provenance explicita")

    def test_empty_for_nonexistent_event_id(self):
        res = machine.HANDLERS["execution"]({"op":"execution", "event_id":"fake_171_99999", "limit":1})
        self.assertEqual(res["status"], "empty")
        self.assertEqual(res["count"], 0)

    def test_execution_filter_by_trace(self):
        res = machine.HANDLERS["execution"]({"op":"execution", "execution_id":"rx-170-repl", "limit":2})
        # Puede ser ok si existe, empty si no (según DB)
        self.assertIn(res["status"], ["ok", "empty", "blocked"])
        for ev in res.get("events", []):
            self.assertTrue(ev.get("execution_id") == "rx-170-repl" or ev.get("execution_id") == "rx-170-repl")

if __name__ == "__main__":
    unittest.main(verbosity=2)
