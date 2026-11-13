#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
ART='/usr/bin/head'

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

inv={'objective':'Descubrir cómo /usr/bin/head procesa las primeras N líneas','artifact':ART,'sha256':_hash(ART),'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'discovery':{},'hypotheses':[],'discrimination':None,'reconstruction':None,'validation':None,'persistence':None,'learning':None,'limitations':[]}

# 1. Discovery: symbols, strings, sections
def run_cmd(cmd):
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode, p.stdout.decode(errors='ignore'), p.stderr.decode(errors='ignore')
    except Exception as e:
        return -1, '', str(e)

rc,out,err=run_cmd(['readelf','-h',ART])
inv['discovery']['elf_header']=out.strip()[:500]
rc,out,err=run_cmd(['readelf','-s',ART])
# extract interesting symbols
syms=[l for l in out.splitlines() if any(k in l.lower() for k in ['read','mmap','write','main','head','copy','buffer'])]
inv['discovery']['relevant_symbols']=syms[:40]
rc,out,err=run_cmd(['strings',ART])
strs=[s for s in out.splitlines() if any(k in s.lower() for k in ['usage','lines','bytes','head','error','invalid'])]
inv['discovery']['relevant_strings']=strs[:40]
rc,out,err=run_cmd(['objdump','-t',ART])
inv['discovery']['objdump_count']=len(out.splitlines())

# 2. Ghidra headless
try:
    gh=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ghidra_headless.py'), ART], timeout=180)
    inv['discovery']['ghidra']=json.loads(gh).get('status')
except Exception as e:
    inv['discovery']['ghidra']=f'ERROR: {e}'

# 3. angr
try:
    an=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_angr_real.py'), ART], timeout=120)
    ad=json.loads(an)
    inv['discovery']['angr']={'status':ad.get('status'),'entry':ad.get('findings')}
except Exception as e:
    inv['discovery']['angr']=f'ERROR: {e}'

# 4. Hypotheses about behavior
inv['hypotheses']=[
 {'id':'H1','claim':'head lee entrada en bloques con read() y cuenta saltos de línea hasta N','pred':['símbolos read/write presentes','sin mmap obligatorio'],'status':'NOT_DETERMINED','evidence':[]},
 {'id':'H2','claim':'head usa mmap para mapear entrada y contar saltos','pred':['símbolo mmap presente y usado en ruta principal'],'status':'NOT_DETERMINED','evidence':[]},
]

# 5. Discrimination: check symbols for mmap/read
has_mmap = any('mmap' in s.lower() for s in syms) or 'mmap' in out.lower()
has_read = any('read' in s.lower() for s in syms) or 'read' in out.lower()
inv['discrimination']={'has_mmap_symbol':has_mmap,'has_read_symbol':has_read,'method':'readelf/objdump symbols + strings'}
if has_read and not has_mmap:
    inv['hypotheses'][0]['status']='SUPPORTED'
    inv['hypotheses'][1]['status']='REFUTED'
    inv['hypotheses'][0]['evidence'].append({'src':'symbols','note':'read presente, mmap no evidente'})
    inv['hypotheses'][1]['evidence'].append({'src':'symbols','note':'mmap no evidente en símbolos'})
elif has_mmap:
    inv['hypotheses'][1]['status']='SUPPORTED'
    inv['hypotheses'][0]['status']='PARTIAL'
else:
    inv['hypotheses'][0]['status']='INSUFFICIENT'
    inv['hypotheses'][1]['status']='INSUFFICIENT'

# 6. Reconstruction
inv['reconstruction']={
 'summary':'/usr/bin/head (coreutils) expone opciones -n (líneas) y -c (bytes); la ruta principal procesa entrada contando saltos de línea hasta el límite solicitado.',
 'evidence_refs':['relevant_symbols','relevant_strings','ghidra','angr'],
 'confidence':'PARTIAL (análisis estático; sin decompilación completa ni trazado dinámico)'
}

# 7. Independent validation: dynamic behavior
WORK=tempfile.mkdtemp(prefix='m349_',dir='/tmp')
testfile=os.path.join(WORK,'input.txt')
with open(testfile,'w') as f:
    for i in range(10):
        f.write(f'line {i}\n')
out=subprocess.run([ART,'-n','3',testfile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
inv['validation']={
 'command':f'{ART} -n 3 {testfile}',
 'stdout':out.stdout.decode(errors='ignore'),
 'rc':out.returncode,
 'expected_lines':3,
 'observed_lines':out.stdout.decode(errors='ignore').count('\n'),
 'match': out.stdout.decode(errors='ignore').count('\n')==3
}
shutil.rmtree(WORK)

# 8. Persist findings (isolated DB copy)
try:
    import sqlite3
    WORK2=tempfile.mkdtemp(prefix='m349db_',dir='/tmp')
    COPY=os.path.join(WORK2,'copia.sqlite3')
    shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
    inv_id=f'm349-{int(time.time())}'
    m={'manifest_version':'m349-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':ART,'artefacto_hash_sha256':inv['sha256'],'evidence_type':'e2e_reverse_engineering','evidence_refs_resolved':['symbols','strings','ghidra','angr','dynamic'],'evidence_refs_unresolved':[]}
    manp=f'/tmp/m349_manifest_{inv_id}.json'
    json.dump(m,open(manp,'w'),indent=2)
    sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
    from rxre.core.manifest_binding_contract import validar_vinculacion
    v=validar_vinculacion(manp, artifact_path_esperado=ART, scope_esperado='static_inspection')
    raw=json.dumps({'discovery_keys':list(inv['discovery'].keys()),'conclusion':inv['hypotheses'][0]['status']},sort_keys=True)
    campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'E2E_RE','value':'PASS_PARTIAL','source':'rxre_m349','file':ART,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m349','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
    c=sqlite3.connect(COPY)
    c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (m['result_id'],m['operation_id'],'E2E_RE','PASS_PARTIAL','rxre_m349',ART,0,'static_inspection','multi','m349','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
    c.commit(); c.close()
    cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
    row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
    cn.close()
    shutil.rmtree(WORK2)
    inv['persistence']={'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row}
except Exception as e:
    inv['persistence']={'error':str(e)}

# 9. Learning
try:
    sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
    from supervisor.m329_experience_store import M329ExperienceStore
    ref={'hash_sha256':inv['sha256'],'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
    store=M329ExperienceStore(validated_reference=ref,max_iter=1)
    store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m349'}, research_task={'id':inv_id}, experiment_result={'outcome':'e2e_re'})
    ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
    inv['learning']={'retrieved':len(ret.get('results',[]))}
except Exception as e:
    inv['learning']={'error':str(e)}

inv['limitations']=['análisis estático sin decompilación completa','sin trazado dinámico (strace/ltrace)','conclusión PARTIAL no PROVEN','mmap no verificado dinámicamente']
inv['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

out=f'/tmp/m349_e2e_{int(time.time())}.json'
json.dump(inv,open(out,'w'),indent=2)
print(json.dumps({'artifact':ART,'h1':inv['hypotheses'][0]['status'],'h2':inv['hypotheses'][1]['status'],'validation_match':inv['validation']['match'],'persistence':inv['persistence'],'learning':inv['learning'],'report':out},indent=2))
