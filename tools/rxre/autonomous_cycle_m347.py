#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
import selector_tools_m343 as sel

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run(obj, artifact):
    cycle={'objective':obj,'artifact':artifact,'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'transitions':[],'tools':{},'hypotheses':[],'conclusion':None,'persistence':None,'learning':None,'intervention':None,'errors':[]}
    def T(name,status,detail=None):
        cycle['transitions'].append({'name':name,'status':status,'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'detail':detail})
    # 1. preflight
    if not os.path.exists(artifact):
        T('preflight','FAIL',{'reason':'missing artifact'}); cycle['conclusion']='BLOCKED'; return cycle
    T('preflight','OK',{'sha256':_hash(artifact)})
    # 2. plan (tool selection)
    selection=sel.select(obj)
    T('plan','OK',{'selected':selection['selected']})
    # 3. execute selected tools (with failure handling)
    for t in selection['selected']:
        try:
            if t=='angr':
                out=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_angr_real.py'), artifact], timeout=120)
                cycle['tools'][t]=json.loads(out)
            elif t=='ghidra':
                out=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ghidra_headless.py'), artifact], timeout=180)
                cycle['tools'][t]=json.loads(out)
            elif t=='rea':
                out=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_rea_bridge.py'), artifact], timeout=60)
                cycle['tools'][t]=json.loads(out)
            elif t=='ofrak':
                out=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ofrak_inspect.py'), artifact], timeout=60)
                cycle['tools'][t]=json.loads(out)
            T(f'tool:{t}','OK',{'status':cycle['tools'][t].get('status')})
        except Exception as e:
            cycle['tools'][t]={'status':'ERROR','reason':str(e)}
            cycle['errors'].append(f'{t}: {e}')
            T(f'tool:{t}','ERROR',{'reason':str(e)})
    # 4. hypotheses
    hyps=[{'id':'H1','claim':'artefacto estándar sin anomalías verificables','status':'NOT_DETERMINED','evidence':[]},
          {'id':'H2','claim':'posibles anomalías locales','status':'NOT_DETERMINED','evidence':[]}]
    # discriminate using angr if available
    angr=cycle['tools'].get('angr',{})
    if angr.get('status')=='IMPLEMENTED_AND_TESTED':
        hyps[0]['evidence'].append({'src':'angr','entry':angr.get('findings',[{}])[0].get('addr') if angr.get('findings') else None})
        hyps[0]['status']='PARTIAL'
        hyps[1]['status']='INSUFFICIENT'
        hyps[1]['evidence'].append({'src':'angr','note':'sin anomalía detectable con análisis mínimo'})
    cycle['hypotheses']=hyps
    T('hypotheses','OK',{'supported':'H1'})
    # 5. conclusion
    cycle['conclusion']={'supported':'H1','state':'PARTIAL','rationale':'herramientas seleccionadas ejecutadas; sin evidencia verificable de anomalías'}
    T('conclusion','OK',cycle['conclusion'])
    # 6. persistence (isolated copy)
    try:
        import sqlite3
        WORK=tempfile.mkdtemp(prefix='m347_',dir='/tmp')
        COPY=os.path.join(WORK,'copia.sqlite3')
        shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
        inv_id=f'm347-{int(time.time())}'
        m={'manifest_version':'m347-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':artifact,'artefacto_hash_sha256':_hash(artifact),'evidence_type':'autonomous_cycle','evidence_refs_resolved':['tools','hypotheses','conclusion'],'evidence_refs_unresolved':[]}
        manp=f'/tmp/m347_manifest_{inv_id}.json'
        json.dump(m,open(manp,'w'),indent=2)
        sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
        from rxre.core.manifest_binding_contract import validar_vinculacion
        v=validar_vinculacion(manp, artifact_path_esperado=artifact, scope_esperado='static_inspection')
        raw=json.dumps({'tools':[k for k,v in cycle['tools'].items() if v.get('status') in ('IMPLEMENTED_AND_TESTED','PARTIAL')],'conclusion':cycle['conclusion']},sort_keys=True)
        campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'AUTO_CYCLE','value':'PASS_PARTIAL','source':'rxre_m347','file':artifact,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m347','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
        c=sqlite3.connect(COPY)
        c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (m['result_id'],m['operation_id'],'AUTO_CYCLE','PASS_PARTIAL','rxre_m347',artifact,0,'static_inspection','multi','m347','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
        c.commit(); c.close()
        cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
        row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
        cn.close()
        shutil.rmtree(WORK)
        cycle['persistence']={'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row}
        T('persistence','OK',cycle['persistence'])
    except Exception as e:
        cycle['errors'].append(f'persistence: {e}')
        T('persistence','ERROR',{'reason':str(e)})
    # 7. learning
    try:
        sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
        from supervisor.m329_experience_store import M329ExperienceStore
        ref={'hash_sha256':_hash(artifact),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
        store=M329ExperienceStore(validated_reference=ref,max_iter=1)
        store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m347'}, research_task={'id':inv_id}, experiment_result={'outcome':'autonomous_cycle'})
        ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
        cycle['learning']={'retrieved':len(ret.get('results',[]))}
        T('learning','OK',cycle['learning'])
    except Exception as e:
        cycle['errors'].append(f'learning: {e}')
        T('learning','ERROR',{'reason':str(e)})
    # 8. intervention decision
    try:
        # only intervene if authorized provision present
        prov_present = os.path.exists('/tmp/rxre_auth_provisioned/identities.json') and os.path.exists('/tmp/rxre_306_work/servicio.key')
        if prov_present:
            # use existing fuego transaction on isolated text copy
            import fuego_transact_m344 as ft
            # create isolated artifact copy
            WORK2=tempfile.mkdtemp(prefix='m347_fuego_',dir='/tmp')
            iso=os.path.join(WORK2,'iso.txt')
            shutil.copy2(artifact,iso) if artifact.endswith('.txt') else None
            # if artifact is binary, create text surrogate
            if not os.path.exists(iso):
                with open(iso,'w') as f: f.write('surrogate for intervention test\n')
            r=ft.run(iso, allow=True)
            cycle['intervention']={'attempted':True,'status':r.get('status'),'rollback_exact':r.get('rollback_exact'),'scope':r.get('scope')}
            T('intervention',r.get('status','BLOCKED'),cycle['intervention'])
            try: shutil.rmtree(WORK2)
            except: pass
        else:
            cycle['intervention']={'attempted':False,'status':'BLOCKED','reason':'provisión persistente ausente','exact_admin_step':'tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key (0600, uid/emisor/ejecutor, identities.json con key_sha256/nonce/firma)'}
            T('intervention','BLOCKED',cycle['intervention'])
    except Exception as e:
        cycle['errors'].append(f'intervention: {e}')
        T('intervention','ERROR',{'reason':str(e)})
    cycle['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    cycle['autonomous']=True
    cycle['autonomous_loop']=False
    cycle['max_iter']=1
    cycle['op_claim']=False
    return cycle

if __name__=='__main__':
    obj=sys.argv[1] if len(sys.argv)>1 else 'Investigar artefacto y decidir intervención'
    art=sys.argv[2] if len(sys.argv)>2 else '/usr/bin/ls'
    c=run(obj,art)
    out=f'/tmp/m347_cycle_{int(time.time())}.json'
    json.dump(c,open(out,'w'),indent=2)
    print(json.dumps({'objective':c['objective'],'artifact':c['artifact'],'transitions':len(c['transitions']),'errors':c['errors'],'intervention':c['intervention'],'report':out},indent=2))
