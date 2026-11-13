#!/usr/bin/env python3
"""RXRE-M339 — Transacción FUEGO (aislada, reversible). Requiere provisión legítima."""
import sys, os, json, hashlib, tempfile, shutil, time
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
import m326_auth_verifier as av

class FuegoTransaction:
    def __init__(self, artifact_path=None, allow=False):
        self.artifact_path = artifact_path
        self.allow = allow
    
    def _hash(self,p):
        h=hashlib.sha256()
        with open(p,'rb') as f:
            for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
        return h.hexdigest()
    
    def run(self):
        if not self.allow:
            return {'status':'BLOCKED','reason':'allow=False'}
        if not os.path.exists('/tmp/rxre_auth_provisioned/identities.json') or not os.path.exists('/tmp/rxre_306_work/servicio.key'):
            return {'status':'BLOCKED','reason':'provisión persistente ausente'}
        if not self.artifact_path or not os.path.exists(self.artifact_path):
            return {'status':'BLOCKED','reason':'artefacto ausente'}
        if self.artifact_path.startswith('/usr/') or self.artifact_path.startswith('/bin/') or self.artifact_path.startswith('/sbin/'):
            return {'status':'BLOCKED','reason':'artefacto sistema no permitido'}
        WORK=tempfile.mkdtemp(prefix='m339_fuego_',dir='/tmp')
        copy_path=os.path.join(WORK,os.path.basename(self.artifact_path)+'.copy')
        shutil.copy2(self.artifact_path,copy_path)
        h0=self._hash(copy_path)
        try:
            with open(copy_path,'rb') as f:
                data=f.read()
            if data[:4]==b'\x7fELF':
                shutil.rmtree(WORK)
                return {'status':'BLOCKED','reason':'binario no permitido sin mecanismo específico','h0':h0}
            # cambio mínimo seguro solo si texto pequeño
            shutil.rmtree(WORK)
            return {'status':'NOT_EXECUTED','reason':'sin cambio seguro aplicable','h0':h0}
        except Exception as e:
            try: shutil.rmtree(WORK)
            except: pass
            return {'status':'BLOCKED','reason':str(e)}

if __name__=='__main__':
    ft=FuegoTransaction(sys.argv[1] if len(sys.argv)>1 else '/tmp/nonexistent', allow=False)
    print(json.dumps(ft.run(), indent=2))
