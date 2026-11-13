#!/usr/bin/env python3
import sys, json, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools/rxre")
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from supervisor.m329_experience_store import M329ExperienceStore

def verify():
    store = M329ExperienceStore(validated_reference={'hash_sha256': __import__('hashlib').sha256(b'x').hexdigest(), 'bytes_read_once':True, 'race_condition_documented':'NOT_DETERMINED', 'fixture_synthetic':True, 'fixture_evidence_note':'fixture synthetic clearly labeled'}, max_iter=1)
    ret = store.retrieve(query_criteria={'fixture_evidence_labeled':True})
    return {'count': len(ret.get('results',[])), 'status': ret.get('status')}

if __name__=='__main__':
    print(json.dumps(verify(), indent=2))
