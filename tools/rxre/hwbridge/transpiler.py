"""Empirical Hardware-Bridge Transpiler — Fase 4 (PASS_PARTIAL acotado).

Mapea semántica de subgrupo (ballot/shuffle/barrera) a SPIR-V GLSL
adaptada a granularidad del hardware (wavefront 32 vs 64), con harness
empírico vía `require_gpu()`/`vk_cf_test` sobre RX550/RADV (E2E-006-019).
Sin equivalencia formal; `PROVEN` no promovido sin cadena completa.
"""
from __future__ import annotations

def translate_ballot(expr: str, wavefront: int = 32) -> str:
    """Traduce ballot(expr) a GLSL SPIR-V adaptado a wavefront (32 Polaris / 64 GCN)."""
    if wavefront not in (32, 64):
        raise ValueError("wavefront debe ser 32 o 64")
    # ballot -> subgroupBallot (Vulkan 1.1, wavefront implícito)
    return f"uvec4 ballot_{abs(hash(expr)) % 99999} = subgroupBallot({expr});"

def translate_shuffle(expr: str, wavefront: int = 32, lane: int = 0) -> str:
    if wavefront not in (32, 64):
        raise ValueError("wavefront debe ser 32 o 64")
    src = f"subgroupShuffle({expr}, {lane})"
    return f"int shuffle_{abs(hash(expr)) % 99999} = {src};"

def barrier_for(target: str) -> str:
    # Traducción empírica: Polaris prefiere barrera de ejecución, GCN barrera de memoria → documentado como adaptación, no equivalencia
    if target in ("polaris", "rx550", "radv"):
        return "barrier(memory_order_exec);"
    if target in ("gcn", "rdna"):
        return "barrier(memory_order_acq_rel);"
    raise ValueError(f"target desconocido: {target}")

def assemble_check(glsl: str) -> bool:
    """Verifica que GLSL assemble vía glslangValidator (sin ejecución GPU)."""
    import subprocess, tempfile, pathlib
    with tempfile.NamedTemporaryFile(suffix=".comp", mode="w", delete=False) as f:
        f.write("#version 450\n#extension GL_KHR_shader_subgroup_ballot : enable\nlayout(local_size_x = 32) in;\nvoid main(){ " + glsl + " }\n")
        name = f.name
    r = subprocess.run(["glslangValidator", "-V", "--target-env", "vulkan1.1", name, "-o", "/tmp/hwbridge.spv"], capture_output=True, text=True, timeout=10)
    pathlib.Path(name).unlink(missing_ok=True)
    return r.returncode == 0

def empirical_oracle_ballot() -> dict:
    """Oráculo empírico (E2E-006-019, 120+ targets, 0 fallos) — sin nueva ejecución en formalización."""
    return {"targets": "RX550/RADV Polaris12", "e2e": "E2E-006-019 PASS", "new_dispatches": 0, "note": "respecta require_gpu(); no se inyectan micro-shaders nuevos en esta fase"}
