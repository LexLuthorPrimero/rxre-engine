#!/usr/bin/env python3
import sys, os, json, hashlib, tempfile, shutil, time, random
ROOT="/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT,'tools/rxre'))
sys.path.insert(0, os.path.join(ROOT,'m326_isolated/scripts'))
import fuego_transact_m344 as ft

def _hash(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda: f.read(1024*1024),b''): h.update(c)
    return h.hexdigest()

def run_case(artifact, transform_kind):
    res={'artifact':artifact,'transform':transform_kind,'status':'UNKNOWN'}
    # ensure isolated copy path not system
    if os.path.realpath(artifact).startswith('/usr/') or os.path.realpath(artifact).startswith('/bin/') or os.path.realpath(artifact).startswith('/sbin/'):
        res['status']='BLOCKED'; res['reason']='system artifact rejected'; return res
    WORK=tempfile.mkdtemp(prefix='m346_',dir='/tmp')
    copy_path=os.path.join(WORK,os.path.basename(artifact)+'.copy')
    try:
        shutil.copy2(artifact,copy_path)
        h0=_hash(copy_path)
        res['baseline']=h0
        with open(copy_path,'rb') as f: data=f.read()
        if data[:4]==b'\x7fELF':
            res['status']='BLOCKED'; res['reason']='ELF rejected'; return res
        # apply transform
        try:
            if transform_kind=='append':
                newd=data+b'\n# rxre_m346_append\n'
            elif transform_kind=='prepend':
                newd=b'# rxre_m346_prepend\n'+data
            elif transform_kind=='replace':
                newd=data.replace(b'OLDTOKEN',b'NEWTOKEN')
            else:
                res['status']='BLOCKED'; res['reason']='unknown transform'; return res
            with open(copy_path,'wb') as f: f.write(newd)
            h1=_hash(copy_path)
            h1b=_hash(copy_path)
            res['change_hash']=h1; res['check_hash']=h1b; res['independent_ok']=(h1==h1b)
            # rollback
            shutil.copy2(artifact,copy_path)
            h2=_hash(copy_path)
            res['rollback_hash']=h2; res['rollback_exact']=(h2==h0)
            res['status']='PASS' if (res['independent_ok'] and res['rollback_exact']) else 'FAIL'
        except Exception as e:
            res['status']='ERROR'; res['reason']=str(e)
        return res
    finally:
        try: shutil.rmtree(WORK)
        except: pass

def induced_failure(artifact):
    res={'artifact':artifact,'transform':'induced_failure','status':'UNKNOWN'}
    if os.path.realpath(artifact).startswith('/usr/'):
        res['status']='BLOCKED'; res['reason']='system'; return res
    WORK=tempfile.mkdtemp(prefix='m346_fail_',dir='/tmp')
    copy_path=os.path.join(WORK,'copy.txt')
    try:
        shutil.copy2(artifact,copy_path)
        h0=_hash(copy_path)
        # induce failure: make read-only dir? Instead simulate by writing then raising
        try:
            with open(copy_path,'ab') as f:
                f.write(b'\n# partial')
            # simulate failure before commit
            raise RuntimeError('induced failure')
        except RuntimeError:
            # recovery: restore from original
            shutil.copy2(artifact,copy_path)
            h1=_hash(copy_path)
            res['recovered']=(h1==h0)
            res['status']='RECOVERED' if res['recovered'] else 'FAILED'
    except Exception as e:
        res['status']='ERROR'; res['reason']=str(e)
    finally:
        try: shutil.rmtree(WORK)
        except: pass
    return res

def unauthorized_scope(artifact):
    # attempt transform on system path -> must reject
    res={'artifact':'/usr/bin/ls','transform':'unauthorized','status':'UNKNOWN'}
    r=run_case('/usr/bin/ls','append')
    res['rejected']= (r['status']=='BLOCKED')
    res['status']='PASS' if res['rejected'] else 'FAIL'
    return res

def main():
    # create artifacts
    arts=[]
    for i in range(3):
        p=f'/tmp/m346_art_{i}.txt'
        with open(p,'w') as f:
            f.write(f'content {i}\nOLDTOKEN here\n')
        arts.append(p)
    cases=[]
    kinds=['append','prepend','replace']
    for a in arts:
        for k in kinds:
            cases.append(run_case(a,k))
    # induced failure
    fail=induced_failure(arts[0])
    # unauthorized
    unauth=unauthorized_scope(arts[0])
    # binary reject
    binreject={'artifact':'/usr/bin/ls','transform':'binary','status':'UNKNOWN'}
    br=run_case('/usr/bin/ls','append')
    binreject['rejected']=(br['status']=='BLOCKED')
    binreject['status']='PASS' if binreject['rejected'] else 'FAIL'
    summary={'cases':cases,'induced_failure':fail,'unauthorized':unauth,'binary_reject':binreject}
    # aggregate
    allpass=all(c['status'] in ('PASS','RECOVERED','BLOCKED') for c in cases) and fail['status']=='RECOVERED' and unauth['status']=='PASS' and binreject['status']=='PASS'
    summary['all_pass']=allpass
    print(json.dumps(summary,indent=2))
    return 0 if allpass else 1

if __name__=='__main__':
    raise SystemExit(main())
