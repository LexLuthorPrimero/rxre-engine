#!/usr/bin/env python3
"""POLARIS-026B: RX Differential Validator — Stateful & Side-Effect Validation.

Extiende POLARIS-026A (differential_validator.py) para validar funciones con
estado y efectos secundarios: memoria, buffers, punteros, variables globales,
control de flujo (condiciones, bucles), I/O y funciones compuestas.

Reutiliza: differential_validator.py, semantic_code_reconstruction.py, ROUTER, TIERRA, AGUA.

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
from typing import Dict, Any, List, Optional, Tuple, Callable

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.polaris12.differential_validator import RXDifferentialValidator


class RXStatefulDifferentialValidator(RXDifferentialValidator):
    """Validación diferencial para funciones con estado y efectos secundarios.

    Extiende RXDifferentialValidator con:
    - Memoria: buffers, punteros, estructuras, lecturas y escrituras
    - Estado: variables globales y estado persistente entre llamadas
    - Control: condiciones, bucles, múltiples caminos de ejecución
    - Efectos externos: I/O en entornos aislados
    - Funciones compuestas: llamadas entre funciones y dependencias
    """

    def __init__(self, db_path: str = ":memory:", agua_path: str = "/tmp/rxre_agua_stateful.db"):
        super().__init__(db_path=db_path, agua_path=agua_path)
        self.stateful_results = []

    # ================================================================
    # 1. MEMORY VALIDATION (buffers, pointers, structures)
    # ================================================================

    def validate_memory_function(self, elf_path: str, func_name: str,
                                 buffer_size: int = 256,
                                 test_cases: List[Tuple] = None) -> Dict[str, Any]:
        """Validate a function that reads/writes memory buffers.

        Compares: return value, memory state (before/after), side effects.
        """
        # Generate C equivalent
        c_result = self.generate_c_equivalent(elf_path, func_name)
        if not c_result.get("compile", {}).get("ok", False):
            return {"function": func_name, "status": "COMPILE_FAILED",
                    "reason": c_result.get("compile", {}).get("stderr", "")}

        # Generate memory test cases
        if test_cases is None:
            test_cases = self._generate_memory_test_cases(buffer_size)

        # Execute original (via shared library)
        orig_results = self._execute_memory_original(elf_path, func_name, test_cases, buffer_size)

        # Execute reconstructed
        recon_results = self._execute_memory_reconstructed(c_result, func_name, test_cases, buffer_size)

        # Compare memory states
        comparison = self._compare_memory_results(orig_results, recon_results, test_cases)

        result = {
            "function": func_name,
            "status": "EQUIVALENT" if comparison["all_match"] else "DIVERGENT",
            "test_cases": len(test_cases),
            "matches": comparison["matches"],
            "mismatches": comparison["mismatches"],
            "memory_matches": comparison["memory_matches"],
            "memory_mismatches": comparison["memory_mismatches"],
            "divergences": comparison["divergences"],
            "validation_type": "memory",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "limitations": ["Finite test cases", "Memory layout may differ",
                           "Pointer aliasing not fully analyzed"],
        }
        self.stateful_results.append(result)
        return result

    def _generate_memory_test_cases(self, buffer_size: int) -> List[Dict[str, Any]]:
        """Generate memory test cases: various buffer contents and sizes."""
        cases = []
        random.seed(42)
        # Empty buffer
        cases.append({"buffer": [0] * buffer_size, "size": buffer_size, "desc": "empty"})
        # Sequential
        cases.append({"buffer": list(range(buffer_size)), "size": buffer_size, "desc": "sequential"})
        # All same value
        cases.append({"buffer": [42] * buffer_size, "size": buffer_size, "desc": "constant"})
        # Random
        for i in range(5):
            cases.append({"buffer": [random.randint(0, 255) for _ in range(buffer_size)],
                         "size": buffer_size, "desc": f"random_{i}"})
        # Small buffer
        cases.append({"buffer": [1, 2, 3], "size": 3, "desc": "small"})
        # Single element
        cases.append({"buffer": [99], "size": 1, "desc": "single"})
        return cases

    def _execute_memory_original(self, elf_path: str, func_name: str,
                                 test_cases: List[Dict], buffer_size: int) -> List[Dict]:
        """Execute original function with memory buffers."""
        results = []
        so_path = self._find_so(elf_path)
        if not so_path:
            for tc in test_cases:
                results.append({"status": "NOT_CALLABLE", "error": "No shared lib"})
            return results

        try:
            lib = ctypes.CDLL(so_path)
            func = getattr(lib, func_name)
        except Exception as e:
            for tc in test_cases:
                results.append({"status": "NOT_CALLABLE", "error": str(e)})
            return results

        for tc in test_cases:
            buf = (ctypes.c_int * len(tc["buffer"]))(*tc["buffer"])
            buf_copy = list(tc["buffer"])
            try:
                # Set up function signature (int func(int*, int))
                func.restype = ctypes.c_int
                func.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
                ret = func(buf, tc["size"])
                after = list(buf[:tc["size"]])
                results.append({
                    "status": "OK",
                    "return": ret,
                    "buffer_before": buf_copy,
                    "buffer_after": after,
                })
            except Exception as e:
                results.append({"status": "ERROR", "error": str(e)})
        return results

    def _execute_memory_reconstructed(self, c_result: Dict, func_name: str,
                                     test_cases: List[Dict], buffer_size: int) -> List[Dict]:
        """Execute reconstructed C function with memory buffers."""
        results = []
        c_path = c_result.get("compile", {}).get("c_path")
        if not c_path:
            for tc in test_cases:
                results.append({"status": "NO_BINARY"})
            return results

        tmpdir = tempfile.mkdtemp(prefix="rxre_mem_")
        so_path = os.path.join(tmpdir, f"lib{func_name}.so")
        compile_res = self.run_cmd(["gcc", "-shared", "-o", so_path, c_path, "-fPIC"])
        if not compile_res["ok"]:
            for tc in test_cases:
                results.append({"status": "COMPILE_FAILED", "error": compile_res["stderr"][:200]})
            return results

        try:
            lib = ctypes.CDLL(so_path)
            func = getattr(lib, func_name)
        except Exception as e:
            for tc in test_cases:
                results.append({"status": "LOAD_FAILED", "error": str(e)})
            return results

        for tc in test_cases:
            buf = (ctypes.c_int * len(tc["buffer"]))(*tc["buffer"])
            buf_copy = list(tc["buffer"])
            try:
                func.restype = ctypes.c_int
                func.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
                ret = func(buf, tc["size"])
                after = list(buf[:tc["size"]])
                results.append({
                    "status": "OK",
                    "return": ret,
                    "buffer_before": buf_copy,
                    "buffer_after": after,
                })
            except Exception as e:
                results.append({"status": "ERROR", "error": str(e)})
        return results

    def _compare_memory_results(self, original: List[Dict], reconstructed: List[Dict],
                                test_cases: List[Dict]) -> Dict[str, Any]:
        """Compare memory execution results."""
        matches = 0
        mismatches = 0
        memory_matches = 0
        memory_mismatches = 0
        divergences = []

        for i, (orig, recon) in enumerate(zip(original, reconstructed)):
            tc = test_cases[i] if i < len(test_cases) else {}

            if orig["status"] != "OK" or recon["status"] != "OK":
                divergences.append({
                    "test_case": tc.get("desc", f"case_{i}"),
                    "reason": f"original={orig['status']}, reconstructed={recon['status']}",
                    "status": "INCONCLUSIVE",
                })
                continue

            # Compare return values
            ret_match = (orig["return"] == recon["return"])
            # Compare memory state
            mem_match = (orig["buffer_after"] == recon["buffer_after"])

            if ret_match:
                matches += 1
            else:
                mismatches += 1
                divergences.append({
                    "test_case": tc.get("desc", f"case_{i}"),
                    "original_return": orig["return"],
                    "reconstructed_return": recon["return"],
                    "status": "DIVERGENT_RETURN",
                })

            if mem_match:
                memory_matches += 1
            else:
                memory_mismatches += 1
                divergences.append({
                    "test_case": tc.get("desc", f"case_{i}"),
                    "original_memory": orig["buffer_after"][:5],
                    "reconstructed_memory": recon["buffer_after"][:5],
                    "status": "DIVERGENT_MEMORY",
                })

        total = matches + mismatches
        all_match = (mismatches == 0 and memory_mismatches == 0 and
                     total > 0 and len(divergences) == 0)

        return {
            "matches": matches,
            "mismatches": mismatches,
            "memory_matches": memory_matches,
            "memory_mismatches": memory_mismatches,
            "total_compared": total,
            "divergences": divergences,
            "all_match": all_match,
        }

    # ================================================================
    # 2. STATE VALIDATION (global variables, persistent state)
    # ================================================================

    def validate_stateful_function(self, elf_path: str, func_name: str,
                                  call_sequences: List[List[Tuple]] = None) -> Dict[str, Any]:
        """Validate a function with persistent state across multiple calls.

        Tests that state is correctly maintained between calls.
        """
        c_result = self.generate_c_equivalent(elf_path, func_name)
        if not c_result.get("compile", {}).get("ok", False):
            return {"function": func_name, "status": "COMPILE_FAILED",
                    "reason": c_result.get("compile", {}).get("stderr", "")}

        if call_sequences is None:
            call_sequences = [
                [(1, 2), (3, 4), (5, 6)],  # sequential calls
                [(0, 0), (1, 1), (2, 2)],  # identity-like
                [(10, 20), (30, 40)],  # larger values
            ]

        so_path = self._find_so(elf_path)
        results = []

        for seq in call_sequences:
            # Execute original sequence
            orig_seq = self._execute_sequence_original(so_path, func_name, seq)
            # Execute reconstructed sequence
            recon_seq = self._execute_sequence_reconstructed(c_result, func_name, seq)

            # Compare
            match = (orig_seq == recon_seq)
            results.append({
                "sequence": seq,
                "original": orig_seq,
                "reconstructed": recon_seq,
                "match": match,
            })

        all_match = all(r["match"] for r in results)
        return {
            "function": func_name,
            "status": "EQUIVALENT" if all_match else "DIVERGENT",
            "sequences": len(call_sequences),
            "matches": sum(1 for r in results if r["match"]),
            "mismatches": sum(1 for r in results if not r["match"]),
            "details": results,
            "validation_type": "stateful",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "limitations": ["State may involve global variables not captured",
                           "Persistent state between calls may differ"],
        }

    def _execute_sequence_original(self, so_path: str, func_name: str,
                                  seq: List[Tuple]) -> List[int]:
        """Execute a sequence of calls on original function."""
        results = []
        try:
            lib = ctypes.CDLL(so_path)
            func = getattr(lib, func_name)
            func.restype = ctypes.c_int
            func.argtypes = [ctypes.c_int, ctypes.c_int]
            for args in seq:
                ret = func(*args)
                results.append(ret)
        except Exception as e:
            results.append(f"ERROR: {e}")
        return results

    def _execute_sequence_reconstructed(self, c_result: Dict, func_name: str,
                                       seq: List[Tuple]) -> List[int]:
        """Execute a sequence of calls on reconstructed function."""
        results = []
        c_path = c_result.get("compile", {}).get("c_path")
        if not c_path:
            return [f"NO_BINARY" for _ in seq]

        tmpdir = tempfile.mkdtemp(prefix="rxre_seq_")
        so_path = os.path.join(tmpdir, f"lib{func_name}.so")
        compile_res = self.run_cmd(["gcc", "-shared", "-o", so_path, c_path, "-fPIC"])
        if not compile_res["ok"]:
            return [f"COMPILE_FAILED" for _ in seq]

        try:
            lib = ctypes.CDLL(so_path)
            func = getattr(lib, func_name)
            func.restype = ctypes.c_int
            func.argtypes = [ctypes.c_int, ctypes.c_int]
            for args in seq:
                ret = func(*args)
                results.append(ret)
        except Exception as e:
            results.append(f"ERROR: {e}")
        return results

    # ================================================================
    # 3. CONTROL FLOW VALIDATION
    # ================================================================

    def validate_control_flow(self, elf_path: str, func_name: str) -> Dict[str, Any]:
        """Validate control flow (conditions, loops, multiple paths).

        Uses a range of inputs to exercise different code paths.
        """
        c_result = self.generate_c_equivalent(elf_path, func_name)
        if not c_result.get("compile", {}).get("ok", False):
            return {"function": func_name, "status": "COMPILE_FAILED",
                    "reason": c_result.get("compile", {}).get("stderr", "")}

        # Generate inputs that exercise different paths
        test_cases = self._generate_control_flow_cases()

        orig_results = self._execute_original_values(elf_path, func_name, test_cases)
        recon_results = self._execute_reconstructed_values(c_result, func_name, test_cases)

        matches = sum(1 for o, r in zip(orig_results, recon_results)
                     if o.get("return") == r.get("return") and o.get("status") == "OK" and r.get("status") == "OK")
        mismatches = sum(1 for o, r in zip(orig_results, recon_results)
                        if o.get("status") == "OK" and r.get("status") == "OK" and o.get("return") != r.get("return"))

        all_match = (mismatches == 0 and matches > 0 and
                     len(orig_results) == len(recon_results))

        return {
            "function": func_name,
            "status": "EQUIVALENT" if all_match else "DIVERGENT",
            "test_cases": len(test_cases),
            "matches": matches,
            "mismatches": mismatches,
            "paths_exercised": len(set(r.get("return") for r in orig_results if r.get("status") == "OK")),
            "validation_type": "control_flow",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }

    def _generate_control_flow_cases(self) -> List[Tuple]:
        """Generate test cases for control flow (various paths)."""
        cases = []
        # Zero, positive, negative
        for a in [0, 1, -1, 2, -2, 5, -5, 10, -10]:
            for b in [0, 1, -1, 2, -2]:
                cases.append((a, b))
        # Boundary values
        cases.append((2147483647, 1))
        cases.append((-2147483648, -1))
        cases.append((0, 2147483647))
        # Random
        random.seed(123)
        for _ in range(20):
            cases.append((random.randint(-50, 50), random.randint(-50, 50)))
        return cases

    def _execute_original_values(self, elf_path: str, func_name: str,
                                 test_cases: List[Tuple]) -> List[Dict]:
        """Execute original function, capture return values."""
        results = []
        so_path = self._find_so(elf_path)
        if not so_path:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NOT_CALLABLE"})
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
                    results.append({"inputs": tc, "return": None, "status": "EXCEPTION", "error": str(e)})
        except Exception as e:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NOT_CALLABLE", "error": str(e)})
        return results

    def _execute_reconstructed_values(self, c_result: Dict, func_name: str,
                                      test_cases: List[Tuple]) -> List[Dict]:
        """Execute reconstructed function, capture return values."""
        results = []
        c_path = c_result.get("compile", {}).get("c_path")
        if not c_path:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "NO_BINARY"})
            return results
        tmpdir = tempfile.mkdtemp(prefix="rxre_cf_")
        so_path = os.path.join(tmpdir, f"lib{func_name}.so")
        compile_res = self.run_cmd(["gcc", "-shared", "-o", so_path, c_path, "-fPIC"])
        if not compile_res["ok"]:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "COMPILE_FAILED"})
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
                    results.append({"inputs": tc, "return": None, "status": "EXCEPTION", "error": str(e)})
        except Exception as e:
            for tc in test_cases:
                results.append({"inputs": tc, "return": None, "status": "LOAD_FAILED", "error": str(e)})
        return results

    # ================================================================
    # 4. COMPOSITE FUNCTION VALIDATION
    # ================================================================

    def validate_composite(self, elf_path: str, func_names: List[str]) -> Dict[str, Any]:
        """Validate composite functions (functions that call other functions).

        Tests functions that depend on other functions in the same ELF.
        """
        results = {}
        for func_name in func_names:
            # First, reconstruct all dependencies
            c_results = {}
            for dep in func_names:
                c_results[dep] = self.generate_c_equivalent(elf_path, dep)

            # Validate the target function
            result = self.validate_function(elf_path, func_name)
            result["dependencies"] = [d for d in func_names if d != func_name]
            result["validation_type"] = "composite"
            results[func_name] = result

        return {
            "functions": results,
            "total": len(func_names),
            "equivalent": sum(1 for r in results.values() if r.get("status") == "EQUIVALENT"),
            "validation_type": "composite",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }

    # ================================================================
    # 5. FULL STATEFUL VALIDATION
    # ================================================================

    def validate_full_stateful(self, elf_path: str, func_names: List[str]) -> Dict[str, Any]:
        """Full stateful validation: memory + state + control flow + composite."""
        results = {}

        for func_name in func_names:
            mem_result = self.validate_memory_function(elf_path, func_name)
            cf_result = self.validate_control_flow(elf_path, func_name)
            state_result = self.validate_stateful_function(elf_path, func_name)

            results[func_name] = {
                "memory": mem_result.get("status"),
                "control_flow": cf_result.get("status"),
                "stateful": state_result.get("status"),
                "memory_matches": mem_result.get("matches", 0),
                "memory_mismatches": mem_result.get("mismatches", 0),
                "cf_matches": cf_result.get("matches", 0),
                "cf_mismatches": cf_result.get("mismatches", 0),
            }

        return {
            "functions": results,
            "total": len(func_names),
            "all_equivalent": all(
                r.get("memory") == "EQUIVALENT" and
                r.get("control_flow") == "EQUIVALENT" and
                r.get("stateful") == "EQUIVALENT"
                for r in results.values()
            ),
            "validation_type": "full_stateful",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }

    def _find_so(self, elf_path: str) -> Optional[str]:
        """Find a loadable shared library for the given ELF."""
        candidates = [
            elf_path,
            elf_path + ".so",
            elf_path.replace("_small", "_small.so"),
            "/tmp/libtest_elf_small.so",
            "/tmp/lib" + os.path.basename(elf_path) + ".so",
        ]
        for c in candidates:
            if os.path.exists(c):
                try:
                    ctypes.CDLL(c)
                    return c
                except Exception:
                    continue
        return None

    def get_stateful_summary(self) -> Dict[str, Any]:
        """Get summary of stateful validations."""
        total = len(self.stateful_results)
        equivalent = sum(1 for r in self.stateful_results if r.get("status") == "EQUIVALENT")
        return {
            "total_validations": total,
            "equivalent": equivalent,
            "divergent": total - equivalent,
            "validation_types": list(set(r.get("validation_type", "unknown") for r in self.stateful_results)),
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RX Stateful Differential Validator")
    parser.add_argument("elf_path", help="Path to ELF file")
    parser.add_argument("--func", help="Function to validate", default=None)
    parser.add_argument("--funcs", help="Comma-separated functions", default=None)
    parser.add_argument("--mode", help="Validation mode: memory, stateful, control, composite, full", default="full")
    args = parser.parse_args()

    validator = RXStatefulDifferentialValidator()

    if args.funcs:
        func_names = [f.strip() for f in args.funcs.split(",")]
    elif args.func:
        func_names = [args.func]
    else:
        func_names = ["add", "mul"]

    if args.mode == "memory":
        result = validator.validate_memory_function(args.elf_path, func_names[0])
    elif args.mode == "stateful":
        result = validator.validate_stateful_function(args.elf_path, func_names[0])
    elif args.mode == "control":
        result = validator.validate_control_flow(args.elf_path, func_names[0])
    elif args.mode == "composite":
        result = validator.validate_composite(args.elf_path, func_names)
    elif args.mode == "full":
        result = validator.validate_full_stateful(args.elf_path, func_names)
    else:
        result = validator.validate_function(args.elf_path, func_names[0])

    print(json.dumps(result, indent=2, default=str))
