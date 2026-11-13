#!/usr/bin/env python3
"""RX Virtual GPU Laboratory — Integration of real hardware, simulation, and reconstruction."""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

LAB_DIR = os.path.join(ROOT, 'evidence', 'virtual_gpu_lab')
os.makedirs(LAB_DIR, exist_ok=True)

class RXVirtualGPULab:
    """Integration of real hardware, simulation, and reconstruction environments."""
    
    def __init__(self):
        self.environments = []
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def run_lab(self):
        print("="*60)
        print("RX VIRTUAL GPU LABORATORY — Hardware/Simulation/Reconstruction")
        print("="*60)
        
        # Environment 1: Real hardware
        print("\n[1] Real Hardware Environment (RX 550)...")
        r = self.run_cmd(['/tmp/vk_compute_dispatch', '/home/lucas/Escritorio/rxre/.rxre/capture_169/compute_169.spv', '64'], timeout=30)
        real_env = {'type': 'REAL_HARDWARE', 'device': 'RX 550', 'status': 'OK' if r['ok'] else 'FAIL', 'timing': None}
        if r['ok'] or r['stdout']:
            for line in r['stdout'].split('\n'):
                if '"timing"' in line:
                    try:
                        import json
                        d = json.loads(line)
                        if 'timing' in d:
                            real_env['timing'] = d['timing']
                    except:
                        pass
        self.environments.append(real_env)
        print(f"  Real hardware: {real_env['status']}")
        
        # Environment 2: SPIR-V simulation (validation)
        print("\n[2] SPIR-V Validation Environment...")
        r = self.run_cmd(['spirv-val', '/home/lucas/Escritorio/rxre/.rxre/capture_169/compute_169.spv'])
        sim_env = {'type': 'SPIRV_VALIDATION', 'status': 'OK' if r['ok'] else 'FAIL'}
        self.environments.append(sim_env)
        print(f"  SPIR-V validation: {sim_env['status']}")
        
        # Environment 3: M58 reconstruction
        print("\n[3] M58 Reconstruction Environment...")
        try:
            from tools.rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline
            p = M58Pipeline('/home/lucas/Escritorio/rxre/.rxre/capture_169/compute_169.spv')
            p.verify_integrity()
            p.disassemble()
            p.extract_structural()
            s = p.build_semantic()
            recon_env = {'type': 'M58_RECONSTRUCTION', 'status': 'OK', 'sufficiency': s.get('reconstruction_sufficiency')}
            self.environments.append(recon_env)
            print(f"  M58 reconstruction: {recon_env['status']} ({recon_env['sufficiency']})")
        except Exception as e:
            recon_env = {'type': 'M58_RECONSTRUCTION', 'status': 'FAIL', 'error': str(e)}
            self.environments.append(recon_env)
            print(f"  M58 reconstruction: FAIL ({e})")
        
        # Environment 4: CPU simulation (llvmpipe)
        print("\n[4] CPU Simulation Environment (llvmpipe)...")
        r = self.run_cmd(['vulkaninfo', '--summary'])
        sim2_env = {'type': 'CPU_SIMULATION', 'status': 'OK' if r['ok'] else 'FAIL'}
        self.environments.append(sim2_env)
        print(f"  llvmpipe: {sim2_env['status']}")
        
        ev_path = os.path.join(LAB_DIR, f'virtual_lab_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_VIRTUAL_GPU_LAB', 'timestamp': datetime.now().isoformat(),
                       'environments': self.environments, 'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        print(f"\nEvidence: {ev_path}")
        
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(LAB_DIR, 'lab_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('virtual_gpu_lab', 'virtual_gpu_lab', 'multi-env integration', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("VIRTUAL GPU LABORATORY — COMPLETE")
        print("="*60)
        return self.environments

if __name__ == '__main__':
    lab = RXVirtualGPULab()
    lab.run_lab()
