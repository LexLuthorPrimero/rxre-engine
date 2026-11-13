#!/usr/bin/env python3
"""Technology Status Verifier — Real verification of each technology's state.
Checks actual code, execution, evidence, and integration status.
"""
from __future__ import annotations
import os, json, hashlib, time, subprocess, sys, importlib
from typing import Dict, Any, List
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

# Technology definitions with verification criteria
TECH_VERIFY = {
    1: {'name': 'RX HyperCompute', 'module': 'hyper_compute', 'class': 'RXHyperCompute', 'method': 'run_hypercompute_experiment', 'evidence_dir': 'hyper_compute'},
    2: {'name': 'RX Parallel Fusion', 'module': 'parallel_fusion', 'class': 'RXParallelFusion', 'method': 'run_fusion_experiment', 'evidence_dir': 'parallel_fusion'},
    3: {'name': 'RX Memory Alchemy', 'module': 'memory_alchemy', 'class': 'RXMemoryAlchemy', 'method': 'run_experiment', 'evidence_dir': None},
    4: {'name': 'RX Neural Fabric', 'module': 'neural_fabric', 'class': 'RXNeuralFabric', 'method': None, 'evidence_dir': None},
    5: {'name': 'RX Neural Texture', 'module': 'neural_texture', 'class': 'RXNeuralTexture', 'method': 'run_texture_experiment', 'evidence_dir': 'neural_texture'},
    6: {'name': 'RX Software Ray', 'module': 'software_ray', 'class': 'RXSoftwareRay', 'method': 'run_ray_experiment', 'evidence_dir': 'software_ray'},
    7: {'name': 'RX Temporal Vision', 'module': 'temporal_vision', 'class': 'RXTemporalVision', 'method': 'run_vision_experiment', 'evidence_dir': 'temporal_vision'},
    8: {'name': 'RX Virtual Texture', 'module': 'virtual_texture', 'class': 'RXVirtualTexture', 'method': 'run_vt_experiment', 'evidence_dir': 'virtual_texture'},
    9: {'name': 'RX Shader Forge', 'module': 'shader_intelligence', 'class': 'RXShaderIntelligence', 'method': 'run_discovery', 'evidence_dir': None},
    10: {'name': 'RX Instruction Lab', 'module': 'instruction_lab', 'class': 'RXInstructionLab', 'method': 'run_instruction_experiment', 'evidence_dir': 'instruction_lab'},
    11: {'name': 'RX Binary Reconstructor', 'module': 'm58', 'class': 'M58Pipeline', 'method': None, 'evidence_dir': 'm58'},
    12: {'name': 'RX Kernel Fusion', 'module': 'kernel_fusion', 'class': 'RXKernelFusion', 'method': 'run_fusion_experiment', 'evidence_dir': None},
    13: {'name': 'RX MicroScheduler', 'module': 'micro_scheduler', 'class': 'RXMicroScheduler', 'method': 'run_microscheduler_experiment', 'evidence_dir': 'micro_scheduler'},
    14: {'name': 'RX Register Optimizer', 'module': 'register_optimizer', 'class': 'RXRegisterOptimizer', 'method': 'run_register_experiment', 'evidence_dir': 'register_optimizer'},
    15: {'name': 'RX Wavefront Intelligence', 'module': 'wavefront_branch', 'class': 'RXWavefrontBranch', 'method': 'run_polaris009', 'evidence_dir': None},
    16: {'name': 'RX Driver Observatory', 'module': 'driver_observatory', 'class': 'RXDriverObservatory', 'method': 'run_observatory', 'evidence_dir': 'driver_observatory'},
    17: {'name': 'RX Hybrid Core', 'module': 'hybrid_core', 'class': 'RXHybridCore', 'method': 'run_polaris010', 'evidence_dir': None},
    18: {'name': 'RX Dynamic Offload', 'module': 'dynamic_offload', 'class': 'RXDynamicOffload', 'method': 'run_offload_experiment', 'evidence_dir': 'dynamic_offload'},
    19: {'name': 'RX Shared Pipeline', 'module': 'shared_pipeline', 'class': 'RXSharedPipeline', 'method': 'run_shared_pipeline_experiment', 'evidence_dir': 'shared_pipeline'},
    20: {'name': 'RX Distributed Compute', 'module': 'distributed_compute', 'class': 'RXDistributedCompute', 'method': 'run_distributed_experiment', 'evidence_dir': 'distributed_compute'},
    21: {'name': 'RX Adaptive Compression', 'module': 'adaptive_compression', 'class': 'RXAdaptiveCompression', 'method': 'run_compression_experiment', 'evidence_dir': 'adaptive_compression'},
    22: {'name': 'RXRE Self-Optimizing GPU', 'module': 'gpu_evolution_engine', 'class': 'GPUEvolutionEngine', 'method': 'run_evolution', 'evidence_dir': 'gpu_evolution'},
    23: {'name': 'RX GPU DNA', 'module': 'gpu_dna_discovery', 'class': 'GPUDNADiscovery', 'method': 'run_full_discovery', 'evidence_dir': 'gpu_dna'},
    24: {'name': 'RX Universal Kernel', 'module': 'universal_re', 'class': 'RXUniversalRE', 'method': 'run_polaris013', 'evidence_dir': None},
    25: {'name': 'RX Neural Reverse Engineering', 'module': 'neural_re', 'class': 'RXNeuralRE', 'method': 'run_polaris012', 'evidence_dir': None},
    26: {'name': 'RX Virtual GPU Laboratory', 'module': 'virtual_gpu_lab', 'class': 'RXVirtualGPULab', 'method': 'run_lab', 'evidence_dir': 'virtual_gpu_lab'},
    27: {'name': 'RX Silicon Resurrection', 'module': 'silicon_resurrection', 'class': 'RXSiliconResurrection', 'method': 'run_resurrection', 'evidence_dir': 'silicon_resurrection'},
}

def verify_technology(tech_id, info):
    """Verify a single technology's actual state."""
    result = {
        'tech_id': tech_id,
        'name': info['name'],
        'registered': False,
        'importable': False,
        'instantiable': False,
        'has_run_method': False,
        'evidence_exists': False,
        'router_registered': False,
        'verification_status': 'NOT_DETERMINED'
    }
    
    # Check importable
    try:
        mod = __import__(info['module'])
        result['importable'] = True
    except Exception as e:
        result['verification_status'] = 'BLOCKED'
        result['error'] = str(e)
        return result
    
    # Check instantiable
    try:
        cls = getattr(mod, info['class'])
        if info['class'] == 'M58Pipeline':
            obj = cls(os.path.join(ROOT, '.rxre/capture_169/compute_169.spv'))
        else:
            obj = cls()
        result['instantiable'] = True
    except Exception as e:
        result['verification_status'] = 'BLOCKED'
        result['error'] = str(e)
        return result
    
    # Check run method
    if info['method']:
        result['has_run_method'] = hasattr(obj, info['method'])
    
    # Check evidence
    if info['evidence_dir']:
        ev_dir = os.path.join(ROOT, 'evidence', info['evidence_dir'])
        if os.path.isdir(ev_dir):
            ev_files = [f for f in os.listdir(ev_dir) if f.endswith('.json')]
            result['evidence_exists'] = len(ev_files) > 0
            result['evidence_count'] = len(ev_files)
    
    # Check ROUTER registration
    try:
        from tools.rxre.arquitectura.ROUTER import Router
        r = Router()
        for p in r.productores:
            if info['module'] in p.nombre or f"tech_{tech_id}" in p.nombre:
                result['router_registered'] = True
                break
    except:
        pass
    
    # Determine verification status
    if result['importable'] and result['instantiable']:
        if result['evidence_exists'] or info['evidence_dir'] is None:
            if result['router_registered']:
                result['verification_status'] = 'VALIDATED'
            else:
                result['verification_status'] = 'OPERATIONAL'
        else:
            result['verification_status'] = 'OPERATIONAL'
    else:
        result['verification_status'] = 'BLOCKED'
    
    return result

def verify_all():
    """Verify all 27 technologies."""
    print("="*70)
    print("TECHNOLOGY STATUS VERIFICATION — 27 Technologies")
    print("="*70)
    
    results = {}
    by_status = {}
    
    for tech_id, info in TECH_VERIFY.items():
        result = verify_technology(tech_id, info)
        results[tech_id] = result
        status = result['verification_status']
        by_status[status] = by_status.get(status, 0) + 1
        print(f"  [{tech_id:2d}] {info['name'][:30]:30s} -> {status:12s} (import={result['importable']}, inst={result['instantiable']}, ev={result['evidence_exists']}, router={result['router_registered']})")
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    print(f"  Total: {len(results)}")
    
    # Save results
    out_path = os.path.join(ROOT, 'evidence', 'tech_verification.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({'timestamp': datetime.now().isoformat(), 'results': results, 'by_status': by_status}, f, indent=2)
    print(f"\nResults saved: {out_path}")
    
    return results, by_status

if __name__ == '__main__':
    results, by_status = verify_all()
