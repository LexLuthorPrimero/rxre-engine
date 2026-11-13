"""Registro de capacidades Polaris 12 integrado al Router de RXRE.

Reutiliza el mecanismo de capacidades existente (sin duplicar catálogo),
resolviendo capacidades por nombre, no inventando herramientas.
"""
from __future__ import annotations

from typing import Dict, List, Any

# Capacidades Polaris 12 que se integran al ecosistema RXRE
POLARIS_CAPABILITIES = {
    "polaris12.dna.characterize": {
        "description": "Caracterización experimental arquitectura Polaris 12/GCN 4",
        "requires": {"hw_context": False, "artifact": False},
        "producers": ["rx_gpu_dna"],
        "scope": ["rxre.observation"],
    },
    "polaris12.shader.forge": {
        "description": "Investigación/generación/transformación/optimización shaders GCN 4",
        "requires": {"glsl": False, "spirv": False},
        "producers": ["rx_shader_forge"],
        "scope": ["rxre.design"],
    },
    "polaris12.neural.reverse": {
        "description": "Reconstrucción asistida por IA con hipótesis discriminantes",
        "requires": {"binary": False, "hypotheses": False},
        "producers": ["rx_neural_re"],
        "scope": ["rxre.reasoning"],
    },
    "polaris12.memory.alchemy": {
        "description": "Estrategias VRAM/asignación/reutilización/compresión/caché",
        "requires": {"vram_context": False},
        "producers": ["rx_memory_alchemy"],
        "scope": ["rxre.optimization"],
    },
    "polaris12.hybrid.core": {
        "description": "Distribución adaptativa Intel i7-4790 + RX 550",
        "requires": {"workload": False},
        "producers": ["rx_hybrid_core"],
        "scope": ["rxre.execution"],
    },
    "polaris12.lab.experiment": {
        "description": "Lab virtual: estático/emulación/simulación/ejecución física controlada",
        "requires": {"mode": False},
        "producers": ["rx_virtual_gpu_lab"],
        "scope": ["rxre.experimentation"],
    },
    "polaris12.evolution.engine": {
        "description": "Variantes/compilación/ejecución/medición/comparación/evolución",
        "requires": {"kernel": False, "benchmark": False},
        "producers": ["rx_autonomous_evolution"],
        "scope": ["rxre.evolution"],
    },
    "polaris12.shared.evidence": {
        "description": "Evidencia/procedencia compartida entre tecnologías",
        "requires": {"artifact": False},
        "producers": ["polaris_evidence_bridge"],
        "scope": ["rxre.verification"],
    },
}


def register_polaris_capabilities(router=None) -> Dict[str, Any]:
    """Registra capacidades Polaris 12 en el Router existente o retorna definición.
    
    Reutiliza Router si está disponible; si no, solo declara capacidades.
    """
    result = {
        "registered": True,
        "capabilities": list(POLARIS_CAPABILITIES.keys()),
        "status": "DECLARED",
        "restrictions": ["no hardware modification", "no firmware flash", 
                        "no voltage/frequency changes", "evidence required"],
    }
    
    try:
        if router is not None:
            from rxre.arquitectura.ROUTER import Productor
            # Registrar productores para capacidades Polaris 12
            prods = []
            for cap, info in POLARIS_CAPABILITIES.items():
                for p in info["producers"]:
                    prods.append(Productor(p, [cap], False))  # disponible=False por defecto
            for p in prods:
                router.registrar(p)
            result["status"] = "REGISTERED_IN_ROUTER"
            result["producers_registered"] = len(prods)
    except Exception as e:
        result["status"] = "DECLARED_ONLY"
        result["router_error"] = str(e)
    
    return result


def get_capabilities() -> Dict[str, Any]:
    return POLARIS_CAPABILITIES
