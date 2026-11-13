"""RX_SHADER_FORGE - Investigación/generación/transformación/optimización shaders GCN 4"""
from __future__ import annotations
from typing import Dict, Any, List
import subprocess
import hashlib
import tempfile
import os

class RXShaderForge:
    name = "RX_SHADER_FORGE"
    description = "Investigación, generación, transformación y optimización de shaders para GCN 4"

    def forge(self, shader_source: str = None) -> Dict[str, Any]:
        result = {
            "tech": self.name,
            "target": "GCN 4",
            "focus": ["glsl", "spirv", "optimization", "transformation"],
            "evidence_based": True,
            "reusable_with": ["RX_GPU_DNA", "RX_VIRTUAL_GPU_LAB"],
            "restrictions_applied": {"autonomous_loop_false": True, "max_iter_1": True, "op_claim_false": True, "db_auth_m294_blocked": True, "dbop_schema_m290_insufficient": True, "w5_blocked": True},
        }
        if shader_source is None:
            result["status"] = "DESIGNED"
            result["compilation"] = None
            return result
        # Real compilation using glslc if available (existing mechanism extended surgically)
        result["shader_source"] = shader_source
        result["glsl_sha256_16"] = hashlib.sha256(open(shader_source, "rb").read()).hexdigest()[:16] if os.path.isfile(shader_source) else None
        try:
            with tempfile.NamedTemporaryFile(suffix=".spv", delete=False) as tmp_spv:
                output_path = tmp_spv.name
            cmd = ["glslc", "-fshader-stage=compute", shader_source, "-o", output_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
            result["compilation_exit"] = proc.returncode
            result["compilation_stdout_200"] = proc.stdout.decode("latin-1", errors="ignore")[:200]
            result["compilation_stderr_200"] = proc.stderr.decode("latin-1", errors="ignore")[:200]
            result["spv_path"] = output_path
            if proc.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                result["spv_sha256_16"] = hashlib.sha256(open(output_path, "rb").read()).hexdigest()[:16]
                result["spv_size"] = os.path.getsize(output_path)
                result["status"] = "COMPILED"
                result["spv_validated"] = False
                result["artifact"] = output_path
                return result
            else:
                result["status"] = "COMPILE_FAILED"
                result["artifact"] = None
                return result
        except Exception as exc:
            result["status"] = "COMPILE_EXCEPTION"
            result["exception"] = str(exc)
            result["artifact"] = None
            return result

    def get_scope(self) -> List[str]:
        return ["shaders", "glsl", "spir-v", "gcnd", "optimization"]
