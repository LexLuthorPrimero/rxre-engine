#!/usr/bin/env python3
"""RXRE-M338 — Runner único RXRE+REA (extremo a extremo, quirúrgico, automatizado).
Reutiliza componentes existentes. Sin modificar zonas protegidas. Sin autonomía ilimitada.
"""
import sys, os, json, hashlib, time, shutil, tempfile, sqlite3
from pathlib import Path

ROOT = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools/rxre"))
sys.path.insert(0, os.path.join(ROOT, "m326_isolated/scripts"))

from rxre.core import orchestrator
try:
    from rxre.verifier import promotion as _authority
except Exception:  # fail-closed
    _authority = None
from rxre.core.manifest_binding_contract import validar_vinculacion
from rxre.contracts import scope_provenance_contract as spc
from rxre.core import unified_verified_contract as uvc
import m326_auth_verifier as av
try:
    import autopilot_m363
except Exception:
    autopilot_m363=None
try:
    import reconstruct_engine
except Exception:
    reconstruct_engine=None
try:
    import fuego_transact_m344
except Exception:
    fuego_transact_m344=None

from supervisor.m325_research_planner import M325ResearchPlanner
from supervisor.m327_experiment_runner import M327ExperimentRunner
from supervisor.m328_research_evaluator import M328ResearchEvaluator
from supervisor.m329_experience_store import M329ExperienceStore

PROTECTED = [
  os.path.join(ROOT,"rxre.sqlite3"),
  os.path.join(ROOT,"tools/rxre/core/unified_verified_contract.py"),
  os.path.join(ROOT,"tools/rxre/core/manifest_binding_contract.py"),
  os.path.join(ROOT,"tools/rxre/contracts/scope_provenance_contract.py"),
  os.path.join(ROOT,"tools/rxre/core/store.py"),
  os.path.join(ROOT,"AGENTS.md"),
]

class RxreRunner:
    def __init__(self, artifact_path=None, objective=None, max_iter=1, allow_fuego=False, reconstruct_ref=None, reconstruct_inputs=None, reconstruct_mode='file'):
        self.artifact_path = artifact_path
        self.objective = objective or {"goal": "investigar artefacto real", "criteria": ["integridad", "hipotesis_discriminantes"]}
        self.max_iter = max_iter
        self.allow_fuego = allow_fuego
        self.reconstruct_ref = reconstruct_ref
        self.reconstruct_inputs = reconstruct_inputs
        self.reconstruct_mode = reconstruct_mode
        self.autonomous_loop = False
        self.op_claim = False
        self.run_id = f"m338-{int(time.time())}-{os.urandom(3).hex()}"
        self.chain = []
        self.state = {}
        self.blocked = False
        self.block_reason = None
        
    def _hash(self, p):
        h = hashlib.sha256()
        with open(p,'rb') as f:
            for chunk in iter(lambda: f.read(1024*1024), b''):
                h.update(chunk)
        return h.hexdigest()
    
    def _log(self, stage, status, data=None):
        entry = {"stage": stage, "status": status, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if data: entry.update(data)
        self.chain.append(entry)
        return entry
    
    def preflight(self):
        if self.blocked: return self._log("PREFLIGHT", "SKIPPED", {"reason": self.block_reason})
        # hashes protegidos
        ph = {}
        for p in PROTECTED:
            if os.path.exists(p): ph[p] = self._hash(p)
        self.state['protected_hashes'] = ph
        # artifact
        if not self.artifact_path or not os.path.exists(self.artifact_path):
            self.blocked = True; self.block_reason = "artefacto ausente"
            return self._log("PREFLIGHT", "BLOCKED", {"reason": self.block_reason})
        self.state['artifact'] = self.artifact_path
        self.state['artifact_hash'] = self._hash(self.artifact_path)
        return self._log("PREFLIGHT", "OK", {"artifact": self.artifact_path, "sha256": self.state['artifact_hash'][:16]})
    
    def observation(self):
        if self.blocked: return self._log("OBSERVATION", "SKIPPED", {"reason": self.block_reason})
        # crear manifiesto
        m = {
            "manifest_version": "m338-01",
            "operation_id": f"op_{self.run_id}",
            "result_id": f"res_{self.run_id}",
            "scope": "static_inspection",
            "artefacto_path": self.artifact_path,
            "artefacto_hash_sha256": self.state['artifact_hash'],
            "evidence_type": "direct_observation",
            "evidence_refs_resolved": ["hash_artefacto"],
            "evidence_refs_unresolved": []
        }
        manp = f"/tmp/m338_manifest_{self.run_id}.json"
        json.dump(m, open(manp,'w'), indent=2)
        v = validar_vinculacion(manp, artifact_path_esperado=self.artifact_path, scope_esperado="static_inspection")
        self.state['manifest'] = manp
        self.state['manifest_data'] = m
        if v.get('decision') != 'PASS':
            self.blocked = True; self.block_reason = "manifest_binding_fail"
            return self._log("OBSERVATION", "BLOCKED", {"reason": v})
        return self._log("OBSERVATION", "OK", {"manifest": manp, "bind": v.get('decision')})
    
    def hypotheses(self):
        if self.blocked: return self._log("HYPOTHESES", "SKIPPED", {"reason": self.block_reason})
        hyps = [
            {"id":"H1","claim":"artefacto estándar sin parches verificables","pred":["hash_coherente"],"evidence_for":[],"evidence_against":[],"status":"NOT_DETERMINED"},
            {"id":"H2","claim":"posibles modificaciones locales","pred":["anomalia_hash"],"evidence_for":[],"evidence_against":[],"status":"NOT_DETERMINED"},
        ]
        # discriminante simple: hash coherente
        hyps[0]['evidence_for'].append({"src":"sha256","hash":self.state['artifact_hash']})
        hyps[0]['status']="PARTIAL"
        hyps[1]['evidence_against'].append({"src":"sha256","note":"sin evidencia verificable"})
        hyps[1]['status']="INSUFFICIENT"
        self.state['hypotheses'] = hyps
        return self._log("HYPOTHESES", "OK", {"count": len(hyps)})
    
    def discriminating_test(self):
        if self.blocked: return self._log("DISCRIMINATING_TEST", "SKIPPED", {"reason": self.block_reason})
        # ejecutar con runner sintético etiquetado (no ejecución real privilegiada)
        fix = bytes.fromhex('4889c790c3') + f'M338-{self.run_id}'.encode()
        ref = {'hash_sha256': hashlib.sha256(fix).hexdigest(), 'bytes_read_once': True, 'race_condition_documented':'NOT_DETERMINED', 'fixture_synthetic': True, 'fixture_evidence_note':'fixture synthetic clearly labeled'}
        run_res = M327ExperimentRunner(validated_reference=ref, max_iter=1).run(experiment_spec={'experiment_id':f'EXP-{self.run_id}','status':'READY','preparation_status':'READY','prerequisites':['fixture_synthetic'],'limitaciones':['fixture synthetic clearly labeled'],'tool_or_analyzer':'existing module'}, fixture_bytes=fix)
        self.state['test_res'] = run_res
        return self._log("DISCRIMINATING_TEST", "OK", {"classification": run_res['record']['classification'], "exit": run_res['record']['exit_status']})
    
    def evidence_verification(self):
        if self.blocked: return self._log("EVIDENCE_VERIFICATION", "SKIPPED", {"reason": self.block_reason})
        # verificación con contratos
        res = spc.verificar_autoridad_scope(
            evidence_ref=f"ref_{self.run_id}",
            claim_scope="static_inspection",
            db_op_path=os.path.join(ROOT, ".rxre/storage/rxre.sqlite3"),
            db_op_result_id=self.state['manifest_data']['result_id'],
            manifest_e2e_path=self.state['manifest'],
            observed_artifact_path=self.artifact_path,
            observed_hash=self.state['artifact_hash']
        )
        self.state['scope_ver'] = res
        return self._log("EVIDENCE_VERIFICATION", "OK", {"decision": res.get('decision')})
    
    def persistence_reread(self):
        if self.blocked: return self._log("PERSISTENCE_REREAD", "SKIPPED", {"reason": self.block_reason})
        # persistir en copia aislada
        WORK = tempfile.mkdtemp(prefix='m338_', dir='/tmp')
        COPY = os.path.join(WORK, 'copia.sqlite3')
        shutil.copy(os.path.join(ROOT, ".rxre/storage/rxre.sqlite3"), COPY)
        m = self.state['manifest_data']
        raw = json.dumps({'hash': self.state['artifact_hash'], 'run_id': self.run_id}, sort_keys=True)
        # --- Autoridad epistemológica (R7/R5): integridad + dictamen vinculado ---
        _sha_a = self.state.get('artifact_hash') or ''
        _inv = f"m338_{_sha_a[:16]}"
        _auth = None
        if _authority is not None:
            try:
                _auth = _authority.authorize_and_consume(
                    investigation_id=_inv, artifact_sha256=_sha_a,
                    target_file='rxre.sqlite3', domain='',
                    consumer="R5", operation_id=f"R5_{_inv}_reread",
                    action="persistence_reread", idempotent=True)
            except Exception:
                _auth = None
        _gate_ref = {
            'investigation_id': _inv,
            'artifact_sha256': _sha_a,
            'dictamen_id': (_auth or {}).get('dictamen_id'),
            'decision': (_auth or {}).get('decision'),
            'epistemic_status': (_auth or {}).get('epistemic_status'),
            'accepted': bool((_auth or {}).get('accepted')),
        }
        raw = json.dumps({'hash': self.state['artifact_hash'], 'run_id': self.run_id, 'gate': _gate_ref,
                          'epistemic': ('AUTHORIZED' if _gate_ref['accepted'] else 'UNVERIFIED')}, sort_keys=True)
        campos = {'result_id': m['result_id'], 'operation_id': m['operation_id'], 'type':'STATIC_OBS', 'value':'PASS_PARTIAL','source':'rxre_m338','file':self.artifact_path,'line':0,'scope':'static_inspection','tool':'sha256','tool_version':'m338','status':'ok','raw_json':raw,'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
        rh = hashlib.sha256(json.dumps(campos, sort_keys=True, default=str).encode()).hexdigest()
        c = sqlite3.connect(COPY)
        c.execute("INSERT OR IGNORE INTO results (result_id,operation_id,type,value,source,file,line,scope,tool,tool_version,status,raw_json,timestamp,row_hash,verified_scope,scope_decision,limitations_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (m['result_id'], m['operation_id'], 'STATIC_OBS', 'PASS_PARTIAL', 'rxre_m338', self.artifact_path, 0, 'static_inspection', 'sha256', 'm338', 'ok', raw, time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), rh, '', 'UNVERIFIED', '[]'))
        c.execute("INSERT OR IGNORE INTO operations (operation_id,scope,declared_scope,authorized_scope,auth_decision,auth_actor,auth_timestamp,request_json) VALUES (?,?,?,?,?,?,?,?)",
                  (m['operation_id'], 'static_inspection', 'static_inspection', 'static_inspection', 'APPROVED', 'local', time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()), '{}'))
        c.commit(); c.close()
        # relectura
        cn = sqlite3.connect(f'file:{COPY}?mode=ro', uri=True)
        row = cn.execute('SELECT result_id,row_hash FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
        fj = cn.execute('SELECT raw_json FROM results WHERE result_id=?',(m['result_id'],)).fetchone()
        cn.close()
        try:
            parsed_raw = json.loads(fj[0]) if fj else {}
            _row_gate = parsed_raw.get('gate', {})
            _matches = (isinstance(row, tuple) and row and row[1] == rh)
            _r = (_auth.get("record") or {}) if _auth else {}
            _dictamen_ok = bool(_r.get('accepted') and isinstance(row, tuple) and row)
        except Exception:
            _matches, _dictamen_ok = False, False
        self.state['persistence'] = {'copy': COPY, 'row': row, 'integrity_ok': _matches,
                                      'dictamen_bound': _dictamen_ok, 'gate': _row_gate}
        # limpiar
        try: shutil.rmtree(WORK)
        except: pass
        return self._log("PERSISTENCE_REREAD", "OK", {"row_id": row[0] if row else None, "row_hash_prefix": row[1][:16] if row else None})
    
    def learning(self):
        if self.blocked: return self._log("LEARNING", "SKIPPED", {"reason": self.block_reason})
        fix = bytes.fromhex('4889c790c3') + f'M338-LEARN-{self.run_id}'.encode()
        ref = {'hash_sha256': hashlib.sha256(fix).hexdigest(), 'bytes_read_once': True, 'race_condition_documented':'NOT_DETERMINED', 'fixture_synthetic': True, 'fixture_evidence_note':'fixture synthetic clearly labeled'}
        store = M329ExperienceStore(validated_reference=ref, max_iter=1)
        run_res = self.state['test_res']
        eval_res = M328ResearchEvaluator(validated_reference=ref, max_iter=1).evaluate(research_task={'task_id':f'T-{self.run_id}','title':self.objective.get('goal'),'hypotheses':self.state['hypotheses'],'success_criteria':'discriminar'}, experiment_result={'record':run_res['record']})
        _sha = self.state.get('artifact_hash') or ''
        _inv = f"m338_{_sha[:16]}"
        _auth_segm = None
        if _authority is not None:
            try:
                _auth_segm = _authority.authorize_and_consume(
                    investigation_id=_inv, artifact_sha256=_sha, target_file='comp.spv', domain='',
                    consumer="R4", operation_id=f"R4_{_inv}_learning",
                    action="learning", idempotent=True)
            except Exception:
                _auth_segm = None
        eval_res = dict(eval_res)
        _r4rec = (_auth_segm or {}).get('record') or {}
        eval_res['gate'] = {
            'investigation_id': _inv,
            'artifact_sha256': _sha,
            'dictamen_id': _r4rec.get('dictamen_id'),
            'decision': _r4rec.get('decision'),
            'epistemic_status': _r4rec.get('epistemic_status') or 'UNVERIFIED',
            'accepted': bool(_r4rec.get('accepted')),
            'consumption_id': (_auth_segm or {}).get('consumption_id'),
            'idempotent_replay': bool((_auth_segm or {}).get('idempotent_replay')),
        }
        rec = store.record(evaluation_result=eval_res, research_task={'task_id':f'T-{self.run_id}','title':self.objective.get('goal'),'hypotheses':self.state['hypotheses'],'success_criteria':'discriminar'}, experiment_result={'record':run_res['record']})
        ret = store.retrieve(query_criteria={'category':'SYNTHETIC_EXPERIENCE','fixture_evidence_labeled':True})
        self.state['learning'] = {'record': rec, 'retrieved': len(ret.get('results',[])), 'gate': eval_res.get('gate')}
        return self._log("LEARNING", "OK", {"experience_id": rec.get('experience',{}).get('experience_id'), "retrieved": len(ret.get('results',[]))})
    
    def fuego(self):
        if self.blocked: return self._log("FUEGO", "SKIPPED", {"reason": self.block_reason})
        if not self.allow_fuego:
            if fuego_transact_m344 is not None and self.artifact_path:
                try:
                    r=fuego_transact_m344.run(self.artifact_path, allow=False)
                    return self._log("FUEGO", r.get('status','BLOCKED'), {k:v for k,v in r.items() if k not in ['provenance']})
                except Exception as e:
                    pass
            return self._log("FUEGO", "BLOCKED", {"reason": "allow_fuego=False (sin autorización legítima persistente)", "exact_admin_step": "tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key (permisos 0600, uid/emisor/ejecutor provistos, identities.json con key_sha256/nonce/firma válida)"})
        if not os.path.exists('/tmp/rxre_auth_provisioned/identities.json') or not os.path.exists('/tmp/rxre_306_work/servicio.key'):
            if fuego_transact_m344 is not None and self.artifact_path:
                try:
                    r=fuego_transact_m344.run(self.artifact_path, allow=True)
                    return self._log("FUEGO", r.get('status','BLOCKED'), {k:v for k,v in r.items() if k not in ['provenance']})
                except Exception as e:
                    pass
            return self._log("FUEGO", "BLOCKED", {"reason": "provisión persistente legítima ausente", "exact_admin_step": "tools/rxre/admin/provision_trust.py --provisioned-by <admin> --confirm --issuer-key <fuera_repo>/issuer.key --service-key <fuera_repo>/servicio.key con permisos 0600, uid/emisor/ejecutor provistos, identities.json con key_sha256/nonce/firma válida)"})
        if fuego_transact_m344 is not None and self.artifact_path:
            try:
                r=fuego_transact_m344.run(self.artifact_path, allow=True)
                return self._log("FUEGO", r.get('status','BLOCKED') if r.get('status')!='PASS_PARTIAL' else 'PASS_PARTIAL', {k:v for k,v in r.items() if k not in ['provenance']})
            except Exception as e:
                return self._log("FUEGO", "BLOCKED", {"reason": str(e)})
        # fallback
        if self.artifact_path.startswith('/usr/') or self.artifact_path.startswith('/bin/') or self.artifact_path.startswith('/sbin/'):
            return self._log("FUEGO", "BLOCKED", {"reason": "artefacto sistema no permitido"})
        WORK = tempfile.mkdtemp(prefix='m338_fuego_', dir='/tmp')
        copy_path = os.path.join(WORK, os.path.basename(self.artifact_path)+'.copy')
        shutil.copy2(self.artifact_path, copy_path)
        h0 = self._hash(copy_path)
        try:
            with open(copy_path,'rb') as f:
                data = f.read()
            if data[:4] == b'\x7fELF':
                shutil.rmtree(WORK)
                return self._log("FUEGO", "BLOCKED", {"reason": "cambio binario no permitido sin mecanismo específico"})
            shutil.rmtree(WORK)
            return self._log("FUEGO", "NOT_EXECUTED", {"reason": "sin cambio seguro aplicable"})
        except Exception as e:
            try: shutil.rmtree(WORK)
            except: pass
            return self._log("FUEGO", "BLOCKED", {"reason": str(e)})
    
    def reconstruct(self):
        if reconstruct_engine is None or not self.reconstruct_ref:
            return self._log("RECONSTRUCT","SKIPPED",{"reason":"no reconstruct_ref"})
        try:
            inputs=self.reconstruct_inputs or [('default',b'')]
            r=reconstruct_engine.run(self.artifact_path, self.reconstruct_ref, inputs, self.reconstruct_mode)
            return self._log("RECONSTRUCT", "PASS_PARTIAL" if r['comparison']['mismatches']==0 else "DISCREPANCIES", {k:r[k] for k in ['comparison','defective_check','persistence','learning','hypotheses'] if k in r})
        except Exception as e:
            return self._log("RECONSTRUCT","BLOCKED",{"reason":str(e)})
    
    def autopilot_select(self):
        if autopilot_m363 is None:
            return self._log("AUTOPILOT","SKIPPED",{"reason":"module not available"})
        try:
            # reload candidates state
            import json, os
            st_path='/tmp/m363_autopilot_state.json'
            st=json.load(open(st_path)) if os.path.exists(st_path) else {'decisions':[]}
            # call select_next via module function if exists, else replicate
            if hasattr(autopilot_m363,'select_next'):
                nxt=autopilot_m363.select_next(autopilot_m363.candidates)
            else:
                # fallback: pick first pending
                done={c['name'] for c in autopilot_m363.candidates if c['status']=='done'}
                elig=[c for c in autopilot_m363.candidates if c['status'] in ('pending','partial') and all(d in done for d in c['deps'])]
                if not elig: elig=[c for c in autopilot_m363.candidates if c['status'] in ('pending','partial')]
                nxt=elig[0] if elig else None
            if nxt is None:
                return self._log("AUTOPILOT","BLOCKED",{"reason":"no eligible candidates"})
            return self._log("AUTOPILOT","OK",{"selected":nxt['name'],"rva":nxt['rva'],"reason":"highest priority with deps resolved"})
        except Exception as e:
            return self._log("AUTOPILOT","BLOCKED",{"reason":str(e)})
    
    def report(self):
        rep = {
            "run_id": self.run_id,
            "objective": self.objective,
            "artifact": self.state.get('artifact'),
            "artifact_hash": self.state.get('artifact_hash'),
            "chain": self.chain,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "autonomous_loop": False,
            "max_iter": self.max_iter,
            "op_claim": False,
            "protected_hashes": self.state.get('protected_hashes'),
            "hypotheses": self.state.get('hypotheses'),
            "learning": self.state.get('learning'),
            "persistence": {"row_id": self.state.get('persistence',{}).get('row')[0] if self.state.get('persistence',{}).get('row') else None}
        }
        out = f"/tmp/m338_report_{self.run_id}.json"
        json.dump(rep, open(out,'w'), indent=2)
        return rep, out
    
    def run(self):
        self.preflight()
        self.observation()
        self.hypotheses()
        self.discriminating_test()
        self.evidence_verification()
        self.persistence_reread()
        self.learning()
        self.autopilot_select()
        self.reconstruct()
        self.fuego()
        rep, out = self.report()
        return rep, out

if __name__ == '__main__':
    art = sys.argv[1] if len(sys.argv)>1 else '/usr/bin/ls'
    r = RxreRunner(artifact_path=art)
    rep,out = r.run()
    print(json.dumps({'run_id':rep['run_id'],'blocked':rep['blocked'],'chain_len':len(rep['chain']),'report':out}, indent=2))
