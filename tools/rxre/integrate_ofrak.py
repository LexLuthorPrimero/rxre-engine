#!/usr/bin/env python3
"""RXRE-M340 — Integración OFRAK (repo no encontrado localmente)"""
import sys, os, json, hashlib, time
ROOT = "/home/lucas/Escritorio/rxre"

class OFRAKIntegrator:
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
            'tool':'ofrak','version':'repo-not-present','artifact':self.artifact_path,
            'sha256':self._hash(self.artifact_path),
            'findings':[],
            'observations':[],
            'interpretations':[],
            'limitations':['repositorio OFRAK no clonado localmente; instalación requiere revisión de licencias/dependencias'],
            'provenance':{'tool':'ofrak','timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},
            'status':'BLOCKED'
        }
        return res

if __name__=='__main__':
    o=OFRAKIntegrator(sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls')
    print(json.dumps(o.analyze(), indent=2))
