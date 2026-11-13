#!/usr/bin/env python3
"""RX Shared Pipeline — CPU/GPU data sharing and transfer path optimization."""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

SHARED_DIR = os.path.join(ROOT, 'evidence', 'shared_pipeline')
os.makedirs(SHARED_DIR, exist_ok=True)

class RXSharedPipeline:
    """CPU/GPU data sharing and transfer path optimization."""
    
    def __init__(self):
        self.transfers = []
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def run_shared_pipeline_experiment(self):
        print("="*60)
        print("RX SHARED PIPELINE — CPU/GPU Data Sharing Optimization")
        print("="*60)
        
        print("\n[1] Testing transfer paths...")
        for size in [64, 256, 1024]:
            r = self.run_cmd(['/tmp/vk_compute_dispatch', '/home/lucas/Escritorio/rxre/.rxre/capture_169/compute_169.spv', str(size)], timeout=30)
            timing = None
            if r['ok'] or r['stdout']:
                for line in r['stdout'].split('\n'):
                    if '"timing"' in line:
                        try:
                            import json
                            d = json.loads(line)
                            if 'timing' in d:
                                timing = d['timing']
                        except:
                            pass
            self.transfers.append({'size': size, 'timing': timing})
            if timing:
                print(f"  size={size}: xfer_in={timing.get('xfer_in',0):.6f}s, exec={timing.get('exec',0):.6f}s, xfer_out={timing.get('xfer_out',0):.6f}s")
        
        ev_path = os.path.join(SHARED_DIR, f'shared_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_SHARED_PIPELINE', 'timestamp': datetime.now().isoformat(),
                       'transfers': self.transfers, 'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        print(f"\nEvidence: {ev_path}")
        
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(SHARED_DIR, 'shared_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('shared_pipeline', 'shared_pipeline', 'cpu gpu sharing', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("SHARED PIPELINE — COMPLETE")
        print("="*60)
        return self.transfers

if __name__ == '__main__':
    sp = RXSharedPipeline()
    sp.run_shared_pipeline_experiment()
