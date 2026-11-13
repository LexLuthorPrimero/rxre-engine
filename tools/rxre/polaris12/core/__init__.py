"""Core components for Polaris 12 ecosystem integration."""
from .registry import register_polaris_capabilities
from .ecosystem import Polaris12Ecosystem, EcosystemConfig

__all__ = ["register_polaris_capabilities", "Polaris12Ecosystem", "EcosystemConfig"]
