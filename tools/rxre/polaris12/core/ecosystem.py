"""Ecosistema Polaris 12 integrado al flujo compartido de RXRE.

Reutiliza: arquitectura 8 elementos, Router, evidencia, aprendizaje,
almacenamiento. No crea motores paralelos.
"""
from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

@dataclass
class EcosystemConfig:
    """Configuración compartida del ecosistema"""
    target_gpu: str = "Radeon RX 550 (Polaris 12 / Lexa PRO)"
    gcn_version: str = "GCN 4"
    vram_limit_gb: float = 2.0
    hybrid_host: str = "Intel i7-4790"
    evidence_required: bool = True
    reproducible_bench: bool = True
    no_hw_modification: bool = True
    simulation_only_by_default: bool = True
    use_existing_router: bool = True
    use_existing_evidence: bool = True


@dataclass
class ExperimentState:
    """Estado compartido entre tecnologías"""
    observations: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    experiments: List[Dict[str, Any]] = field(default_factory=list)
    validations: List[Dict[str, Any]] = field(default_factory=list)
    learnings: List[Dict[str, Any]] = field(default_factory=list)
    evidence_refs: List[str] = field(default_factory=list)


class Polaris12Ecosystem:
    """Motor unificado para tecnologías Polaris 12.
    
    Comparte evidencia, hipótesis, benchmarking, compilación/validación
    con el núcleo RXRE.
    """
    
    FLOW = [
        "OBSERVACIÓN",
        "RECONSTRUCCIÓN", 
        "HIPÓTESIS",
        "DISEÑO",
        "GENERACIÓN",
        "COMPILACIÓN",
        "EXPERIMENTO",
        "VALIDACIÓN",
        "APRENDIZAJE",
        "EVOLUCIÓN"
    ]
    
    TECH_STACK = [
        "RX_GPU_DNA",
        "RX_SHADER_FORGE",
        "RX_NEURAL_RE",
        "RX_MEMORY_ALCHEMY",
        "RX_HYBRID_CORE",
        "RX_VIRTUAL_GPU_LAB",
        "RX_AUTONOMOUS_GPU_EVOLUTION",
    ]
    
    def __init__(self, config: Optional[EcosystemConfig] = None):
        self.config = config or EcosystemConfig()
        self.state = ExperimentState()
        self.connected = False
        self.capabilities_connected = []
        self.missing_capabilities = []
    
    def connect_to_rxre(self) -> Dict[str, Any]:
        """Conecta al núcleo RXRE reutilizando componentes existentes."""
        result = {
            "connected": False,
            "components": [],
            "reused": [],
            "missing": [],
        }
        
        # Intentar conectar con Router existente
        try:
            from rxre.arquitectura.ROUTER import Router
            self.router = Router()
            result["reused"].append("arquitectura.ROUTER")
            result["components"].append("ROUTER")
        except Exception as e:
            result["missing"].append(f"ROUTER: {e}")
            self.router = None
        
        # Intentar conectar con 8 elementos
        try:
            from rxre.arquitectura import ALMA, CUERPO, MENTE, TIERRA, FUEGO, AIRE, AGUA, ETER
            result["reused"].extend(["ALMA", "CUERPO", "MENTE", "TIERRA", "FUEGO", "AIRE", "AGUA", "ETER"])
            result["components"].extend(["ALMA", "CUERPO", "MENTE", "TIERRA", "FUEGO", "AIRE", "AGUA", "ETER"])
        except Exception as e:
            result["missing"].append(f"arquitectura 8-elementos: {e}")
        
        # Intentar conectar con capability registry
        try:
            from rxre.core import capability_registry
            result["reused"].append("core.capability_registry")
            result["components"].append("CAPABILITY_REGISTRY")
        except Exception as e:
            result["missing"].append(f"capability_registry: {e}")
        
        # Intentar conectar con evidencia/snapshot
        try:
            from rxre.core import evidence_snapshot
            result["reused"].append("core.evidence_snapshot")
            result["components"].append("EVIDENCE_SNAPSHOT")
        except Exception as e:
            result["missing"].append(f"evidence_snapshot: {e}")
        
        # Intentar conectar con store
        try:
            from rxre.core import store
            result["reused"].append("core.store")
            result["components"].append("STORE")
        except Exception as e:
            result["missing"].append(f"store: {e}")
        
        # Registrar capacidades Polaris
        try:
            from .registry import register_polaris_capabilities
            reg = register_polaris_capabilities(self.router)
            self.capabilities_connected = reg.get("capabilities", [])
        except Exception as e:
            result["missing"].append(f"polaris registry: {e}")
        
        self.connected = len(result["reused"]) >= 2
        result["connected"] = self.connected
        result["shared_flow"] = self.FLOW
        result["tech_stack"] = self.TECH_STACK
        return result
    
    def observe(self, artifact_path: str = None) -> Dict[str, Any]:
        """Observación usando componentes RXRE existentes"""
        obs = {
            "type": "OBSERVACIÓN",
            "timestamp": time.time(),
            "target": self.config.target_gpu,
            "artifact": artifact_path,
            "evidence_collected": False,
        }
        try:
            if artifact_path and os.path.exists(artifact_path):
                from rxre.core import evidence_snapshot
                snap = evidence_snapshot.capturar_evidencia(artifact_path)
                obs["evidence_collected"] = True
                obs["hash"] = snap.hash_capturado
                obs["bytes"] = len(snap.bytes_consumidos)
        except Exception as e:
            obs["error"] = str(e)
        self.state.observations.append(obs)
        return obs
    
    def hypothesize(self, claim: str, falsification_test: str) -> Dict[str, Any]:
        """Genera hipótesis con falsificación (usando patrón MENTE)"""
        hyp = {
            "type": "HIPÓTESIS",
            "timestamp": time.time(),
            "claim": claim,
            "falsification_test": falsification_test,
            "status": "NOT_DETERMINED",
            "evidence_refs": [],
        }
        self.state.hypotheses.append(hyp)
        return hyp
    
    def experiment(self, design: Dict[str, Any]) -> Dict[str, Any]:
        """Experimento con restricciones de seguridad"""
        exp = {
            "type": "EXPERIMENTO",
            "timestamp": time.time(),
            "design": design,
            "simulation_only": self.config.simulation_only_by_default,
            "reproducible": self.config.reproducible_bench,
            "no_hw_mod": self.config.no_hw_modification,
            "status": "DESIGNED",
            "validated": False,
        }
        self.state.experiments.append(exp)
        return exp
    
    def validate(self, exp_id: int) -> Dict[str, Any]:
        """Validación con evidencia verificable"""
        val = {
            "type": "VALIDACIÓN",
            "timestamp": time.time(),
            "exp_ref": exp_id,
            "evidence_required": self.config.evidence_required,
            "status": "PENDING_EVIDENCE",
        }
        self.state.validations.append(val)
        return val
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "config": {
                "target_gpu": self.config.target_gpu,
                "gcn_version": self.config.gcn_version,
                "vram_limit_gb": self.config.vram_limit_gb,
                "hybrid_host": self.config.hybrid_host,
            },
            "flow": self.FLOW,
            "tech_stack": self.TECH_STACK,
            "capabilities_connected": self.capabilities_connected,
            "state_counts": {
                "observations": len(self.state.observations),
                "hypotheses": len(self.state.hypotheses),
                "experiments": len(self.state.experiments),
                "validations": len(self.state.validations),
                "learnings": len(self.state.learnings),
            },
            "restrictions": [
                "no hardware modification",
                "no firmware flash", 
                "no voltage/frequency changes",
                "no destructive experiments",
                "simulation not presented as real execution",
                "evidence required for improvements",
            ],
        }
