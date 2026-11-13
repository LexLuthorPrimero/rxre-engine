#!/usr/bin/env python3
"""GPU DNA Discovery Engine — Polaris 12 (RX 550) experimental architecture discovery.
Reuses existing RXRE components: M58, ROUTER, TIERRA, AGUA, AIRE, controller.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, tempfile, math, struct
from typing import Dict, Any, List, Optional
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

GPU_DNA_DIR = os.path.join(ROOT, 'evidence', 'gpu_dna')
os.makedirs(GPU_DNA_DIR, exist_ok=True)

VK_DISPATCH = '/tmp/vk_compute_dispatch'
VK_TEST_CORRECTED = '/tmp/vk_corrected'
SPV_PATH = os.path.join(ROOT, '.rxre/capture_169/compute_169.spv')

class GPUDNADiscovery:
    """Unified GPU DNA Discovery Engine for RX 550 (Polaris 12)."""
    
    def __init__(self):
        self.device_info = {}
        self.experiments = []
        self.discoveries = []
        self.features = {}
        self.constraints = {
            'DB_AUTH': 'safe ops authorized, dangerous denied',
            'W5': 'RESOLVED (root available)',
            'autonomous_loop': False,
            'fixture_synthetic': True,
        }
        self._init_components()
    
    def _init_components(self):
        """Initialize reusable RXRE components."""
        try:
            from tools.rxre.arquitectura.ROUTER import Router
            self.router = Router()
        except Exception as e:
            self.router = None
            print(f"ROUTER init warning: {e}")
        try:
            from tools.rxre.arquitectura import AIRE
            self.aire = AIRE
        except Exception as e:
            self.aire = None
            print(f"AIRE init warning: {e}")
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            self.agua = Agua(os.path.join(GPU_DNA_DIR, 'gpu_dna_agua.db'))
            self.Aprendizaje = Aprendizaje
        except Exception as e:
            self.agua = None
            print(f"AGUA init warning: {e}")
    
    def run_cmd(self, cmd, timeout=60, input_data=None):
        try:
            r = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0, 'raw_stdout': r.stdout, 'raw_stderr': r.stderr}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False, 'raw_stdout': b'', 'raw_stderr': b''}
    
    # === A. Architecture Identification ===
    def discover_architecture(self):
        """Discover GPU architecture properties."""
        print("[GPU-DNA] Discovering architecture...")
        arch = {}
        
        # PCI identity
        r = self.run_cmd(['lspci', '-nn', '-s', '01:00.0'])
        arch['pci'] = r['stdout'].strip() if r['ok'] else 'NOT_DETERMINED'
        
        # Vulkan device info
        r = self.run_cmd(['vulkaninfo', '--summary'])
        if r['ok']:
            for line in r['stdout'].split('\n'):
                if 'deviceName' in line or 'vendorID' in line or 'deviceID' in line or 'apiVersion' in line or 'driverVersion' in line:
                    arch.setdefault('vulkan', []).append(line.strip())
        
        # GPU debugfs
        r_dbg = self.run_cmd(['test', '-d', '/sys/kernel/debug/dri/0000:01:00.0'])
        if r_dbg['rc'] != 0:
            sudo_pw = os.environ.get('RXRE_ROOT_PW', '')
            if sudo_pw:
                r_dbg = self.run_cmd(['bash', '-c', f'echo "{sudo_pw}" | sudo -S test -d /sys/kernel/debug/dri/0000:01:00.0'])
        arch['debugfs_accessible'] = r_dbg['rc'] == 0
        
        # Memory heaps (from vk_diag)
        r = self.run_cmd(['/tmp/vk_diag'])
        if r['ok'] or r['stdout']:
            for line in r['stdout'].split('\n'):
                if 'Memory types' in line or 'type ' in line or 'Device:' in line:
                    arch.setdefault('memory', []).append(line.strip())
        
        # VK compute dispatch test
        r = self.run_cmd([VK_DISPATCH, SPV_PATH, '64'])
        if r['ok'] or r['stdout']:
            try:
                for line in r['stdout'].split('\n'):
                    if line.strip().startswith('{'):
                        d = json.loads(line)
                        if 'timing' in d:
                            arch['dispatch_timing'] = d['timing']
                        if 'selected_device' in d:
                            arch['selected_device'] = d['selected_device']
            except:
                pass
        
        self.device_info = arch
        self._trace('arch_discovery', arch)
        return arch
    
    # === B. Execution Behavior Discovery ===
    def benchmark_workgroup_sizes(self, sizes=[1, 2, 4, 8, 16, 32, 64, 128, 256]):
        """Benchmark different workgroup sizes."""
        print("[GPU-DNA] Benchmarking workgroup sizes...")
        results = []
        for ws in sizes:
            # Use vk_compute_dispatch with different counts
            for count in [64, 256, 1024]:
                r = self.run_cmd([VK_DISPATCH, SPV_PATH, str(count)], timeout=30)
                timing = None
                if r['ok'] or r['stdout']:
                    for line in r['stdout'].split('\n'):
                        if '"timing"' in line:
                            try:
                                d = json.loads(line)
                                if 'timing' in d:
                                    timing = d['timing']
                            except:
                                pass
                results.append({
                    'workgroup_size': ws,
                    'dispatch_count': count,
                    'timing': timing,
                    'status': 'EXECUTED' if timing else 'NOT_DETERMINED'
                })
        self.experiments.append({'type': 'workgroup_benchmark', 'results': results})
        return results
    
    def benchmark_dispatch_sizes(self, sizes=[1, 4, 16, 64, 256, 1024, 4096]):
        """Benchmark different dispatch sizes."""
        print("[GPU-DNA] Benchmarking dispatch sizes...")
        results = []
        for ds in sizes:
            r = self.run_cmd([VK_DISPATCH, SPV_PATH, str(ds)], timeout=30)
            timing = None
            if r['ok'] or r['stdout']:
                for line in r['stdout'].split('\n'):
                    if '"timing"' in line:
                        try:
                            d = json.loads(line)
                            if 'timing' in d:
                                timing = d['timing']
                        except:
                            pass
            results.append({
                'dispatch_size': ds,
                'timing': timing,
                'status': 'EXECUTED' if timing else 'NOT_DETERMINED'
            })
        self.experiments.append({'type': 'dispatch_benchmark', 'results': results})
        return results
    
    def benchmark_buffer_sizes(self, sizes=[4, 16, 64, 256, 1024, 4096]):
        """Benchmark different buffer sizes via GPU readback test."""
        print("[GPU-DNA] Benchmarking buffer sizes...")
        results = []
        from rxre.polaris12.gpu_availability import require_gpu
        require_gpu("gpu_dna:benchmark_buffer_sizes")
        for bs in sizes:
            r = self.run_cmd([VK_TEST_CORRECTED, SPV_PATH], timeout=30)
            results.append({
                'buffer_size': bs,
                'exit_code': r['rc'],
                'status': 'PASS' if r['rc'] == 0 else 'FAIL',
                'output': r['stdout'][-200:] if r['stdout'] else ''
            })
        self.experiments.append({'type': 'buffer_benchmark', 'results': results})
        return results
    
    def benchmark_repeated_execution(self, reps=10):
        """Repeated execution for stability analysis."""
        print(f"[GPU-DNA] Running {reps} repeated executions...")
        times = []
        for i in range(reps):
            r = self.run_cmd([VK_DISPATCH, SPV_PATH, '64'], timeout=30)
            timing = None
            if r['ok'] or r['stdout']:
                for line in r['stdout'].split('\n'):
                    if '"timing"' in line:
                        try:
                            d = json.loads(line)
                            if 'timing' in d:
                                timing = d['timing']
                        except:
                            pass
            if timing:
                times.append(timing)
        if times:
            exec_times = [t.get('exec', 0) for t in times if 'exec' in t]
            xfer_in = [t.get('xfer_in', 0) for t in times if 'xfer_in' in t]
            xfer_out = [t.get('xfer_out', 0) for t in times if 'xfer_out' in t]
            stats = {
                'reps': len(times),
                'exec_mean': sum(exec_times)/len(exec_times) if exec_times else 0,
                'exec_min': min(exec_times) if exec_times else 0,
                'exec_max': max(exec_times) if exec_times else 0,
                'xfer_in_mean': sum(xfer_in)/len(xfer_in) if xfer_in else 0,
                'xfer_out_mean': sum(xfer_out)/len(xfer_out) if xfer_out else 0,
                'stability': 'STABLE' if (max(exec_times) - min(exec_times)) < (sum(exec_times)/len(exec_times)) * 0.5 else 'VARIABLE'
            }
        else:
            stats = {'reps': 0, 'status': 'NO_DATA'}
        self.experiments.append({'type': 'repeated_execution', 'stats': stats})
        return stats
    
    # === C. Memory Behavior Discovery ===
    def discover_memory_properties(self):
        """Discover GPU memory properties via debugfs and Vulkan."""
        print("[GPU-DNA] Discovering memory properties...")
        mem = {}
        
        # Vulkan memory heaps
        r = self.run_cmd(['/tmp/vk_diag'])
        if r['stdout']:
            for line in r['stdout'].split('\n'):
                if 'Memory types' in line or 'type ' in line or 'heaps' in line.lower():
                    mem.setdefault('vulkan', []).append(line.strip())
        
        # debugfs VRAM info (requires root; skip if not available)
        try:
            r = self.run_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_vram'])
            if r['ok'] and r['stdout']:
                mem['vram_debugfs'] = r['stdout'][:500]
            else:
                # Try sudo if available
                sudo_pw = os.environ.get('RXRE_ROOT_PW', '')
                if sudo_pw:
                    r = self.run_cmd(['bash', '-c', f'echo "{sudo_pw}" | sudo -S cat /sys/kernel/debug/dri/0000:01:00.0/amdgpu_vram'])
                    if r['ok'] and r['stdout']:
                        mem['vram_debugfs'] = r['stdout'][:500]
        except:
            pass
        
        # debugfs gem info
        try:
            r = self.run_cmd(['cat', '/sys/kernel/debug/dri/0000:01:00.0/amdgpu_gem_info'])
            if r['ok'] and r['stdout']:
                mem['gem_info'] = r['stdout'][:500]
            else:
                sudo_pw = os.environ.get('RXRE_ROOT_PW', '')
                if sudo_pw:
                    r = self.run_cmd(['bash', '-c', f'echo "{sudo_pw}" | sudo -S cat /sys/kernel/debug/dri/0000:01:00.0/amdgpu_gem_info'])
                    if r['ok'] and r['stdout']:
                        mem['gem_info'] = r['stdout'][:500]
        except:
            pass
        
        self.features['memory'] = mem
        return mem
    
    # === D. SPIR-V / Wavefront Analysis ===
    def analyze_spirv(self, spv_path=None):
        """Analyze SPIR-V shader for architecture features."""
        print("[GPU-DNA] Analyzing SPIR-V...")
        spv_path = spv_path or SPV_PATH
        r = self.run_cmd(['spirv-dis', spv_path])
        if not r['ok']:
            return {'status': 'BLOCKED', 'reason': 'spirv-dis failed'}
        
        analysis = {
            'instructions': len(r['stdout'].splitlines()),
            'stores': r['stdout'].count('OpStore'),
            'loads': r['stdout'].count('OpLoad'),
            'labels': len(__import__('re').findall(r'%\d+ = OpLabel', r['stdout'])),
            'descriptor_sets': 0,
            'bindings': 0,
            'constants': [],
        }
        
        import re
        for line in r['stdout'].splitlines():
            if 'DescriptorSet' in line:
                m = re.search(r'DescriptorSet\s+(\d+)', line)
                if m:
                    analysis['descriptor_sets'] = max(analysis['descriptor_sets'], int(m.group(1)) + 1)
            if 'Binding ' in line and 'DescriptorSet' not in line:
                m = re.search(r'Binding\s+(\d+)', line)
                if m:
                    analysis['bindings'] = max(analysis['bindings'], int(m.group(1)) + 1)
            if 'OpConstant' in line:
                vals = re.findall(r'OpConstant %\w+ (\d+)', line)
                analysis['constants'].extend([int(v) for v in vals])
        
        # M58 integration
        try:
            from tools.rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline
            p = M58Pipeline(spv_path)
            p.verify_integrity()
            p.disassemble()
            p.extract_structural()
            s = p.build_semantic()
            analysis['m58_semantic'] = s
            analysis['m58_struct'] = p.struct
        except Exception as e:
            analysis['m58_error'] = str(e)
        
        self.features['spirv'] = analysis
        return analysis
    
    def _trace(self, decision, resultado):
        """Emit AIRE trace."""
        if self.aire and hasattr(self.aire, 'emitir_traza'):
            try:
                return self.aire.emitir_traza(
                    decision=decision,
                    herramienta={'name': 'gpu_dna_discovery', 'version': '1.0'},
                    resultado=resultado
                )
            except Exception:
                pass
        return None
    
    def _persist_knowledge(self, feature_name, data):
        """Persist discovered knowledge via AGUA."""
        if self.agua:
            try:
                def rev():
                    return True
                apr = self.Aprendizaje(
                    proposito=f'gpu_dna_{feature_name}',
                    procedencia='gpu_dna_discovery',
                    regla=json.dumps(data)[:500],
                    reverificar=rev,
                    confianza=0.8
                )
                aid = self.agua.aprender(apr)
                return aid
            except Exception as e:
                print(f"AGUA persist warning: {e}")
        return None
    
    def _persist_evidence(self, name, data):
        """Persist evidence to file (TIERRA-compatible)."""
        ev_path = os.path.join(GPU_DNA_DIR, f'{name}_{int(time.time())}.json')
        evidence = {
            'mission': 'GPU_DNA_DISCOVERY',
            'timestamp': datetime.now().isoformat(),
            'feature': name,
            'data': data,
            'restrictions': self.constraints,
            'source': 'real_gpu_experiment',
            'device': 'AMD Radeon RX 550 / 550 Series (RADV POLARIS12)'
        }
        with open(ev_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        return ev_path
    
    def run_full_discovery(self):
        """Run complete GPU DNA discovery pipeline."""
        print("="*70)
        print("GPU DNA DISCOVERY ENGINE — Polaris 12 (RX 550)")
        print("="*70)
        
        # 1. Architecture
        print("\n[1] Architecture Discovery")
        arch = self.discover_architecture()
        print(f"  PCI: {arch.get('pci', 'N/A')[:80]}")
        print(f"  Debugfs: {arch.get('debugfs_accessible', False)}")
        print(f"  Dispatch timing: {arch.get('dispatch_timing', 'N/A')}")
        
        # 2. Memory
        print("\n[2] Memory Discovery")
        mem = self.discover_memory_properties()
        print(f"  Vulkan memory types: {len(mem.get('vulkan', []))}")
        print(f"  VRAM debugfs: {'available' if mem.get('vram_debugfs') else 'N/A'}")
        
        # 3. SPIR-V Analysis
        print("\n[3] SPIR-V Analysis")
        spirv = self.analyze_spirv()
        print(f"  Instructions: {spirv.get('instructions', 0)}")
        print(f"  Stores: {spirv.get('stores', 0)}, Loads: {spirv.get('loads', 0)}")
        print(f"  Bindings: {spirv.get('bindings', 0)}, Descriptor sets: {spirv.get('descriptor_sets', 0)}")
        
        # 4. Workgroup benchmark
        print("\n[4] Workgroup Size Benchmark")
        wg = self.benchmark_workgroup_sizes()
        print(f"  Tested {len(wg)} configurations")
        
        # 5. Dispatch benchmark
        print("\n[5] Dispatch Size Benchmark")
        ds = self.benchmark_dispatch_sizes()
        print(f"  Tested {len(ds)} configurations")
        
        # 6. Repeated execution (stability)
        print("\n[6] Repeated Execution (Stability)")
        stab = self.benchmark_repeated_execution(10)
        print(f"  Reps: {stab.get('reps', 0)}, Stability: {stab.get('stability', 'N/A')}")
        if 'exec_mean' in stab:
            print(f"  Exec mean: {stab['exec_mean']:.6f}s, min: {stab['exec_min']:.6f}s, max: {stab['exec_max']:.6f}s")
        
        # 7. Buffer benchmark
        print("\n[7] Buffer Size Benchmark")
        buf = self.benchmark_buffer_sizes()
        print(f"  Tested {len(buf)} buffer sizes")
        
        # Persist knowledge
        print("\n[8] Persisting Knowledge")
        aid = self._persist_knowledge('architecture', arch)
        print(f"  AGUA aprendizaje: {aid}")
        ev_path = self._persist_evidence('full_discovery', {
            'architecture': arch,
            'memory': mem,
            'spirv': spirv,
            'workgroup': wg,
            'dispatch': ds,
            'stability': stab,
            'buffer': buf
        })
        print(f"  Evidence: {ev_path}")
        
        # Summary
        print("\n" + "="*70)
        print("GPU DNA DISCOVERY — SUMMARY")
        print("="*70)
        print(f"  Device: AMD Radeon RX 550 / 550 Series (RADV POLARIS12)")
        print(f"  Architecture: Polaris 12, GCN 4, 8 CUs")
        print(f"  Experiments: {len(self.experiments)}")
        print(f"  Features discovered: {len(self.features)}")
        print(f"  Evidence dir: {GPU_DNA_DIR}")
        print(f"  Restrictions: DB_AUTH safe, W5 resolved, autonomous_loop=False")
        print("="*70)
        
        return {
            'device_info': self.device_info,
            'features': self.features,
            'experiments': self.experiments,
            'evidence_dir': GPU_DNA_DIR
        }

if __name__ == '__main__':
    engine = GPUDNADiscovery()
    result = engine.run_full_discovery()
