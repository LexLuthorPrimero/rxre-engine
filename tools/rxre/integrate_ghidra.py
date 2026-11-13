#!/usr/bin/env python3
"""RXRE-M339 — Integración Ghidra headless (mínima, aislada)."""
import sys, os, json, hashlib, tempfile, subprocess, time
from pathlib import Path

ROOT = "/home/lucas/Escritorio/rxre"

class GhidraIntegrator:
    def __init__(self, artifact_path=None):
        self.artifact_path = artifact_path
        self.ghidra = '/usr/bin/ghidra'
    
    def _hash(self, p):
        h = hashlib.sha256()
        with open(p,'rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    
    def analyze(self):
        if not self.artifact_path or not os.path.exists(self.artifact_path):
            return {'status': 'BLOCKED', 'reason': 'artefacto ausente'}
        res = {
            'tool': 'ghidra',
            'version': 'available',
            'artifact': self.artifact_path,
            'sha256': self._hash(self.artifact_path),
            'commands': [],
            'findings': [],
            'observations': [],
            'interpretations': [],
            'limitations': ['análisis headless no ejecutado automáticamente', 'requiere proyecto/análisis específico'],
            'provenance': {'tool': 'ghidra', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        }
        # Verificar que ghidra está disponible
        if not os.path.exists(self.ghidra):
            res['status'] = 'BLOCKED'
            res['reason'] = 'ghidra no encontrado'
            return res
        res['status'] = 'PARTIAL'
        res['observations'].append(f'ghidra disponible en {self.ghidra}')
        res['observations'].append('análisis estructural básico pendiente de script headless')
        return res

if __name__ == '__main__':
    gi = GhidraIntegrator(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls')
    print(json.dumps(gi.analyze(), indent=2))
