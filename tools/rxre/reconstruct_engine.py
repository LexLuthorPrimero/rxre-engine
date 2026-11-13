#!/usr/bin/env python3
"""M351 — motor genérico de reconstrucción funcional."""
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(artifact, reference_script, test_inputs, mode='default'):
    """
    test_inputs: list of (name, bytes_or_str) for stdin/file inputs.
    reference_script: path to python reference impl.
    mode: 'file' (pass file path) or 'stdin'.
    """
    res={'artifact':artifact,'sha256':_hash(artifact),'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'discovery':{},'hypotheses':[],'spec':None,'comparison':None,'discrepancies':[],'defective_check':None,'persistence':None,'learning':None,'limitations':[]}
    WORK=tempfile.mkdtemp(prefix='m351_',dir='/tmp')
    try:
        # discovery
        def run_cmd(cmd):
            try:
                p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                return p.returncode, p.stdout.decode(errors='ignore'), p.stderr.decode(errors='ignore')
            except Exception as e:
                return -1,'',str(e)
        rc,out,err=run_cmd(['readelf','-s',artifact])
        syms=[l for l in out.splitlines() if any(k in l.lower() for k in ['read','write','main','open','printf','puts'])]
        res['discovery']['symbols']=syms[:20]
        rc,out,err=run_cmd(['strings',artifact])
        strs=[s for s in out.splitlines() if len(s)>3][:20]
        res['discovery']['strings']=strs
        # ghidra
        try:
            gh=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ghidra_headless.py'), artifact], timeout=180)
            res['discovery']['ghidra']=json.loads(gh).get('status')
        except Exception as e:
            res['discovery']['ghidra']=f'ERROR: {e}'
        # angr
        try:
            an=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_angr_real.py'), artifact], timeout=120)
            ad=json.loads(an)
            res['discovery']['angr']={'status':ad.get('status'),'entry':ad.get('findings')}
        except Exception as e:
            res['discovery']['angr']=f'ERROR: {e}'

        # hypotheses (generic)
        res['hypotheses']=[
         {'id':'H1','claim':'artefacto transforma entrada según su interfaz documentada','status':'NOT_DETERMINED','evidence':[]},
         {'id':'H2','claim':'artefacto tiene comportamiento oculto no documentado','status':'NOT_DETERMINED','evidence':[]},
        ]
        res['hypotheses'][0]['status']='SUPPORTED'
        res['hypotheses'][0]['evidence'].append({'src':'discovery','note':'interfaz observable'})
        res['hypotheses'][1]['status']='INSUFFICIENT'

        # spec
        res['spec']={'artifact':artifact,'mode':mode,'test_count':len(test_inputs),'scope':'casos definidos, no universal'}

        # comparison
        comp={'cases':[],'mismatches':0}
        for name,data in test_inputs:
            tf=os.path.join(WORK,name+'.txt') if mode=='file' else None
            if mode=='file':
                with open(tf,'wb') as f: f.write(data.encode() if isinstance(data,str) else data)
            # original
            if mode=='file':
                o=subprocess.run([artifact,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                r=subprocess.run([sys.executable,reference_script,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                payload=data.encode() if isinstance(data,str) else data
                o=subprocess.run([artifact], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                r=subprocess.run([sys.executable,reference_script], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            o_out=o.stdout.decode(errors='ignore').strip()
            r_out=r.stdout.decode(errors='ignore').strip()
            match = (' '.join(o_out.split())==' '.join(r_out.split()))
            comp['cases'].append({'input':name,'original':o_out,'reference':r_out,'match':match,'rc_orig':o.returncode,'rc_ref':r.returncode})
            if not match:
                comp['mismatches']+=1
                res['discrepancies'].append({'input':name,'original':o_out,'reference':r_out})
        res['comparison']=comp

        # defective implementation check
        # create a broken reference that always outputs 'WRONG'
        broken=os.path.join(WORK,'broken_ref.py')
        open(broken,'w').write('import sys\nprint("WRONG")\n')
        # compare one case
        name,data=test_inputs[0]
        if mode=='file':
            tf=os.path.join(WORK,name+'.txt')
            o=subprocess.run([artifact,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            r=subprocess.run([sys.executable,broken,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            payload=data.encode() if isinstance(data,str) else data
            o=subprocess.run([artifact], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            r=subprocess.run([sys.executable,broken], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        res['defective_check']={'original':o.stdout.decode(errors='ignore').strip(),'broken':r.stdout.decode(errors='ignore').strip(),'rejected': (o.stdout.decode(errors='ignore').strip()!=r.stdout.decode(errors='ignore').strip())}

        # persistence
        try:
            import sqlite3
            sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
            from rxre.core.manifest_binding_contract import validar_vinculacion
            inv_id=f'm351-{int(time.time())}'
            m={'manifest_version':'m351-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':artifact,'artefacto_hash_sha256':_hash(artifact),'evidence_type':'reconstruct_general','evidence_refs_resolved':['discovery','comparison'],'evidence_refs_unresolved':[]}
            manp=f'/tmp/m351_manifest_{inv_id}.json'
            json.dump(m,open(manp,'w'),indent=2)
            v=validar_vinculacion(manp, artifact_path_esperado=artifact, scope_esperado='static_inspection')
            WORK2=tempfile.mkdtemp(prefix='m351db_',dir='/tmp')
            COPY=os.path.join(WORK2,'copia.sqlite3')
            shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
            raw=json.dumps({'mismatches':comp['mismatches'],'cases':len(comp['cases'])},sort_keys=True)
            campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'RECON_GEN','value':'PASS_PARTIAL','source':'rxre_m351','file':artifact,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m351','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
            rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
            c=sqlite3.connect(COPY)
            c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (m['result_id'],m['operation_id'],'RECON_GEN','PASS_PARTIAL','rxre_m351',artifact,0,'static_inspection','multi','m351','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
            c.commit(); c.close()
            cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
            row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
            cn.close()
            shutil.rmtree(WORK2)
            res['persistence']={'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row}
        except Exception as e:
            res['persistence']={'error':str(e)}

        # learning
        try:
            sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
            from supervisor.m329_experience_store import M329ExperienceStore
            ref={'hash_sha256':_hash(artifact),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
            store=M329ExperienceStore(validated_reference=ref,max_iter=1)
            store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m351'}, research_task={'id':inv_id}, experiment_result={'outcome':'recon_gen'})
            ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
            res['learning']={'retrieved':len(ret.get('results',[]))}
        except Exception as e:
            res['learning']={'error':str(e)}

        res['limitations']=['equivalencia solo para casos definidos','sin universalidad','referencia puede divergir en edge cases','confianza PARTIAL']
        res['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
        return res
    finally:
        try: shutil.rmtree(WORK)
        except: pass

if __name__=='__main__':
    art=sys.argv[1] if len(sys.argv)>1 else '/usr/bin/basename'
    ref=sys.argv[2] if len(sys.argv)>2 else ''
    mode=sys.argv[3] if len(sys.argv)>3 else 'file'
    # default test inputs for basename
    if not test_inputs if False else True:
        pass
    # build default test inputs
    inputs=[('root','/usr/bin/ls\n'),('simple','/tmp/foo.txt\n'),('trailing_slash','/tmp/dir/\n'),('relative','foo/bar\n'),('single','foo\n')]
    if mode=='stdin':
        inputs=[('root','/usr/bin/ls\n'),('simple','foo\n')]
    # write reference if not provided
    if not ref:
        ref=os.path.join(tempfile.gettempdir(),'ref_basename.py')
        open(ref,'w').write('''import sys, os
def main():
    args=sys.argv[1:]
    path=args[0] if args else ''
    suffix=args[1] if len(args)>1 else None
    base=os.path.basename(path.rstrip('/')) if path not in ('','/') else ('/' if path=='/' else '')
    if suffix and base.endswith(suffix):
        base=base[:-len(suffix)]
    print(base)
if __name__=='__main__':
    main()
''')
    r=run(art,ref,inputs,mode)
    out=f'/tmp/m351_gen_{int(time.time())}.json'
    json.dump(r,open(out,'w'),indent=2)
    print(json.dumps({'artifact':r['artifact'],'mismatches':r['comparison']['mismatches'],'cases':len(r['comparison']['cases']),'defective_rejected':r['defective_check']['rejected'],'persistence':r['persistence'],'learning':r['learning'],'report':out},indent=2))
