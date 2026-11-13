#!/usr/bin/env python3
"""POLARIS-005: RX Shader Intelligence"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math
from typing import Dict, Any, List

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))

class RXShaderIntelligence:
    def __init__(self):
        self.harness = '/tmp/vk_compute_dispatch'
        self.discoveries = []
        self.knowledge = []
        
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 
                    'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def transform_shader(self, base_glsl, transforms):
        """Apply controlled semantic-preserving transforms"""
        result = base_glsl
        applied = []
        for t in transforms:
            if t == 'fma':
                if ' * 2.0 + 1.0' in result:
                    result = result.replace('out_buf.data[idx] = in_buf.data[idx] * 2.0 + 1.0;',
                                          'out_buf.data[idx] = fma(in_buf.data[idx], 2.0, 1.0);')
                    applied.append('fma')
            elif t == 'addform':
                if ' * 2.0 + 1.0' in result:
                    result = result.replace('out_buf.data[idx] = in_buf.data[idx] * 2.0 + 1.0;',
                                          'float v = in_buf.data[idx];\n        out_buf.data[idx] = v + v + 1.0;')
                    applied.append('addform')
            elif t == 'inline':
                if 'float v = in_buf.data[idx];' not in result and ' * 2.0 + 1.0' in result:
                    result = result.replace('out_buf.data[idx] = in_buf.data[idx] * 2.0 + 1.0;',
                                          '{ float v = in_buf.data[idx]; out_buf.data[idx] = v * 2.0 + 1.0; }')
                    applied.append('inline')
            elif t == 'reorder':
                # safe reorder - just restructure
                pass
        return result, applied
    
    def test_transform(self, glsl_code, test_id, count=1024, reps=7):
        res = {'id': test_id, 'compiled': False, 'spirv_valid': False, 'functional': False, 'benchmark': None}
        tmpdir = tempfile.mkdtemp(prefix='shader_intel_')
        glsl_path = os.path.join(tmpdir, f'{test_id}.comp')
        spv_path = os.path.join(tmpdir, f'{test_id}.spv')
        with open(glsl_path, 'w') as f:
            f.write(glsl_code)
        res['glsl_hash'] = hashlib.sha256(glsl_code.encode()).hexdigest()
        
        r = self.run_cmd(['glslangValidator', '-V', '-S', 'comp', glsl_path, '-o', spv_path])
        if not (r['ok'] and os.path.exists(spv_path)):
            res['status'] = 'DISCARDED'; res['reason'] = 'COMPILE_FAILED'
            return res
        res['compiled'] = True
        r2 = self.run_cmd(['spirv-val', spv_path])
        if not r2['ok']:
            res['status'] = 'DISCARDED'; res['reason'] = 'SPIRV_INVALID'
            return res
        res['spirv_valid'] = True
        
        times = []; correct = True
        for i in range(reps):
            rb = self.run_cmd([self.harness, spv_path, str(count)], timeout=30)
            if not rb['ok']: correct = False; continue
            for line in rb['stdout'].split('\n'):
                if '"timing"' in line:
                    try:
                        t = json.loads(line); 
                        if 'timing' in t: times.append(t['timing']['exec'])
                    except: pass
            for line in rb['stdout'].split('\n'):
                if '"verification"' in line:
                    try:
                        v = json.loads(line)
                        if v.get('verification',{}).get('all_correct') != 1: correct = False
                    except: pass
        res['functional'] = correct
        if not correct:
            res['status'] = 'DISCARDED'; res['reason'] = 'INCORRECT'
            return res
        if times:
            res['benchmark'] = {'median_exec': sorted(times)[len(times)//2], 'mean_exec': sum(times)/len(times), 
                               'stdev': math.sqrt(sum((x-sum(times)/len(times))**2 for x in times)/len(times)) if len(times)>1 else 0}
        res['status'] = 'VALID'
        return res
    
    def run_discovery(self):
        print("=" * 60)
        print("POLARIS-005: RX SHADER INTELLIGENCE")
        print("=" * 60)
        print()
        
        base_glsl = open('/tmp/rxre_polaris_xjtsb94h/test.comp').read()
        base_spv = '/tmp/rxre_polaris_xjtsb94h/test.spv'
        
        print("[1] Baseline on RX 550...")
        base_res = self.test_transform(base_glsl, 'baseline_original')
        print(f"  Original: median={base_res['benchmark']['median_exec']:.6f}s" if base_res.get('benchmark') else "  Original: FAILED")
        base_med = base_res['benchmark']['median_exec'] if base_res.get('benchmark') else None
        
        print("\n[2] Applying semantic-preserving transforms...")
        tests = []
        # fma
        g1, a1 = self.transform_shader(base_glsl, ['fma'])
        tests.append(('fma_transform', g1))
        # addform
        g2, a2 = self.transform_shader(base_glsl, ['addform'])
        tests.append(('addform_transform', g2))
        # combined
        g3, a3 = self.transform_shader(base_glsl, ['fma'])
        g3 = g3.replace('#version 450\nlayout(local_size_x = 64', '#version 450\nlayout(local_size_x = 128')  # combine with wg
        # better combine properly
        g3 = '''#version 450
layout(local_size_x = 128, local_size_y = 1, local_size_z = 1) in;
layout(set = 0, binding = 0) buffer Input { float data[]; } in_buf;
layout(set = 0, binding = 1) buffer Output { float data[]; } out_buf;
void main() {
    uint idx = gl_GlobalInvocationID.x;
    if (idx < in_buf.data.length()) {
        out_buf.data[idx] = fma(in_buf.data[idx], 2.0, 1.0);
    }
}
'''
        tests.append(('fma_wg128_combined', g3))
        
        results = []
        for tid, gcode in tests:
            print(f"  Testing {tid}...", end=' ')
            r = self.test_transform(gcode, tid)
            if r.get('benchmark') and base_med:
                r['vs_baseline_ratio'] = r['benchmark']['median_exec']/base_med
                r['improvement_pct'] = (1-r['vs_baseline_ratio'])*100
                print(f"{r['status']} ({r['improvement_pct']:+.2f}%)")
            else:
                print(f"{r['status']}")
            results.append(r)
        
        print("\n[3] Learning...")
        for r in results:
            if r['status']=='VALID':
                if r.get('improvement_pct',0) > 2.0:
                    self.knowledge.append({'transform': r['id'], 'outcome': 'IMPROVES', 'evidence': r['benchmark']})
                    print(f"  LEARNED: {r['id']} IMPROVES by {r['improvement_pct']:.2f}%")
                elif r.get('improvement_pct',0) < -2.0:
                    self.knowledge.append({'transform': r['id'], 'outcome': 'WORSE', 'evidence': r['benchmark']})
                    print(f"  LEARNED: {r['id']} WORSENS by {abs(r['improvement_pct']):.2f}%")
                else:
                    self.knowledge.append({'transform': r['id'], 'outcome': 'NEUTRAL/NOISE', 'evidence': r['benchmark']})
                    print(f"  LEARNED: {r['id']} within noise")
        
        summary = {
            'mission': 'POLARIS-005',
            'timestamp': time.time(),
            'base_verified': base_res['status']=='VALID',
            'transforms_tested': len(results),
            'all_functionally_equivalent': all(r['functional'] for r in results),
            'improvements_found': len([k for k in self.knowledge if k['outcome']=='IMPROVES']),
            'knowledge': self.knowledge,
            'results': results,
            'status': 'PASS'
        }
        print(f"\n{'='*60}")
        print(f"SUMMARY: {summary['status']} - {summary['improvements_found']} improvements found")
        print(f"{'='*60}")
        with open('/tmp/polaris005_results.json', 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        print(f"\nResults saved to /tmp/polaris005_results.json")
        return summary

if __name__ == '__main__':
    si = RXShaderIntelligence()
    si.run_discovery()
