#!/usr/bin/env python3
"""RXRE-M340 — Integración REA (mínima, funcional)"""
import sys, os, json, hashlib, time
ROOT = "/home/lucas/Escritorio/rxre"
REA = os.path.join(ROOT, "tools/rxre/github/rea")

class REAIntegrator:
    def __init__(self, artifact_path=None):
        self.artifact_path = artifact_path
    
    def _hash(self,p):
        h=hashlib.sha256()
        with open(p,'rb') as f:
            for c in iter(lambda:f.read(1024*1024),b''): h.update(c)
        return h.hexdigest()
    
    def analyze(self):
        if not self.artifact_path or not os.path.exists(self.artifact_path):
            return {'status':'BLOCKED','reason':'artefacto ausente'}
        res = {
            'tool':'rea','version':'repo-present','artifact':self.artifact_path,
            'sha256':self._hash(self.artifact_path),
            'findings':[],
            'observations':['REA repo presente en tools/rxre/github/rea'],
            'interpretations':[],
            'limitations':['integración mínima; requiere análisis asistido con scripts REA según caso'],
            'provenance':{'tool':'rea','timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},
            'status':'PARTIAL'
        }
        # explorar estructura útil
        if os.path.exists(os.path.join(REA,'bridge')):
            res['observations'].append('rea/bridge presente')
        if os.path.exists(os.path.join(REA,'experiments')):
            res['observations'].append('rea/experiments presente')
        return res

if __name__=='__main__':
    r=REAIntegrator(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls')
    print(json.dumps(r.analyze(), indent=2))
