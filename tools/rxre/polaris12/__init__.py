"""RXRE Polaris 12 Ecosystem (GCN 4 / Lexa PRO)
============================================

Integración coordinada de tecnologías para investigación y desarrollo
sobre AMD Radeon RX 550 (Polaris 12).

Se integra reutilizando los mecanismos existentes de RXRE (Router, 
arquitectura elemental 8 elementos, evidencia, aprendizaje) sin crear
motores paralelos.

Tecnologías coordinadas:
- RX_GPU_DNA: caracterización experimental
- RX_SHADER_FORGE: investigación/generación/optimización de shaders GCN 4
- RX_NEURAL_RE: reconstrucción asistida por IA (hipótesis discriminantes)
- RX_MEMORY_ALCHEMY: estrategias de VRAM/transferencia/caché
- RX_HYBRID_CORE: distribución adaptativa i7-4790 + RX 550
- RX_VIRTUAL_GPU_LAB: análisis estático/emulación/simulación/ejecución física controlada
- RX_AUTONOMOUS_GPU_EVOLUTION: generación/compilación/ejecución/medición/evolución

Principios: evidencia verificable, procedencia, hipótesis/falsificación,
ejecución controlada, benchmarking reproducible. Sin modificación de
hardware/firmware, sin experimentos destructivos, sin inventar mejoras.
"""

from __future__ import annotations

from .core.ecosystem import Polaris12Ecosystem, EcosystemConfig
from .core.registry import register_polaris_capabilities

__all__ = [
    "Polaris12Ecosystem",
    "EcosystemConfig", 
    "register_polaris_capabilities",
]
