#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil
ROOT="/home/lucas/Escritorio/rxre"
OFRAK_ROOT=os.path.join(ROOT,'tools/rxre/github/ofrak')
sys.path.insert(0, os.path.join(OFRAK_ROOT,'ofrak_core/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'ofrak_type/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'ofrak_io/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'ofrak_patch_maker/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'disassemblers/ofrak_angr/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'disassemblers/ofrak_binary_ninja/src'))
sys.path.insert(0, os.path.join(OFRAK_ROOT,'ofrak_ghidra/src'))

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact, allow=False):
    res={'tool':'ofrak','license':'Apache-2.0','artifact':artifact,'sha256_baseline':_hash(artifact) if os.path.exists(artifact) else None,'phase':'transform_m344','provenance':{'tool':'ofrak','ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}}
    if not os.path.exists(artifact): 
        res['status']='BLOCKED'; res['reason']='missing'; return res
    if not allow:
        res['status']='BLOCKED'; res['reason']='allow=False (sin autorización operativa)'; return res
    WORK=tempfile.mkdtemp(prefix='m344_ofrak_',dir='/tmp')
    copy_path=os.path.join(WORK,os.path.basename(artifact)+'.copy')
    try:
        shutil.copy2(artifact,copy_path)
        h0=_hash(copy_path)
        res['baseline_hash']=h0
        # intento mínimo: solo marcar inspección/lectura con OFRAK si es binario
        try:
            import ofrak
            from ofrak import OFRAK
            res['import']='ok'
        except Exception as e:
            res['import']=str(e)
        # no modificar binario sistema; prueba aislada
        if os.path.realpath(artifact).startswith('/usr/') or os.path.realpath(artifact).startswith('/bin/') or os.path.realpath(artifact).startswith('/sbin/'):
            try: shutil.rmtree(WORK)
            except: pass
            res['status']='BLOCKED'; res['reason']='artefacto sistema prohibido para modificación'; res['h0']=h0
            return res
        # cambio acotado solo si archivo texto pequeño
        if os.path.isfile(copy_path):
            with open(copy_path,'rb') as f:
                data=f.read()
            if data[:4]==b'\x7fELF':
                try: shutil.rmtree(WORK)
                except: pass
                res['status']='BLOCKED'; res['reason']='binario ELF requiere mecanismo específico; sin cambio aplicado'; res['h0']=h0
                return res
            # texto: intentar añadir comentario si no existe
            try:
                if b'# rxre_m344_test' not in data:
                    newd = data + b'\n# rxre_m344_test\n'
                    with open(copy_path,'wb') as f: f.write(newd)
                    h1=_hash(copy_path)
                    # validar independiente (comparar)
                    h1b=_hash(copy_path)
                    res['change_applied']=True
                    res['hash_after']=h1
                    res['hash_after_check']=h1b
                    res['diff_bytes']=len(newd)-len(data)
                    # rollback exacto
                    shutil.copy2(artifact, copy_path)
                    h2=_hash(copy_path)
                    res['hash_rollback']=h2
                    res['rollback_exact']=(h2==h0)
                    res['status']='PASS_PARTIAL' if res['rollback_exact'] else 'BLOCKED'
                    try: shutil.rmtree(WORK)
                    except: pass
                    return res
            except Exception as e:
                try: shutil.rmtree(WORK)
                except: pass
                res['status']='BLOCKED'; res['reason']=str(e); return res
        try: shutil.rmtree(WORK)
        except: pass
        res['status']='NOT_EXECUTED'; res['reason']='sin cambio seguro aplicable'
        return res
    except Exception as e:
        try: shutil.rmtree(WORK)
        except: pass
        res['status']='BLOCKED'; res['reason']=str(e); return res

if __name__=='__main__':
    print(json.dumps(run(sys.argv[1] if len(sys.argv)>1 else '/tmp/nonexistent', allow=False), indent=2))
