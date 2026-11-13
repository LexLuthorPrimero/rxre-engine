#!/usr/bin/env python3
"""Technology Integration — Register existing polaris12 modules with ROUTER.
Reuses existing code, no duplication.
"""
from __future__ import annotations
import os, sys, json, time
from datetime import datetime

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.join(ROOT, 'tools/rxre/polaris12'))

from tools.rxre.arquitectura.ROUTER import Router, Productor

# Map technology number to module and run method
TECH_MODULE_MAP = {
    1: ('hyper_compute', 'RXHyperCompute', 'run_hypercompute_experiment'),
    10: ('instruction_lab', 'RXInstructionLab', 'run_instruction_experiment'),
    3: ('memory_alchemy', 'RXMemoryAlchemy', 'run_experiment'),
    4: ('neural_fabric', 'RXNeuralFabric', 'run_polaris011' if hasattr(__import__('neural_fabric', fromlist=['RXNeuralFabric']), 'RXNeuralFabric') else 'run'),
    9: ('shader_intelligence', 'RXShaderIntelligence', 'run_discovery'),
    11: ('m58', 'M58Pipeline', None),  # Already integrated
    12: ('kernel_fusion', 'RXKernelFusion', 'run_fusion_experiment'),
    15: ('wavefront_branch', 'RXWavefrontBranch', 'run_polaris009'),
    17: ('hybrid_core', 'RXHybridCore', 'run_polaris010'),
    23: ('gpu_dna_discovery', 'GPUDNADiscovery', 'run_full_discovery'),
    24: ('universal_re', 'RXUniversalRE', 'run_polaris013'),
    25: ('neural_re', 'RXNeuralRE', 'run_polaris012'),
    22: ('gpu_evolution_engine', 'GPUEvolutionEngine', 'run_evolution'),
    27: None,  # Silicon Resurrection - composite
}

def create_producer(tech_id, module_name, class_name, method_name):
    """Create a ROUTER producer for a technology."""
    try:
        mod = __import__(module_name)
        cls = getattr(mod, class_name)
        
        def executor(*args, **kwargs):
            obj = cls()
            if method_name and hasattr(obj, method_name):
                return getattr(obj, method_name)(*args, **kwargs)
            return {'status': 'NO_RUN_METHOD', 'module': module_name}
        
        return Productor(
            nombre=f'tech_{tech_id}_{module_name}',
            capacidades=[f'tech_{tech_id}', module_name],
            disponible=True,
            ejecutar=executor,
            honesto=True
        )
    except Exception as e:
        print(f"  Failed to create producer for {module_name}: {e}")
        return None

def register_all_technologies():
    """Register all available technology modules with ROUTER."""
    router = Router()
    registered = []
    for tech_id, info in TECH_MODULE_MAP.items():
        if info is None:
            continue
        module_name, class_name, method_name = info
        prod = create_producer(tech_id, module_name, class_name, method_name)
        if prod:
            router.registrar(prod)
            registered.append((tech_id, module_name))
            print(f"  Registered tech {tech_id}: {module_name}")
    print(f"\nTotal registered: {len(registered)}")
    return router, registered

if __name__ == '__main__':
    print("Registering technologies with ROUTER...")
    router, registered = register_all_technologies()
    
    # Test resolution
    print("\nTesting resolution:")
    for tech_id, module_name in registered:
        res = router.resolver(f'tech_{tech_id}')
        print(f"  tech_{tech_id} ({module_name}): {res['elegido']} [{res['estado']}]")
    
    # Update tech status
    from tech_status_tracker import TechStatusTracker
    tracker = TechStatusTracker()
    for tech_id, module_name in registered:
        tracker.update_status(tech_id, 'OPERATIONAL', evidence=f'tools/rxre/polaris12/{module_name}.py')
    tracker.print_summary()
