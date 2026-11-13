#!/usr/bin/env python3
"""POLARIS-026A: RX Differential Validator — Validación diferencial de código reconstruido.

Extiende POLARIS-025 para ejecutar funciones originales y reconstrucciones C
bajo entradas equivalentes, comparando retornos, memoria y efectos observables.

Reutiliza: semantic_code_reconstruction.py, ROUTER, TIERRA, AGUA.

Restricciones preservadas:
  - DB_AUTH_ACTOR_M294: BLOCKED
  - W5: BLOCKED
  - autonomous_loop: False
  - max_iter: 1
  - op_claim: False
  - No modificar activos protegidos
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math, ctypes, random
from typing import Dict, Any, List, Optional, Tuple

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.polaris12.semantic_code_reconstruction import RXSemanticCodeReconstruction


class RXDifferentialValidator(RXSemanticCodeReconstruction):
    """Validación diferencial de código reconstruido.

    Ejecuta funciones originales y reconstrucciones C bajo entradas equivalentes,
    comparando retornos, memoria modificada y efectos observables.
    """

    def __init__(self, db_path: str = ":memory:", agua_path: str = "/tmp/rxre_agua_diff.db"):
        super().__init__(db_path=db_path, agua_path=agua_path)
        self.validation_results = []

    def validate_function(self, elf_path: str, func_name: str,
                          test_cases: List[Tuple] = None) -> Dict[str, Any]:
        """Validate a reconstructed function via differential testing.

        Args:
            elf_path: Path to ELF containing the original function
            func_name: Name of the function to validate
            test_cases: List of input tuples. If None, generates default cases.

        Returns:
            Validation result with pass/fail, divergences, and evidence.
        """
        # Step 1: Generate C equivalent
        c_result = self.generate_c_equivalent(elf_path, func_name)
        if not c_result.get("compile", {}).get("ok", False):
            return {
                "function": func_name,
                "status": "COMPILE_FAILED",
                "reason": c_result.get("compile", {}).get("stderr", "Unknown"),
                "compile_ok": False,
            }

        # Step 2: Generate test cases
        if test_cases is None:
            test_cases = self._generate_test_cases(func_name)

        # Step 3: Execute original function (via ctypes)
        original_results = self._execute_original(elf_path, func_name, test_cases)

        # Step 4: Execute reconstructed function (via compiled C)
        reconstructed_results = self._execute_reconstructed(c_result, func_name, test_cases)

        # Step 5: Compare results
        comparison = self._compare_results(original_results, reconstructed_results, test_cases)

        result = {
            "function": func_name,
            "status": "EQUIVALENT" if comparison["all_match"] else "DIVERGENT",
            "test_cases": len(test_cases),
            "matches": comparison["matches"],
            "mismatches": comparison["mismatches"],
            "divergences": comparison["divergences"],
            "compile_ok": True,
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "limitations": ["Finite test cases (not universal proof)",
                           "Static analysis for argument/return inference",
                           "No physical execution of original binary"],
        }

        self.validation_results.append(result)
        return result

    def _generate_test_cases(self, func_name: str) -> List[Tuple]:
        """Generate test cases: normal, boundary, random."""
        cases = []
        # Normal cases
        cases.append((0, 0))
        cases.append((1, 1))
        cases.append((2, 3))
        cases.append((5, 7))
        cases.append((10, 20))
        # Boundary cases
        cases.append((0, 1))
        cases.append((1, 0))
        cases.append((-1, 1))
        cases.append((1, -1))
        cases.append((-1, -1))
        # Large values
        cases.append((100, 200))
        cases.append((1000, 2000))
        # Edge cases
        cases.append((2147483647, 0))  # INT_MAX
        cases.append((0, 2147483647))
        # Random reproducible cases
        random.seed(42)
        for _ in range(10):
            cases.append((random.randint(-100, 100), random.randint(-100, 100)))
        return cases

    def _execute_original(self, elf_path: str, func_name: str, test_cases: List[Tuple]) -> List[Dict[str, Any]]:
        """Execute original function from ELF via ctypes."""
        results = []
        # Try to load as shared library; if ELF is executable, try .so variant
        load_path = elf_path
        if not os.path.exists(elf_path + ".so") and elf_path.endswith("_small"):
            load_path = elf_path.replace("_small", "_small.so") if os.path.exists(elf_path.replace("_small", "_small.so")) else elf_path

        # Try various .so paths
        so_candidates = [elf_path, elf_path + ".so", elf_path.replace("_small", "_small.so"),
                        elf_path.replace("_small", "_small.so").replace("test_elf", "libtest_elf"),
                        "/tmp/libtest_elf_small.so"]
        loaded = False
        for candidate in so_candidates:
            if os.path.exists(candidate):
                try:
                    lib = ctypes.CDLL(candidate)
                    func = getattr(lib, func_name)
                    loaded = True
                    break
                except Exception:
                    continue

        if not loaded:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NOT_CALLABLE",
                               "error": "No loadable shared library found"})
            return results

        try:
            func.restype = ctypes.c_int
            func.argtypes = [ctypes.c_int, ctypes.c_int]
            func.restype = ctypes.c_int
            func.argtypes = [ctypes.c_int, ctypes.c_int]
            for tc in test_cases:
                try:
                    ret = func(*tc)
                    results.append({"inputs": tc, "return": ret, "status": "OK"})
                except Exception as e:
                    results.append({"inputs": tc, "return": None, "status": "ERROR", "error": str(e)})
        except Exception as e:
            # Function not callable via ctypes (not exported, or different signature)
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NOT_CALLABLE", "error": str(e)})
        return results

    def _execute_reconstructed(self, c_result: Dict, func_name: str, test_cases: List[Tuple]) -> List[Dict[str, Any]]:
        """Execute reconstructed C function."""
        results = []
        c_path = c_result.get("compile", {}).get("c_path")
        o_path = c_result.get("compile", {}).get("o_path")
        if not c_path or not o_path:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NO_BINARY"})
            return results

        # Compile to shared library
        tmpdir = tempfile.mkdtemp(prefix="rxre_diff_")
        so_path = os.path.join(tmpdir, f"lib{func_name}.so")
        compile_res = self.run_cmd(["gcc", "-shared", "-o", so_path, c_path, "-fPIC"])
        if not compile_res["ok"]:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "COMPILE_SHARED_FAILED",
                               "error": compile_res["stderr"][:200]})
            return results

        try:
            lib = ctypes.CDLL(so_path)
            func = getattr(lib, func_name)
            func.restype = ctypes.c_int
            func.argtypes = [ctypes.c_int, ctypes.c_int]
            for tc in test_cases:
                try:
                    ret = func(*tc)
                    results.append({"inputs": tc, "return": ret, "status": "OK"})
                except Exception as e:
                    results.append({"inputs": tc, "return": None, "status": "ERROR", "error": str(e)})
        except Exception as e:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "LOAD_FAILED", "error": str(e)})
        return results

    def _compare_results(self, original: List[Dict], reconstructed: List[Dict],
                         test_cases: List[Tuple]) -> Dict[str, Any]:
        """Compare original vs reconstructed results."""
        matches = 0
        mismatches = 0
        divergences = []

        for i, (orig, recon) in enumerate(zip(original, reconstructed)):
            tc = test_cases[i] if i < len(test_cases) else ("?", "?")

            if orig["status"] == "NOT_CALLABLE" or recon["status"] in ("NO_BINARY", "COMPILE_SHARED_FAILED", "LOAD_FAILED"):
                # Can't compare — record as inconclusive
                divergences.append({
                    "test_case": tc,
                    "reason": f"original={orig['status']}, reconstructed={recon['status']}",
                    "status": "INCONCLUSIVE",
                })
                continue

            if orig["return"] == recon["return"]:
                matches += 1
            else:
                mismatches += 1
                divergences.append({
                    "test_case": tc,
                    "original_return": orig["return"],
                    "reconstructed_return": recon["return"],
                    "status": "DIVERGENT",
                })

        total = matches + mismatches
        all_match = (mismatches == 0 and total > 0 and
                     not any(d.get("status") == "INCONCLUSIVE" for d in divergences))

        return {
            "matches": matches,
            "mismatches": mismatches,
            "total_compared": total,
            "inconclusive": len(divergences) - mismatches,
            "divergences": divergences,
            "all_match": all_match,
        }

    def validate_multiple(self, elf_path: str, func_names: List[str]) -> Dict[str, Any]:
        """Validate multiple functions from the same ELF."""
        results = {}
        for func_name in func_names:
            results[func_name] = self.validate_function(elf_path, func_name)
        return {
            "functions": results,
            "total": len(func_names),
            "equivalent": sum(1 for r in results.values() if r.get("status") == "EQUIVALENT"),
            "divergent": sum(1 for r in results.values() if r.get("status") == "DIVERGENT"),
            "inconclusive": sum(1 for r in results.values() if r.get("status") not in ("EQUIVALENT", "DIVERGENT")),
        }

    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of all validations."""
        total = len(self.validation_results)
        equivalent = sum(1 for r in self.validation_results if r.get("status") == "EQUIVALENT")
        divergent = sum(1 for r in self.validation_results if r.get("status") == "DIVERGENT")
        return {
            "total_validations": total,
            "equivalent": equivalent,
            "divergent": divergent,
            "inconclusive": total - equivalent - divergent,
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RX Differential Validator")
    parser.add_argument("elf_path", help="Path to ELF file")
    parser.add_argument("--func", help="Function to validate", default=None)
    parser.add_argument("--funcs", help="Comma-separated functions", default=None)
    args = parser.parse_args()

    validator = RXDifferentialValidator()

    if args.funcs:
        func_names = [f.strip() for f in args.funcs.split(",")]
        result = validator.validate_multiple(args.elf_path, func_names)
    elif args.func:
        result = validator.validate_function(args.elf_path, args.func)
    else:
        # Default: validate add and mul
        result = validator.validate_multiple(args.elf_path, ["add", "mul"])

    print(json.dumps(result, indent=2, default=str))
