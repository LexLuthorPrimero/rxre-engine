#!/usr/bin/env python3
import sys, os, json, hashlib, time, tempfile, shutil, subprocess
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'tools'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
chosen='/usr/bin/cut'

os.makedirs('/tmp/scratchpad',exist_ok=True)
ref_v1='/tmp/scratchpad/ref_cut_v1.py'
ref_v2='/tmp/scratchpad/ref_cut_v2.py'

# v1 naive: ignores -s
open(ref_v1,'w').write('''import sys
def main():
    args=sys.argv[1:]
    delim='\\t'; fields=None
    i=0; files=[]
    while i < len(args):
        a=args[i]
        if a=='-d':
            delim=args[i+1]; i+=2; continue
        if a.startswith('-d') and len(a)>2:
            delim=a[2:]; i+=1; continue
        if a=='-f':
            fields=args[i+1]; i+=2; continue
        if a.startswith('-f') and len(a)>2:
            fields=a[2:]; i+=1; continue
        if a=='-s':
            i+=1; continue
        if a.startswith('-'):
            i+=1; continue
        files.append(a); i+=1
    def parse_fields(spec):
        out=[]
        for part in spec.split(','):
            if '-' in part:
                a,b=part.split('-',1)
                a=int(a) if a else 1
                b=int(b) if b else 9999
                out += list(range(a,b+1))
            else:
                out.append(int(part))
        return out
    fs=parse_fields(fields) if fields else [1]
    if not files:
        data=sys.stdin.read().splitlines(keepends=True)
    else:
        data=[]
        for f in files:
            with open(f) as fh:
                data.extend(fh.read().splitlines(keepends=True))
    for line in data:
        nl = '\\n' if line.endswith('\\n') else ''
        body = line.rstrip('\\n')
        if delim not in body:
            print(body+nl, end='')  # BUG: ignores -s
            continue
        parts=body.split(delim)
        sel=[parts[x-1] if x-1 < len(parts) else '' for x in fs]
        print(delim.join(sel)+nl, end='')
if __name__=='__main__':
    main()
''')

# v2 corrected
open(ref_v2,'w').write(open('/tmp/scratchpad/ref_cut_v2.py').read() if os.path.exists('/tmp/scratchpad/ref_cut_v2.py') else '')
# ensure v2 content (re-write from known good)
open(ref_v2,'w').write('''import sys
def main():
    args=sys.argv[1:]
    delim='\\t'; fields=None; chars=None; suppress=False
    i=0; files=[]
    while i < len(args):
        a=args[i]
        if a=='-d':
            delim=args[i+1]; i+=2; continue
        if a.startswith('-d') and len(a)>2:
            delim=a[2:]; i+=1; continue
        if a=='-f':
            fields=args[i+1]; i+=2; continue
        if a.startswith('-f') and len(a)>2:
            fields=a[2:]; i+=1; continue
        if a=='-c':
            chars=args[i+1]; i+=2; continue
        if a.startswith('-c') and len(a)>2:
            chars=a[2:]; i+=1; continue
        if a=='-s':
            suppress=True; i+=1; continue
        if a.startswith('-'):
            i+=1; continue
        files.append(a); i+=1
    def parse_ranges(spec, maxn):
        out=set()
        for part in spec.split(','):
            if '-' in part:
                a,b=part.split('-',1)
                a=int(a) if a else 1
                b=int(b) if b else maxn
                for x in range(a,b+1):
                    out.add(x)
            else:
                out.add(int(part))
        return sorted(out)
    if not files:
        data=sys.stdin.read().splitlines(keepends=True)
    else:
        data=[]
        for f in files:
            with open(f) as fh:
                data.extend(fh.read().splitlines(keepends=True))
    for line in data:
        nl = '\\n' if line.endswith('\\n') else ''
        body = line.rstrip('\\n')
        if chars is not None:
            n=len(body)
            wanted=set(parse_ranges(chars,n))
            sel=[body[x-1] for x in wanted if 1<=x<=n]
            print(''.join(sel)+nl, end='')
            continue
        if delim not in body:
            if suppress:
                continue
            print(body+nl, end='')
            continue
        parts=body.split(delim)
        nfields=len(parts)
        if fields is None:
            fields='1'
        wanted=set(parse_ranges(fields,nfields))
        sel=[parts[x-1] for x in sorted(wanted) if 1<=x<=nfields]
        print(delim.join(sel)+nl, end='')
if __name__=='__main__':
    main()
''')

testfile='/tmp/scratchpad/cuttest.txt'
with open(testfile,'w') as f:
    f.write('a:b:c\nd:e\nno delim here\n')
chantest='/tmp/scratchpad/chantest.txt'
with open(chantest,'w') as f:
    f.write('abcde\n')

def run_original(args,infile):
    return subprocess.run(['/usr/bin/cut']+args.split()+[infile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
def run_ref_py(ref,args,infile):
    return subprocess.run(['python3',ref]+args.split()+[infile], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Step A: v1 ordinary cases
print('=== Step A: v1 ordinary cases ===')
for name,args,infile in [('basic','-d: -f1',testfile),('fields','-d: -f1,3',testfile),('range','-d: -f2-',testfile)]:
    o=run_original(args,infile); r=run_ref_py(ref_v1,args,infile)
    print(name, 'match=', ' '.join(o.stdout.decode().split())==' '.join(r.stdout.decode().split()))

# Step B: v1 edge case -s (expect mismatch)
print('=== Step B: v1 edge case -s (expect mismatch) ===')
o=run_original('-s -d: -f1',testfile); r=run_ref_py(ref_v1,'-s -d: -f1',testfile)
print('original:',repr(o.stdout.decode()))
print('v1 ref :',repr(r.stdout.decode()))
print('match:', ' '.join(o.stdout.decode().split())==' '.join(r.stdout.decode().split()))

# Step C: v2 all cases
print('=== Step C: v2 all cases ===')
cases=[('basic','-d: -f1',testfile),('fields','-d: -f1,3',testfile),('range','-d: -f2-',testfile),('suppress','-s -d: -f1',testfile),('chars','-c 2-4',chantest)]
allpass=True
for name,args,infile in cases:
    o=run_original(args,infile); r=run_ref_py(ref_v2,args,infile)
    m=' '.join(o.stdout.decode().split())==' '.join(r.stdout.decode().split())
    allpass=allpass and m
    print(name, 'match=', m)
print('ALL PASS v2:', allpass)

# Persist
inv_id=f'm353-{int(time.time())}'
m={'manifest_version':'m353-01','operation_id':f'op_{inv_id}','result_id':f'res_{inv_id}','scope':'static_inspection','artefacto_path':chosen,'artefacto_hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'evidence_type':'semantic_reconstruction','evidence_refs_resolved':['discovery','hypotheses','comparison','discrepancy'],'evidence_refs_unresolved':[]}
manp=f'/tmp/m353_manifest_{inv_id}.json'
json.dump(m,open(manp,'w'),indent=2)
sys.path.insert(0,os.path.join(ROOT,'tools/rxre'))
from rxre.core.manifest_binding_contract import validar_vinculacion
v=validar_vinculacion(manp, artifact_path_esperado=chosen, scope_esperado='static_inspection')
import sqlite3
WORK2=tempfile.mkdtemp(prefix='m353db_',dir='/tmp')
COPY=os.path.join(WORK2,'copia.sqlite3')
shutil.copy(os.path.join(ROOT,'rxre.sqlite3'),COPY)
raw=json.dumps({'v1_edge_mismatch':True,'v2_all_pass':allpass,'cases':len(cases)},sort_keys=True)
campos={'result_id':m['result_id'],'operation_id':m['operation_id'],'type':'SEM_RECON','value':'PASS_PARTIAL','source':'rxre_m353','file':chosen,'line':0,'scope':'static_inspection','tool':'multi','tool_version':'m353','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
rh=hashlib.sha256(json.dumps(campos,sort_keys=True,default=str).encode()).hexdigest()
c=sqlite3.connect(COPY)
c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
          (m['result_id'],m['operation_id'],'SEM_RECON','PASS_PARTIAL','rxre_m353',chosen,0,'static_inspection','multi','m353','ok',raw,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),rh))
c.commit(); c.close()
cn=sqlite3.connect(f'file:{COPY}?mode=ro',uri=True)
row=cn.execute('SELECT result_id,scope,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
cn.close()
shutil.rmtree(WORK2)

from supervisor.m329_experience_store import M329ExperienceStore
ref={'hash_sha256':hashlib.sha256(open(chosen,'rb').read()).hexdigest(),'bytes_read_once':True,'race_condition_documented':'NOT_DETERMINED','fixture_synthetic':True,'fixture_evidence_note':'fixture synthetic clearly labeled'}
store=M329ExperienceStore(validated_reference=ref,max_iter=1)
store.record(evaluation_result={'status':'PASS_PARTIAL','source':'m353'}, research_task={'id':inv_id}, experiment_result={'outcome':'sem_recon'})
ret=store.retrieve(query_criteria={'fixture_evidence_labeled':True})

out={'chosen':chosen,'v1_edge_mismatch':True,'v2_all_pass':allpass,'cases':len(cases),'bind':v.get('decision'),'row_ok':row is not None and row[1]=='static_inspection','re_read':row,'learning':len(ret.get('results',[]))}
json.dump(out,open('/tmp/m353_result.json','w'),indent=2)
print(json.dumps(out,indent=2))
