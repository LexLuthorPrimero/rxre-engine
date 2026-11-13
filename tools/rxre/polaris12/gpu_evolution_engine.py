#!/usr/bin/env python3
"""GPU Evolution Engine — Autonomous Shader Optimization for RX 550 (Polaris 12).
Reuses existing: M58, GPU DNA, ROUTER, TIERRA, AGUA, AIRE, shader_intelligence.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, tempfile, math, re
from typing import Dict, Any, List, Optional
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))

GPU_EVOL_DIR = os.path.join(ROOT, 'evidence', 'gpu_evolution')
os.makedirs(GPU_EVOL_DIR, exist_ok=True)

VK_DISPATCH = '/tmp/vk_compute_dispatch'
VK_TEST_CORRECTED = '/tmp/vk_corrected'
SPV_PATH = os.path.join(ROOT, '.rxre/capture_169/compute_169.spv')

class GPUShaderForge:
    """Shader variant generator and transformer. Reuses shader_intelligence patterns."""
    
    def __init__(self):
        self.variants = []
        self.tested = set()
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def create_base_shader(self):
        """Create a base GLSL compute shader for optimization experiments."""
        return '''#version 450
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;
layout(set = 0, binding = 0) buffer Input { float data[]; } in_buf;
layout(set = 0, binding = 1) buffer Output { float data[]; } out_buf;
void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx < in_buf.data.length()) {
        out_buf.data[idx] = in_buf.data[idx] * 2.0 + 1.0;
    }
}
'''
    
    def transform_fma(self, glsl):
        """Apply FMA transformation: a*b+c -> fma(a,b,c)"""
        if 'in_buf.data[idx] * 2.0 + 1.0' in glsl:
            return glsl.replace('in_buf.data[idx] * 2.0 + 1.0', 'fma(in_buf.data[idx], 2.0, 1.0)'), 'fma'
        return None, None
    
    def transform_addform(self, glsl):
        """Apply add-form transformation: a*2+1 -> a+a+1"""
        if 'in_buf.data[idx] * 2.0 + 1.0' in glsl:
            return glsl.replace('in_buf.data[idx] * 2.0 + 1.0', 'in_buf.data[idx] + in_buf.data[idx] + 1.0'), 'addform'
        return None, None
    
    def transform_inline(self, glsl):
        """Inline variable"""
        if 'in_buf.data[idx] * 2.0 + 1.0' in glsl and 'float v =' not in glsl:
            return glsl.replace('out_buf.data[idx] = in_buf.data[idx] * 2.0 + 1.0;',
                              'float v = in_buf.data[idx];\n        out_buf.data[idx] = v * 2.0 + 1.0;'), 'inline'
        return None, None
    
    def transform_workgroup(self, glsl, wg_size):
        """Change workgroup size."""
        import re
        new = re.sub(r'local_size_x = \d+', f'local_size_x = {wg_size}', glsl)
        if new != glsl:
            return new, f'wg{wg_size}'
        return None, None
    
    def transform_dispatch_unroll(self, glsl):
        """Unroll the computation (if applicable)."""
        # For simple element-wise, unrolling doesn't apply meaningfully
        return None, None
    
    def generate_variants(self, base_glsl, gpu_dna=None):
        """Generate multiple semantic-equivalent variants."""
        variants = []
        # Original
        variants.append({'id': 'original', 'glsl': base_glsl, 'transforms': []})
        
        # FMA
        r = self.transform_fma(base_glsl)
        if r and r[0]:
            variants.append({'id': 'fma', 'glsl': r[0], 'transforms': [r[1]]})
        
        # Addform
        r = self.transform_addform(base_glsl)
        if r and r[0]:
            variants.append({'id': 'addform', 'glsl': r[0], 'transforms': [r[1]]})
        
        # Inline
        r = self.transform_inline(base_glsl)
        if r and r[0]:
            variants.append({'id': 'inline', 'glsl': r[0], 'transforms': [r[1]]})
        
        # Workgroup size variants
        for wg in [32, 64, 128, 256]:
            r = self.transform_workgroup(base_glsl, wg)
            if r and r[0]:
                variants.append({'id': f'wg{wg}', 'glsl': r[0], 'transforms': [r[1]]})
        
        # FMA + workgroup 128
        r = self.transform_fma(base_glsl)
        if r and r[0]:
            r2 = self.transform_workgroup(r[0], 128)
            if r2 and r2[0]:
                variants.append({'id': 'fma_wg128', 'glsl': r2[0], 'transforms': [r[1], r2[1]]})
        
        # Deduplicate by GLSL hash
        seen = set()
        unique = []
        for v in variants:
            h = hashlib.sha256(v['glsl'].encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                v['glsl_hash'] = h
                unique.append(v)
        self.variants = unique
        return unique


class GPUVariantTester:
    """Compile, execute, and benchmark shader variants on RX 550."""
    
    def __init__(self):
        import subprocess
        self._subprocess = subprocess
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = self._subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0, 'raw_stdout': r.stdout}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False, 'raw_stdout': b''}
    
    def compile_variant(self, glsl, variant_id, tmpdir):
        """Compile GLSL to SPIR-V and validate."""
        glsl_path = os.path.join(tmpdir, f'{variant_id}.comp')
        spv_path = os.path.join(tmpdir, f'{variant_id}.spv')
        with open(glsl_path, 'w') as f:
            f.write(glsl)
        
        # Compile
        r = self.run_cmd(['glslangValidator', '-V', '-S', 'comp', glsl_path, '-o', spv_path])
        if not (r['ok'] and os.path.exists(spv_path)):
            return {'compiled': False, 'reason': 'COMPILE_FAILED', 'stderr': r['stderr'][:300]}
        
        # Validate SPIR-V
        r2 = self.run_cmd(['spirv-val', spv_path])
        if not r2['ok']:
            return {'compiled': True, 'spirv_valid': False, 'reason': 'SPIRV_INVALID', 'stderr': r2['stderr'][:300]}
        
        return {'compiled': True, 'spirv_valid': True, 'spv_path': spv_path, 'glsl_path': glsl_path}
    
    def execute_variant(self, spv_path, count=1024, reps=7):
        """Execute variant on RX 550 and collect results."""
        times = []
        correct = True
        all_correct = True
        for i in range(reps):
            r = self.run_cmd(['/tmp/vk_compute_dispatch', spv_path, str(count)], timeout=30)
            if not r['ok']:
                correct = False
                continue
            for line in r['stdout'].split('\n'):
                if '"timing"' in line:
                    try:
                        t = json.loads(line)
                        if 'timing' in t:
                            times.append(t['timing']['exec'])
                    except:
                        pass
            for line in r['stdout'].split('\n'):
                if '"verification"' in line:
                    try:
                        v = json.loads(line)
                        if v.get('verification', {}).get('all_correct') != 1:
                            all_correct = False
                    except:
                        pass
        if not all_correct:
            correct = False
        
        result = {
            'functional': correct,
            'all_correct': all_correct,
            'reps': len(times),
        }
        if times:
            result['median_exec'] = sorted(times)[len(times)//2]
            result['mean_exec'] = sum(times)/len(times)
            result['min_exec'] = min(times)
            result['max_exec'] = max(times)
            result['stdev'] = (sum((x - result['mean_exec'])**2 for x in times)/len(times))**0.5 if len(times) > 1 else 0
        else:
            result['median_exec'] = None
            result['functional'] = False
        
        return result
    
    def verify_correctness(self, result, expected_func=True):
        """Verify correctness constraints."""
        if not result.get('functional', False):
            return False, 'FUNCTIONAL_FAILURE'
        if result.get('reps', 0) < 3:
            return False, 'INSUFFICIENT_REPS'
        return True, 'OK'


class GPUEvolutionEngine:
    """Autonomous GPU Evolution Engine. Orchestrates the full optimization loop."""
    
    def __init__(self):
        self.forge = GPUShaderForge()
        self.tester = GPUVariantTester()
        self.results = []
        self.knowledge = []
        self.best_variant = None
        self.baseline_median = None
        self.iteration = 0
        self.max_iterations = 5
        self.evidence_dir = os.path.join(ROOT, 'evidence', 'gpu_evolution')
        os.makedirs(self.evidence_dir, exist_ok=True)
        
        # Load GPU DNA constraints
        self.gpu_dna = self._load_gpu_dna()
        
        # Load M58
        try:
            from tools.rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline
            self.M58Pipeline = M58Pipeline
        except Exception as e:
            self.M58Pipeline = None
            print(f"M58 load warning: {e}")
        
        # Load ROUTER
        try:
            from tools.rxre.arquitectura.ROUTER import Router
            self.router = Router()
        except Exception as e:
            self.router = None
            print(f"ROUTER load warning: {e}")
        
        # Load AGUA
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            self.agua = Agua(os.path.join(self.evidence_dir, 'evolution_agua.db'))
            self.Aprendizaje = Aprendizaje
        except Exception as e:
            self.agua = None
            print(f"AGUA load warning: {e}")
    
    def _load_gpu_dna(self):
        """Load GPU DNA experimental data."""
        dna = {}
        gpu_dna_dir = os.path.join(ROOT, 'evidence', 'gpu_dna')
        if os.path.isdir(gpu_dna_dir):
            for f in os.listdir(gpu_dna_dir):
                if f.endswith('.json'):
                    try:
                        data = json.load(open(os.path.join(gpu_dna_dir, f)))
                        dna[f] = data
                    except:
                        pass
        return dna
    
    def _trace(self, decision, resultado):
        """Emit AIRE trace."""
        try:
            from tools.rxre.arquitectura import AIRE
            if hasattr(AIRE, 'emitir_traza'):
                return AIRE.emitir_traza(
                    decision=decision,
                    herramienta={'name': 'gpu_evolution_engine', 'version': '1.0'},
                    resultado=resultado
                )
        except Exception:
            pass
        return None
    
    def _persist_knowledge(self, name, data):
        """Persist optimization knowledge via AGUA."""
        if self.agua:
            try:
                def rev():
                    return True
                apr = self.Aprendizaje(
                    proposito=f'gpu_evolution_{name}',
                    procedencia='gpu_evolution_engine',
                    regla=json.dumps(data)[:500],
                    reverificar=rev,
                    confianza=0.8
                )
                return self.agua.aprender(apr)
            except Exception as e:
                print(f"AGUA persist warning: {e}")
        return None
    
    def _persist_evidence(self, name, data):
        """Persist evidence to file."""
        ev_path = os.path.join(self.evidence_dir, f'{name}_{int(time.time())}.json')
        evidence = {
            'mission': 'GPU_EVOLUTION_ENGINE',
            'timestamp': datetime.now().isoformat(),
            'iteration': self.iteration,
            'data': data,
            'restrictions': {'DB_AUTH': 'safe ops authorized', 'autonomous_loop': False},
            'source': 'real_gpu_experiment',
            'device': 'AMD Radeon RX 550 / 550 Series (RADV POLARIS12)'
        }
        with open(ev_path, 'w') as f:
            json.dump(evidence, f, indent=2)
        return ev_path
    
    def analyze_shader(self, glsl):
        """Analyze shader with M58."""
        # First compile to SPIR-V
        tmpdir = tempfile.mkdtemp(prefix='evol_')
        glsl_path = os.path.join(tmpdir, 'shader.comp')
        spv_path = os.path.join(tmpdir, 'shader.spv')
        with open(glsl_path, 'w') as f:
            f.write(glsl)
        r = self.tester.run_cmd(['glslangValidator', '-V', '-S', 'comp', glsl_path, '-o', spv_path])
        if not (r['ok'] and os.path.exists(spv_path)):
            return None, f'COMPILE_FAILED: {r["stderr"][:200]}'
        
        # M58 analysis
        if self.M58Pipeline:
            p = self.M58Pipeline(spv_path)
            p.verify_integrity()
            p.disassemble()
            p.extract_structural()
            s = p.build_semantic()
            return spv_path, s
        return spv_path, {'status': 'M58_UNAVAILABLE'}
    
    def run_evolution(self, base_glsl=None, max_variants=8):
        """Run the full evolution loop."""
        print("="*70)
        print("GPU EVOLUTION ENGINE — Autonomous Shader Optimization")
        print("="*70)
        
        if base_glsl is None:
            base_glsl = self.forge.create_base_shader()
        
        self.iteration += 1
        print(f"\n[ITERATION {self.iteration}]")
        
        # 1. Analyze base shader
        print("\n[1] Analyzing base shader with M58...")
        spv_path, semantic = self.analyze_shader(base_glsl)
        if spv_path is None:
            print(f"  Base shader analysis failed: {semantic}")
            return {'status': 'FAILED', 'reason': semantic}
        print(f"  SPIR-V: {spv_path}")
        print(f"  Semantic: {semantic.get('reconstruction_sufficiency', 'N/A')}")
        
        # 2. Generate variants
        print("\n[2] Generating variants...")
        variants = self.forge.generate_variants(base_glsl, self.gpu_dna)
        print(f"  Generated {len(variants)} unique variants")
        for v in variants:
            print(f"    - {v['id']}: {v.get('transforms', [])}")
        
        # 3. Compile and test each variant
        print("\n[3] Compiling and testing variants...")
        tmpdir = tempfile.mkdtemp(prefix='evol_')
        results = []
        
        # Test baseline first
        print("  Testing baseline...")
        base_result = self.tester.compile_variant(base_glsl, 'baseline', tmpdir)
        if base_result.get('compiled') and base_result.get('spirv_valid'):
            base_exec = self.tester.execute_variant(base_result['spv_path'], count=1024, reps=7)
            base_ok, base_reason = self.tester.verify_correctness(base_exec)
            base_result.update(base_exec)
            base_result['correct'] = base_ok
            base_result['correctness_reason'] = base_reason
            self.baseline_median = base_exec.get('median_exec')
            print(f"    baseline: correct={base_ok}, median={base_exec.get('median_exec', 'N/A')}")
        else:
            print(f"    baseline: COMPILE FAILED")
            base_result['correct'] = False
        
        results.append({'id': 'baseline', 'result': base_result})
        
        # Test each variant
        for v in variants:
            if v['id'] == 'original':
                continue
            print(f"  Testing {v['id']}...")
            var_result = self.tester.compile_variant(v['glsl'], v['id'], tmpdir)
            if var_result.get('compiled') and var_result.get('spirv_valid'):
                var_exec = self.tester.execute_variant(var_result['spv_path'], count=1024, reps=7)
                var_ok, var_reason = self.tester.verify_correctness(var_exec)
                var_result.update(var_exec)
                var_result['correct'] = var_ok
                var_result['correctness_reason'] = var_reason
                if self.baseline_median and var_exec.get('median_exec'):
                    var_result['speedup'] = self.baseline_median / var_exec['median_exec']
                    var_result['improvement_pct'] = (var_result['speedup'] - 1) * 100
                print(f"    {v['id']}: correct={var_ok}, median={var_exec.get('median_exec', 'N/A')}, speedup={var_result.get('speedup', 'N/A')}")
            else:
                print(f"    {v['id']}: COMPILE FAILED ({var_result.get('reason', 'unknown')})")
                var_result['correct'] = False
            results.append({'id': v['id'], 'result': var_result, 'variant': v})
        
        # 4. Select best
        print("\n[4] Selecting best variant...")
        valid_variants = [r for r in results if r['result'].get('correct', False) and r['result'].get('median_exec')]
        if not valid_variants:
            print("  No valid variants found")
            best = None
        else:
            valid_variants.sort(key=lambda r: r['result']['median_exec'])
            best = valid_variants[0]
            print(f"  Best: {best['id']} (median={best['result']['median_exec']:.6f}s)")
            if self.baseline_median:
                speedup = self.baseline_median / best['result']['median_exec']
                print(f"  Speedup vs baseline: {speedup:.4f}x ({(speedup-1)*100:+.2f}%)")
        
        # 5. Persist results
        print("\n[5] Persisting results...")
        self.results = results
        self.best_variant = best
        
        # Persist knowledge
        if best and best['id'] != 'baseline':
            knowledge = {
                'best_variant': best['id'],
                'speedup': best['result'].get('speedup', 1.0),
                'transforms': best.get('variant', {}).get('transforms', []),
                'median_exec': best['result'].get('median_exec'),
                'baseline_median': self.baseline_median
            }
            aid = self._persist_knowledge(f'evolution_iter{self.iteration}', knowledge)
            print(f"  AGUA aprendizaje: {aid}")
        
        # Persist evidence
        ev_data = {
            'iteration': self.iteration,
            'base_shader_hash': hashlib.sha256(base_glsl.encode()).hexdigest(),
            'variants_tested': len(results),
            'valid_variants': len(valid_variants),
            'best_variant': best['id'] if best else 'baseline',
            'best_median': best['result'].get('median_exec') if best else None,
            'baseline_median': self.baseline_median,
            'speedup': best['result'].get('speedup', 1.0) if best else 1.0,
            'results': [{ 'id': r['id'], 'correct': r['result'].get('correct', False), 'median': r['result'].get('median_exec'), 'speedup': r['result'].get('speedup') } for r in results]
        }
        ev_path = self._persist_evidence(f'evolution_iter{self.iteration}', ev_data)
        print(f"  Evidence: {ev_path}")
        
        # Emit trace
        self._trace('gpu_evolution_complete', ev_data)
        
        # Summary
        print("\n" + "="*70)
        print("GPU EVOLUTION — SUMMARY")
        print("="*70)
        print(f"  Iteration: {self.iteration}")
        print(f"  Variants tested: {len(results)}")
        print(f"  Valid variants: {len(valid_variants)}")
        print(f"  Best: {best['id'] if best else 'baseline'}")
        if best and best['id'] != 'baseline' and best['result'].get('speedup', 1) > 1.0:
            print(f"  Speedup: {best['result'].get('speedup', 1.0):.4f}x")
        else:
            print(f"  No improvement found (baseline retained)")
        print(f"  Baseline median: {self.baseline_median:.6f}s" if self.baseline_median else "  Baseline: N/A")
        print("="*70)
        
        return {
            'iteration': self.iteration,
            'variants': len(results),
            'valid': len(valid_variants),
            'best': best['id'] if best else 'baseline',
            'speedup': best['result'].get('speedup', 1.0) if best else 1.0,
            'baseline_median': self.baseline_median,
            'evidence': ev_path
        }

if __name__ == '__main__':
    engine = GPUEvolutionEngine()
    result = engine.run_evolution()
    print(f"\nResult: {json.dumps(result, indent=2)}")
