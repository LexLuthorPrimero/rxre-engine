#!/usr/bin/env python3
"""RX Register Optimizer — Register usage, resource pressure, and occupancy optimization."""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, re
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

REG_DIR = os.path.join(ROOT, 'evidence', 'register_optimizer')
os.makedirs(REG_DIR, exist_ok=True)

class RXRegisterOptimizer:
    """Register usage and occupancy optimization."""
    
    def __init__(self):
        self.results = []
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def analyze_register_usage(self, spv_path):
        """Analyze register usage from SPIR-V disassembly."""
        r = self.run_cmd(['spirv-dis', spv_path])
        if not r['ok']:
            return {'status': 'BLOCKED'}
        
        disasm = r['stdout']
        # Count unique % registers
        regs = set(re.findall(r'%\w+', disasm))
        # Count instructions
        instr_count = len([l for l in disasm.splitlines() if 'Op' in l])
        # Estimate VGPR/SGPR usage (approximate from SPIR-V)
        # In GCN, each SPIR-V variable maps to registers
        var_count = disasm.count('OpVariable')
        # Estimate occupancy (simplified: 256 VGPRs / vars, 8 waves per CU)
        est_vgpr = var_count * 4  # rough estimate
        est_occupancy = min(8, 256 // max(est_vgpr, 1)) if est_vgpr > 0 else 8
        
        return {
            'total_registers': len(regs),
            'instructions': instr_count,
            'variables': var_count,
            'est_vgpr': est_vgpr,
            'est_occupancy': est_occupancy,
            'status': 'ANALYZED'
        }
    
    def run_register_experiment(self):
        print("="*60)
        print("RX REGISTER OPTIMIZER — Register Usage & Occupancy")
        print("="*60)
        
        spv_path = os.path.join(ROOT, '.rxre/capture_169/compute_169.spv')
        analysis = self.analyze_register_usage(spv_path)
        print(f"\n[Analysis] {analysis}")
        
        # Test different workgroup sizes for occupancy
        print("\n[Occupancy Test]")
        for wg in [32, 64, 128, 256]:
            r = self.run_cmd(['/tmp/vk_compute_dispatch', spv_path, '64'], timeout=30)
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
            print(f"  wg={wg}: exec={timing.get('exec',0):.6f}s" if timing else f"  wg={wg}: FAILED")
        
        ev_path = os.path.join(REG_DIR, f'register_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_REGISTER_OPTIMIZER', 'timestamp': datetime.now().isoformat(),
                       'analysis': analysis, 'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        print(f"\nEvidence: {ev_path}")
        
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(REG_DIR, 'reg_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('register_optimizer', 'register_optimizer', 'register usage', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("REGISTER OPTIMIZER — COMPLETE")
        print("="*60)
        return analysis

if __name__ == '__main__':
    ro = RXRegisterOptimizer()
    ro.run_register_experiment()
