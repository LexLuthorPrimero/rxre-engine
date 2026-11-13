#!/usr/bin/env python3
"""RX Driver Observatory — GPU driver behavior, submission paths, memory management, and execution observation.
Uses root access for debugfs/amdgpu registers. Reuses existing GPU DNA and Vulkan infrastructure.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

OBS_DIR = os.path.join(ROOT, 'evidence', 'driver_observatory')
os.makedirs(OBS_DIR, exist_ok=True)

class RXDriverObservatory:
    """GPU driver behavior observation using root access."""
    
    def __init__(self):
        self.observations = []
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def sudo_cmd(self, cmd, timeout=60):
        """Run command with sudo."""
        try:
            r = subprocess.run(['bash', '-c', f'echo "123456" | sudo -S {" ".join(cmd)}'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def observe_driver_state(self):
        """Observe current driver state via debugfs."""
        print("[Driver Observatory] Observing driver state...")
        obs = {}
        
        # amdgpu info
        files = ['amdgpu_pm_info', 'amdgpu_sensors', 'amdgpu_firmware_info', 'amdgpu_vbios']
        for f in files:
            r = self.sudo_cmd(['cat', f'/sys/kernel/debug/dri/0000:01:00.0/{f}'])
            if r['ok'] and r['stdout']:
                obs[f] = r['stdout'][:500]
                print(f"  {f}: OK ({len(r['stdout'])} bytes)")
            else:
                obs[f] = 'UNAVAILABLE'
                print(f"  {f}: UNAVAILABLE")
        
        # VM info
        r = self.sudo_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_vm_info'])
        if r['ok']:
            obs['vm_info'] = r['stdout'][:1000]
            # Count BOs
            bo_count = r['stdout'].count('byte')
            obs['bo_count'] = bo_count
            print(f"  VM info: {bo_count} BOs")
        
        # GEM info
        r = self.sudo_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_gem_info'])
        if r['ok']:
            obs['gem_info'] = r['stdout'][:500]
            print(f"  GEM info: OK")
        
        # Fence info
        r = self.sudo_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_fence_info'])
        if r['ok']:
            obs['fence_info'] = r['stdout'][:500]
            print(f"  Fence info: OK")
        
        # Kernel module info
        r = self.run_cmd(['lsmod'])
        if r['ok']:
            for line in r['stdout'].split('\n'):
                if 'amdgpu' in line or 'drm' in line:
                    obs.setdefault('kernel_modules', []).append(line.strip())
        
        # Vulkan device
        r = self.run_cmd(['vulkaninfo', '--summary'])
        if r['ok']:
            for line in r['stdout'].split('\n'):
                if 'deviceName' in line or 'driverVersion' in line or 'apiVersion' in line:
                    obs.setdefault('vulkan', []).append(line.strip())
        
        self.observations.append(obs)
        return obs
    
    def observe_submission_path(self):
        """Observe command submission and execution path."""
        print("[Driver Observatory] Observing submission path...")
        obs = {}
        
        # Ring info
        for ring in ['amdgpu_ring_gfx', 'amdgpu_ring_comp_1.0.0', 'amdgpu_ring_sdma0']:
            r = self.sudo_cmd(['cat', f'/sys/kernel/debug/dri/0000:01:00.0/{ring}'])
            if r['ok']:
                # Get last few lines
                lines = r['stdout'].strip().split('\n')
                obs[ring] = lines[-5:] if lines else []
                print(f"  {ring}: {len(lines)} entries")
        
        # SA info
        r = self.sudo_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_sa_info'])
        if r['ok']:
            obs['sa_info'] = r['stdout'][:500]
        
        return obs
    
    def run_observatory(self):
        """Run full driver observatory."""
        print("="*60)
        print("RX DRIVER OBSERVATORY — GPU Driver Behavior Observation")
        print("="*60)
        
        state = self.observe_driver_state()
        submission = self.observe_submission_path()
        
        ev_path = os.path.join(OBS_DIR, f'driver_obs_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_DRIVER_OBSERVATORY', 'timestamp': datetime.now().isoformat(),
                       'driver_state': state, 'submission_path': submission,
                       'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        print(f"\nEvidence: {ev_path}")
        
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(OBS_DIR, 'obs_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('driver_observatory', 'driver_observatory', 'driver state observation', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("DRIVER OBSERVATORY — COMPLETE")
        print("="*60)
        return state

if __name__ == '__main__':
    obs = RXDriverObservatory()
    state = obs.run_observatory()
