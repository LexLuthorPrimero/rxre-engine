#!/usr/bin/env python3
"""RX Instruction Lab — GCN instruction analysis, semantic experiments, and instruction-level optimization.
Reuses M58 SPIR-V analysis and GPU DNA experimental data.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, re, tempfile
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

SPV_PATH = os.path.join(ROOT, '.rxre/capture_169/compute_169.spv')
LAB_DIR = os.path.join(ROOT, 'evidence', 'instruction_lab')
os.makedirs(LAB_DIR, exist_ok=True)

class RXInstructionLab:
    """GCN instruction analysis and semantic experiments."""
    
    def __init__(self):
        self.instructions = []
        self.experiments = []
        self.features = {}
    
    def run_cmd(self, cmd, timeout=60):
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            return {'rc': r.returncode, 'stdout': r.stdout.decode(errors='ignore'), 'stderr': r.stderr.decode(errors='ignore'), 'ok': r.returncode == 0}
        except Exception as e:
            return {'rc': -1, 'stdout': '', 'stderr': str(e), 'ok': False}
    
    def analyze_spirv_instructions(self, spv_path=None):
        """Analyze SPIR-V instructions for GCN-relevant patterns."""
        spv_path = spv_path or SPV_PATH
        print("[Instruction Lab] Analyzing SPIR-V instructions...")
        r = self.run_cmd(['spirv-dis', spv_path])
        if not r['ok']:
            return {'status': 'BLOCKED', 'reason': 'spirv-dis failed'}
        
        disasm = r['stdout']
        lines = disasm.splitlines()
        
        # Count instruction types
        instr_counts = {}
        opcodes = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            # Extract opcode
            parts = line.split()
            if len(parts) >= 2 and parts[0].startswith('%'):
                # Format: %id = OpXXX ...
                if '=' in line:
                    op = line.split('=')[1].strip().split()[0]
                    opcodes[op] = opcodes.get(op, 0) + 1
            elif line.startswith('Op'):
                op = line.split()[0]
                opcodes[op] = opcodes.get(op, 0) + 1
        
        # GCN-relevant instruction patterns
        gcn_patterns = {
            'arithmetic': ['OpIAdd', 'OpFAdd', 'OpIMul', 'OpFMul', 'OpFSub', 'OpISub'],
            'memory': ['OpLoad', 'OpStore', 'OpAccessChain'],
            'control': ['OpBranch', 'OpBranchConditional', 'OpReturn', 'OpFunctionEnd'],
            'conversion': ['OpConvertFToS', 'OpConvertSToF', 'OpBitcast'],
            'vector': ['OpCompositeConstruct', 'OpCompositeExtract', 'OpVectorExtractDynamic'],
        }
        
        pattern_counts = {}
        for category, ops in gcn_patterns.items():
            count = sum(opcodes.get(op, 0) for op in ops)
            pattern_counts[category] = count
        
        # Data dependency analysis
        # Find all %id references and build dependency graph
        deps = {}
        for line in lines:
            line = line.strip()
            if '=' in line and 'Op' in line:
                parts = line.split('=')
                if len(parts) == 2:
                    target = parts[0].strip()
                    rest = parts[1].strip()
                    # Find referenced %ids
                    refs = re.findall(r'%\w+', rest)
                    refs = [r for r in refs if r != target]
                    if refs:
                        deps[target] = list(set(refs))
        
        # Instruction-level features
        features = {
            'total_instructions': len(lines),
            'opcode_counts': dict(sorted(opcodes.items(), key=lambda x: -x[1])[:20]),
            'gcn_patterns': pattern_counts,
            'dependency_edges': len(deps),
            'max_dependency_depth': self._compute_depth(deps),
            'has_vector_ops': pattern_counts.get('vector', 0) > 0,
            'has_memory_ops': pattern_counts.get('memory', 0) > 0,
            'arithmetic_intensity': pattern_counts.get('arithmetic', 0) / max(pattern_counts.get('memory', 1), 1),
        }
        
        self.instructions = lines
        self.features['spirv_instructions'] = features
        
        # M58 integration
        try:
            from tools.rxre.polaris12.m58.m58_spirv_pipeline import M58Pipeline
            p = M58Pipeline(spv_path)
            p.verify_integrity()
            p.disassemble()
            p.extract_structural()
            s = p.build_semantic()
            features['m58_semantic'] = s
            features['m58_struct'] = p.struct
        except Exception as e:
            features['m58_error'] = str(e)
        
        # Persist
        ev_path = os.path.join(LAB_DIR, f'instr_analysis_{int(time.time())}.json')
        with open(ev_path, 'w') as f:
            json.dump({'mission': 'RX_INSTRUCTION_LAB', 'timestamp': datetime.now().isoformat(),
                       'spv_path': spv_path, 'features': features, 'restrictions': {'DB_AUTH': 'safe'}}, f, indent=2)
        
        print(f"  Total instructions: {features['total_instructions']}")
        print(f"  GCN patterns: {pattern_counts}")
        print(f"  Dependency edges: {features['dependency_edges']}")
        print(f"  Arithmetic intensity: {features['arithmetic_intensity']:.2f}")
        print(f"  Evidence: {ev_path}")
        
        return features
    
    def _compute_depth(self, deps):
        """Compute max dependency depth."""
        memo = {}
        def depth(node, visited=None):
            if visited is None:
                visited = set()
            if node in memo:
                return memo[node]
            if node in visited:
                return 0  # cycle
            visited.add(node)
            refs = deps.get(node, [])
            if not refs:
                memo[node] = 0
                return 0
            d = 1 + max(depth(r, visited.copy()) for r in refs)
            memo[node] = d
            return d
        if not deps:
            return 0
        return max(depth(n) for n in deps)
    
    def run_instruction_experiment(self):
        """Run a full instruction lab experiment."""
        print("="*60)
        print("RX INSTRUCTION LAB — GCN Instruction Analysis")
        print("="*60)
        
        features = self.analyze_spirv_instructions()
        
        # Semantic experiment: test arithmetic intensity impact
        print("\n[Experiment] Arithmetic intensity analysis")
        print(f"  Arithmetic ops: {features['gcn_patterns'].get('arithmetic', 0)}")
        print(f"  Memory ops: {features['gcn_patterns'].get('memory', 0)}")
        print(f"  Intensity: {features['arithmetic_intensity']:.2f}")
        
        # Persist knowledge
        try:
            from tools.rxre.arquitectura.AGUA import Agua, Aprendizaje
            agua = Agua(os.path.join(LAB_DIR, 'instr_lab_agua.db'))
            def rev():
                return True
            apr = Aprendizaje('instr_lab_analysis', 'instruction_lab', 'spirv instruction analysis', rev, 0.8)
            aid = agua.aprender(apr)
            print(f"  AGUA aprendizaje: {aid}")
        except Exception as e:
            print(f"  AGUA warning: {e}")
        
        print("\n" + "="*60)
        print("INSTRUCTION LAB — COMPLETE")
        print("="*60)
        return features

if __name__ == '__main__':
    lab = RXInstructionLab()
    features = lab.run_instruction_experiment()
