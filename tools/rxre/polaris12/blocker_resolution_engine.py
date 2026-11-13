#!/usr/bin/env python3
"""RXRE Blocker Resolution Engine — autonomous discovery, diagnosis, resolution, verification.
Reuses existing components; does not duplicate. Operates within restrictions.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys
from datetime import datetime
from typing import Dict, Any, List

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# Formal persistence directory
PERSIST_DIR = os.path.join(ROOT, 'evidence', 'rxre_blockers')
os.makedirs(PERSIST_DIR, exist_ok=True)

BLOCKER_CATEGORIES = ['TECHNICAL', 'EVIDENCE', 'AUTHORIZATION', 'HARDWARE', 'ENVIRONMENT', 'DEPENDENCY']

class Blocker:
    def __init__(self, blocker_id, category, root_cause, affected, deps, evidence, missing, legal_paths, auth, status):
        self.blocker_id = blocker_id
        self.category = category
        self.root_cause = root_cause
        self.affected_capabilities = affected
        self.dependencies = deps
        self.available_evidence = evidence
        self.missing_evidence = missing
        self.legal_resolution_paths = legal_paths
        self.required_authorization = auth
        self.resolution_attempts = []
        self.validation_result = None
        self.current_status = status
        self.created_at = datetime.utcnow().isoformat()
    
    def to_dict(self):
        return {
            'blocker_id': self.blocker_id,
            'category': self.category,
            'root_cause': self.root_cause,
            'affected_capabilities': self.affected_capabilities,
            'dependencies': self.dependencies,
            'available_evidence': self.available_evidence,
            'missing_evidence': self.missing_evidence,
            'legal_resolution_paths': self.legal_resolution_paths,
            'required_authorization': self.required_authorization,
            'resolution_attempts': self.resolution_attempts,
            'validation_result': self.validation_result,
            'current_status': self.current_status,
            'created_at': self.created_at
        }

class BlockerResolutionEngine:
    def __init__(self):
        self.blockers = {}
        self.state_path = os.path.join(PERSIST_DIR, 'blocker_state.json')
        self.load_state()
    
    def load_state(self):
        if os.path.isfile(self.state_path):
            try:
                with open(self.state_path) as f:
                    data = json.load(f)
                for bid, bdata in data.get('blockers', {}).items():
                    b = Blocker(
                        bdata['blocker_id'], bdata['category'], bdata['root_cause'],
                        bdata['affected_capabilities'], bdata['dependencies'],
                        bdata['available_evidence'], bdata['missing_evidence'],
                        bdata['legal_resolution_paths'], bdata['required_authorization'],
                        bdata['current_status']
                    )
                    b.resolution_attempts = bdata.get('resolution_attempts', [])
                    b.validation_result = bdata.get('validation_result')
                    b.created_at = bdata.get('created_at', b.created_at)
                    self.blockers[bid] = b
            except Exception:
                pass
    
    def save_state(self):
        data = {
            'timestamp': datetime.utcnow().isoformat(),
            'blockers': {bid: b.to_dict() for bid, b in self.blockers.items()}
        }
        with open(self.state_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def discover_blockers(self):
        """Discover blockers from real state."""
        # GPU_READBACK_42
        self.blockers['GPU_READBACK_42'] = Blocker(
            'GPU_READBACK_42', 'HARDWARE',
            'Vulkan compute shader readback returns 0 instead of 42; root cause unresolved (memory coherence/visibility issue)',
            ['gpu_compute', 'shader_execution', 'rx550_driver'],
            ['VULKAN_RUNTIME', 'RADV_DRIVER'],
            ['/tmp/rxre_027_evidence.json', '/home/lucas/Escritorio/rxre/vk_test/vk_compute_test_fixed2.c'],
            ['root_cause_of_zero_readback', 'memory_visibility_proof', 'independent_gpu_execution'],
            ['Vulkan validation layers', 'application-level instrumentation', 'shader input/output comparison', 'public reproducible tools'],
            'W5 (root/debugfs/UMR) for low-level driver inspection',
            'BLOCKED'
        )
        
        # W5
        self.blockers['W5'] = Blocker(
            'W5', 'ENVIRONMENT',
            'No root access; debugfs/UMR/MMIO unavailable in current environment',
            ['hardware_introspection', 'gpu_register_access', 'driver_debug'],
            [],
            ['/home/lucas/Escritorio/rxre/.rxre/capture_166/logs/'],
            ['root_access', 'debugfs_mount', 'umr_tool'],
            ['Vulkan validation layers', 'application-level instrumentation', 'DRM user-space interfaces', 'shader I/O comparison'],
            'root/sudo for debugfs/UMR/MMIO',
            'BLOCKED'
        )
        
        # DB_AUTH
        self.blockers['DB_AUTH'] = Blocker(
            'DB_AUTH_ACTOR_M294', 'AUTHORIZATION',
            'Authorization mechanism for VERIFIED persistence not found; DB_AUTH_ACTOR_M294 BLOCKED',
            ['persistence_verified', 'op_claim', 'schema_modification'],
            [],
            ['/home/lucas/Escritorio/rxre/rxre.sqlite3', '/home/lucas/Escritorio/rxre/core/store.py'],
            ['authorization_mechanism', 'DB_AUTH_ACTOR_M294 resolution'],
            ['File-based evidence persistence (already implemented)', 'Independent verification without DB write'],
            'DB_AUTH_ACTOR_M294 unblock + DBOP_SCHEMA_M290 verification',
            'BLOCKED'
        )
        
        # PUERTA_CONTESTED
        self.blockers['PUERTA_CONTESTED'] = Blocker(
            'PUERTA_CONTESTED', 'EVIDENCE',
            'Independent reviewer (condition 3) not yet assigned; CONTESTED state',
            ['mission_closure', 'acceptance_gate'],
            ['EVIDENCE', 'VALIDATION'],
            ['/home/lucas/Escritorio/rxre/docs/PUERTA_CORR7.md'],
            ['independent_reviewer', 'formal_review_process'],
            ['Prepare complete evidence package', 'Document all verification steps', 'Hash all artifacts'],
            'Human reviewer assignment',
            'BLOCKED'
        )
        
        # POLARIS-021 grep
        # Check current status
        grep_status = 'RESOLVED' if os.path.isfile('/tmp/polaris021_results.json') and json.load(open('/tmp/polaris021_results.json')).get('grep_differential_equiv') == '4/4' else 'PARTIAL'
        self.blockers['POLARIS021_GREP'] = Blocker(
            'POLARIS021_GREP', 'TECHNICAL',
            'GNU grep vs reconstructed implementation semantic differences (ignore_case, line_numbers, invert)',
            ['grep_reconstruction', 'semantic_completeness'],
            [],
            ['/tmp/polaris021_results.json', '/home/lucas/Escritorio/rxre/tools/rxre/polaris12/semantic_completeness.py'],
            [],
            ['Fix arg parsing', 'Fix output formatting', 'Validate all 4 cases'],
            None,
            'RESOLVED' if grep_status == 'RESOLVED' else 'PARTIAL'
        )
        
        # ALMA PARTIAL
        self.blockers['ALMA_PARTIAL'] = Blocker(
            'ALMA_PARTIAL', 'EVIDENCE',
            'ALMA evaluators created but some criteria remain PARTIAL (idempotency, reproducibility, v3 discriminant tests, falsification tests)',
            ['closure_evaluation', 'mission_completion'],
            ['M58_EXECUTION', 'EVIDENCE'],
            ['/home/lucas/Escritorio/rxre/evidence/m58/', '/home/lucas/Escritorio/rxre/tools/rxre/arquitectura/alma_m58_evaluators.py'],
            ['full_idempotency_test_suite', 'independent_third_party_reproduction', 'full_v3_discriminant_suite', 'adversarial_falsification_tests'],
            ['Reuse existing test architecture', 'Execute discriminant tests', 'Document results'],
            None,
            'PARTIAL'
        )
        
        self.save_state()
    
    def attempt_resolution(self, blocker_id, dry_run=False):
        """Attempt to resolve a blocker."""
        b = self.blockers.get(blocker_id)
        if not b:
            return {'error': 'blocker not found'}
        
        attempt = {
            'timestamp': datetime.utcnow().isoformat(),
            'blocker_id': blocker_id,
            'action': None,
            'result': None
        }
        
        if b.current_status == 'RESOLVED':
            attempt['result'] = 'already resolved'
            b.resolution_attempts.append(attempt)
            self.save_state()
            return attempt
        
        if b.category in ('HARDWARE', 'AUTHORIZATION', 'ENVIRONMENT'):
            # Cannot resolve programmatically
            attempt['action'] = 'diagnose_only'
            attempt['result'] = f'Cannot resolve {b.category} blocker programmatically; requires external authorization/hardware'
            b.resolution_attempts.append(attempt)
            self.save_state()
            return attempt
        
        if blocker_id == 'POLARIS021_GREP':
            # Already resolved
            attempt['action'] = 'verify'
            # Re-run semantic completeness
            r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/rxre/polaris12/semantic_completeness.py')], capture_output=True, text=True)
            attempt['result'] = 'verified' if r.returncode == 0 else 'failed'
            b.current_status = 'RESOLVED' if r.returncode == 0 else 'PARTIAL'
            b.resolution_attempts.append(attempt)
            self.save_state()
            return attempt
        
        if blocker_id == 'ALMA_PARTIAL':
            # Try to improve with available evidence
            attempt['action'] = 're-evaluate with latest evidence'
            try:
                from tools.rxre.arquitectura.alma_m58_evaluators import M58ALMAEvaluators
                e = M58ALMAEvaluators()
                res = e.evaluar_todas()
                por_estado = {}
                for r in res:
                    por_estado[r['status']] = por_estado.get(r['status'], 0) + 1
                attempt['result'] = f'evaluated: {por_estado}'
                # Update status based on results
                if por_estado.get('PROVEN', 0) > 0:
                    b.current_status = 'PARTIAL'  # Still partial but improved
                b.validation_result = por_estado
            except Exception as ex:
                attempt['result'] = f'error: {ex}'
            b.resolution_attempts.append(attempt)
            self.save_state()
            return attempt
        
        if blocker_id == 'PUERTA_CONTESTED':
            # Prepare evidence package
            attempt['action'] = 'prepare_evidence_package'
            try:
                ev_dir = os.path.join(ROOT, 'evidence', 'puerta')
                os.makedirs(ev_dir, exist_ok=True)
                # Collect all evidence
                evidence_files = []
                for root, dirs, files in os.walk(os.path.join(ROOT, 'evidence')):
                    for f in files:
                        if f.endswith('.json'):
                            evidence_files.append(os.path.join(root, f))
                pkg = {
                    'mission': 'PUERTA_EVIDENCE_PACKAGE',
                    'timestamp': datetime.utcnow().isoformat(),
                    'evidence_files': evidence_files,
                    'hashes': {f: hashlib.sha256(open(f,'rb').read()).hexdigest() for f in evidence_files if os.path.isfile(f)},
                    'restrictions': {'DB_AUTH': 'BLOCKED', 'W5': 'BLOCKED', 'autonomous_loop': False},
                    'note': 'Evidence package prepared; independent reviewer required for condition 3'
                }
                pkg_path = os.path.join(ev_dir, 'PUERTA_EVIDENCE_PACKAGE.json')
                with open(pkg_path, 'w') as f:
                    json.dump(pkg, f, indent=2)
                attempt['result'] = f'evidence package prepared: {pkg_path}'
            except Exception as ex:
                attempt['result'] = f'error: {ex}'
            b.resolution_attempts.append(attempt)
            self.save_state()
            return attempt
        
        attempt['result'] = 'no resolution path implemented'
        b.resolution_attempts.append(attempt)
        self.save_state()
        return attempt
    
    def run_autonomous_cycle(self, max_iterations=5):
        """Run autonomous blocker resolution cycle."""
        print("="*70)
        print("BLOCKER RESOLUTION ENGINE — AUTONOMOUS CYCLE")
        print("="*70)
        
        self.discover_blockers()
        print(f"\nDiscovered {len(self.blockers)} blockers")
        
        # Sort by priority: TECHNICAL first, then EVIDENCE, then others
        priority = {'TECHNICAL': 0, 'EVIDENCE': 1, 'DEPENDENCY': 2, 'ENVIRONMENT': 3, 'HARDWARE': 4, 'AUTHORIZATION': 5}
        sorted_blockers = sorted(self.blockers.keys(), key=lambda x: priority.get(self.blockers[x].category, 99))
        
        for i, bid in enumerate(sorted_blockers[:max_iterations]):
            b = self.blockers[bid]
            print(f"\n[{i+1}] Processing: {bid} ({b.category}) - status: {b.current_status}")
            if b.current_status == 'RESOLVED':
                print(f"  Already resolved, skipping")
                continue
            result = self.attempt_resolution(bid)
            print(f"  Result: {result.get('result', 'N/A')}")
            print(f"  New status: {b.current_status}")
        
        # Save final state
        self.save_state()
        
        # Summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        by_status = {}
        for bid, b in self.blockers.items():
            by_status[b.current_status] = by_status.get(b.current_status, 0) + 1
            print(f"  {bid}: {b.current_status} ({b.category})")
        print(f"\nBy status: {by_status}")
        print(f"State saved: {self.state_path}")
        
        # Generate report
        report = {
            'mission': 'BLOCKER_RESOLUTION_ENGINE',
            'timestamp': time.time(),
            'blockers': {bid: b.to_dict() for bid, b in self.blockers.items()},
            'by_status': by_status,
            'restrictions': {'DB_AUTH': 'BLOCKED', 'W5': 'BLOCKED', 'autonomous_loop': False},
            'protections': {
                'rxre.sqlite3': hashlib.sha256(open(os.path.join(ROOT, 'rxre.sqlite3'), 'rb').read()).hexdigest(),
                'compute_169.spv': hashlib.sha256(open(os.path.join(ROOT, '.rxre/capture_169/compute_169.spv'), 'rb').read()).hexdigest(),
            }
        }
        report_path = os.path.join(PERSIST_DIR, 'BLOCKER_RESOLUTION_REPORT.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report: {report_path}")
        return report

if __name__ == '__main__':
    engine = BlockerResolutionEngine()
    report = engine.run_autonomous_cycle()
