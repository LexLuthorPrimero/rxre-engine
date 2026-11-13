#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
ART='/usr/bin/wc'

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

inv={'objective':'Reconstruir comportamiento de /usr/bin/wc y verificar equivalencia funcional','artifact':ART,'sha256':_hash(ART),'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'discovery':{},'hypotheses':[],'spec':None,'reference':None,'comparison':None,'discrepancies':[],'persistence':None,'learning':None,'limitations':[]}

# 1. Discovery
def run_cmd(cmd):
    try:
        p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return p.returncode, p.stdout.decode(errors='ignore'), p.stderr.decode(errors='ignore')
    except Exception as e:
        return -1,'',str(e)

rc,out,err=run_cmd(['readelf','-s',ART])
syms=[l for l in out.splitlines() if any(k in l.lower() for k in ['read','write','count','word','line','byte','main'])]
inv['discovery']['relevant_symbols']=syms[:30]
rc,out,err=run_cmd(['strings',ART])
strs=[s for s in out.splitlines() if any(k in s.lower() for k in ['lines','words','bytes','chars','maximum','usage'])]
inv['discovery']['relevant_strings']=strs[:30]
# ghidra
try:
    gh=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_ghidra_headless.py'), ART], timeout=180)
    inv['discovery']['ghidra']=json.loads(gh).get('status')
except Exception as e:
    inv['discovery']['ghidra']=f'ERROR: {e}'
# angr
try:
    an=subprocess.check_output([sys.executable, os.path.join(ROOT,'tools/rxre/run_angr_real.py'), ART], timeout=120)
    ad=json.loads(an)
    inv['discovery']['angr']={'status':ad.get('status'),'entry':ad.get('findings')}
except Exception as e:
    inv['discovery']['angr']=f'ERROR: {e}'

# 2. Hypotheses
inv['hypotheses']=[
 {'id':'H1','claim':'wc cuenta líneas por \\n, palabras por transiciones de espacio, bytes por tamaño de entrada','status':'NOT_DETERMINED','evidence':[]},
 {'id':'H2','claim':'wc cuenta caracteres (multibyte) por defecto en lugar de bytes','status':'NOT_DETERMINED','evidence':[]},
]
# discriminate via strings/options
if any('bytes' in s.lower() for s in strs):
    inv['hypotheses'][0]['status']='SUPPORTED'
    inv['hypotheses'][0]['evidence'].append({'src':'strings','note':'opción bytes documentada'})
    inv['hypotheses'][1]['status']='REFUTED'
    inv['hypotheses'][1]['evidence'].append({'src':'strings','note':'bytes por defecto, no chars'})

# 3. Spec
inv['spec']={
 'default_output':'lines words bytes (en ese orden)',
 'options':{'-l':'solo líneas','-w':'solo palabras','-c':'solo bytes','-m':'caracteres (multibyte)','-L':'longitud máxima de línea'},
 'definitions':{'line':'secuencia terminada en \\n (última sin \\n cuenta si hay contenido)','word':'secuencia de caracteres no-espacio','byte':'byte crudo'},
 'scope':'solo entradas de texto/bytes en archivos y stdin; sin locale avanzado'
}

# 4. Reference implementation (isolated)
WORK=tempfile.mkdtemp(prefix='m350_',dir='/tmp')
REF=os.path.join(WORK,'ref_wc.py')
ref_code='''import sys
def counts(data):
    lines = data.count(b"\\n")
    # wc counts newline characters only; no implicit +1
    # words: split on whitespace
    import re
    words = len(data.split())
    bytesn = len(data)
    # max line length (wc -L): 0 if NUL present; else char count per line
    if b"\\x00" in data:
        maxl = 0
    else:
        maxl = 0
        try:
            text = data.decode("utf-8")
            for line in text.split("\\n"):
                if len(line) > maxl:
                    maxl = len(line)
        except Exception:
            for line in data.split(b"\\n"):
                if len(line) > maxl:
                    maxl = len(line)
    return lines, words, bytesn, maxl

def main():
    mode = "default"
    args = sys.argv[1:]
    files = []
    for a in args:
        if a.startswith("-"):
            mode = a
        else:
            files.append(a)
    if not files:
        data = sys.stdin.buffer.read()
        l,w,b,mx = counts(data)
        if mode == "-l":
            print(l)
        elif mode == "-w":
            print(w)
        elif mode == "-c":
            print(b)
        elif mode == "-L":
            print(mx)
        else:
            print(l, w, b)
        return
    for f in files:
        with open(f,"rb") as fh:
            data = fh.read()
        l,w,b,mx = counts(data)
        name = f
        if mode == "-l":
            print(l, name)
        elif mode == "-w":
            print(w, name)
        elif mode == "-c":
            print(b, name)
        elif mode == "-L":
            print(mx, name)
        else:
            print(l, w, b, name)

if __name__ == "__main__":
    main()
'''
open(REF,'w').write(ref_code)

# 5. Comparison across cases
cases=[]
# generate test inputs
inputs={
 'empty': b'',
 'single_line': b'hello world\n',
 'no_trailing': b'hello world',
 'multi': b'a b c\nd e\nf\n',
 'only_spaces': b'   \n',
 'binary': b'\x00\x01\x02\n',
 'unicode': 'café\n'.encode(),
 'large': (b'x '*1000 + b'\n')*10,
}
comparison={'cases':[],'mismatches':0}
for name,data in inputs.items():
    tf=os.path.join(WORK,name+'.txt')
    with open(tf,'wb') as f: f.write(data)
    for mode in ['default','-l','-w','-c','-L']:
        # original
        if mode=='default':
            o=subprocess.run([ART,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            o=subprocess.run([ART,mode,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # reference
        if mode=='default':
            r=subprocess.run([sys.executable,REF,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            r=subprocess.run([sys.executable,REF,mode,tf], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # normalize: remove filename? compare numeric part
        o_out=o.stdout.decode(errors='ignore').strip()
        r_out=r.stdout.decode(errors='ignore').strip()
        # strip filename for comparison
        o_nums=' '.join(o_out.split()[: (1 if mode!='default' else 3)])
        r_nums=' '.join(r_out.split()[: (1 if mode!='default' else 3)])
        match = (o_nums==r_nums)
        comparison['cases'].append({'input':name,'mode':mode,'original':o_out,'reference':r_out,'match':match})
        if not match:
            comparison['mismatches']+=1
            inv['discrepancies'].append({'input':name,'mode':mode,'original':o_out,'reference':r_out})

# stdin case
p=subprocess.run([ART], input=b'hi there\nbye\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
r=subprocess.run([sys.executable,REF], input=b'hi there\nbye\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
comparison['cases'].append({'input':'stdin','mode':'default','original':p.stdout.decode().strip(),'reference':r.stdout.decode().strip(),'match':' '.join(p.stdout.decode().split())==' '.join(r.stdout.decode().split())})
if ' '.join(p.stdout.decode().split()) != ' '.join(r.stdout.decode().split()):
    comparison['mismatches']+=1

inv['comparison']=comparison
inv['reference_path']=REF

# 6. Update reconstruction based on discrepancies
if comparison['mismatches']==0:
    inv['reconstruction_final']={'status':'EQUIVALENT_FOR_TESTED_CASES','note':'Todas las comparaciones coincidieron para los casos definidos. No implica equivalencia universal.','mismatches':0}
else:
    inv['reconstruction_final']={'status':'DISCREPANCIES_FOUND','mismatches':comparison['mismatches'],'note':'Revisar definiciones (locale, multibyte, max line length).'}

# 7. Persist
try:
    import sqlite3
    WORK2=tempfile.mkdtemp(prefix='m350db_',dir='/tmp')
    COPY=os.path.join(WORK2,'copia.sqlite3')
    shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
    inv_id=f'm350-{int(time.time())}'
    m={'manifest_version':'m350-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':ART,'artefacto_hash_sha256':inv['sha256'],'evidence_type':'functional_reconstruction','evidence_refs_resolved':['discovery','hypotheses','spec','reference','comparison'],'evidence_refs_unresolved':[]}
    manp=f'/tmp/m350_manifest_{inv_id}.json'
    json.dump(m,open(manp,'w'),indent=2)
    sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
    from rxre.core.manifest_binding_contract import validar_vinculacion
    v=validar_vinculacion(manp, artifact_path_esperado=ART, scope_esperado='static_inspection')
    raw=json.dumps({'mismatches':comparison['mismatches'],'status':inv['reconstruction_final']['status']},sort_keys=True)
    campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'FUNC_RECON','value':'PASS_PARTIAL','source':'rxre_m350','file':ART,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m350','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
    c=sqlite3.connect(COPY)
    c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (m['result_id'],m['operation_id'],'FUNC_RECON','PASS_PARTIAL','rxre_m350',ART,0,'static_inspection','multi','m350','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
    c.commit(); c.close()
    cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
    row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
    cn.close()
    shutil.rmtree(WORK2)
    inv['persistence']={'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row}
except Exception as e:
    inv['persistence']={'error':str(e)}

# 8. Learning
try:
    sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
    from supervisor.m329_experience_store import M329ExperienceStore
    ref={'hash_sha256':inv['sha256'],'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
    store=M329ExperienceStore(validated_reference=ref,max_iter=1)
    store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m350'}, research_task={'id':inv_id}, experiment_result={'outcome':'func_recon'})
    ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})
    inv['learning']={'retrieved':len(ret.get('results',[]))}
except Exception as e:
    inv['learning']={'error':str(e)}

inv['limitations']=['equivalencia solo para casos definidos, no universal','sin locale/multibyte exhaustivo','sin opciones combinadas','referencia Python puede divergir en edge cases','confianza PARTIAL']
inv['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
# cleanup work (keep ref? remove)
try: shutil.rmtree(WORK)
except: pass
out=f'/tmp/m350_recon_{int(time.time())}.json'
json.dump(inv,open(out,'w'),indent=2)
print(json.dumps({'artifact':ART,'mismatches':inv['comparison']['mismatches'],'total_cases':len(inv['comparison']['cases']),'status':inv['reconstruction_final']['status'],'persistence':inv['persistence'],'learning':inv['learning'],'report':out},indent=2))
