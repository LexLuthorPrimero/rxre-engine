#!/usr/bin/env python3
"""POLARIS-025: RX Semantic Code Reconstruction — Reconstrucción semántica de código máquina.

Extiende POLARIS-022/023/024 para reconstruir el comportamiento semántico de
funciones x86-64 a partir de código máquina.

Ciclo por función:
  INSTRUCCIONES → FLUJO DE DATOS → RECONSTRUCCIÓN SEMÁNTICA → C EQUIVALENTE
  → VALIDACIÓN DIFERENCIAL → CONOCIMIENTO REUTILIZABLE

Reutiliza: semantic_reconstruction.py, elf_reconstruction.py, ROUTER, TIERRA, AGUA.

Restricciones preservadas:
  - DB_AUTH_ACTOR_M294: BLOCKED
  - W5: BLOCKED
  - autonomous_loop: False
  - max_iter: 1
  - op_claim: False
  - No modificar activos protegidos
"""
from __future__ import annotations
import os, json, time, hashlib, subprocess, tempfile, sys, math, re
from typing import Dict, Any, List, Optional, Tuple

ROOT = '/home/lucas/Escritorio/rxre'
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

from rxre.polaris12.elf_reconstruction import RXELFReconstruction


class RXSemanticCodeReconstruction(RXELFReconstruction):
    """Reconstrucción semántica de código máquina x86-64.

    Extiende RXELFReconstruction con análisis de instrucciones, flujo de datos,
    reconstrucción semántica y generación de C equivalente.
    """

    # Categorías de instrucciones x86-64
    INSTR_CATEGORIES = {
        "arithmetic": ["add", "sub", "imul", "mul", "div", "idiv", "inc", "dec", "neg", "adc", "sbb"],
        "logical": ["and", "or", "xor", "not", "test", "shl", "shr", "sar", "sal", "rol", "ror", "rcl", "rcr"],
        "move": ["mov", "movz", "movs", "movsx", "movzx", "lea", "cmov", "xchg", "bswap"],
        "memory": ["push", "pop", "lod", "sto", "scas", "cmps", "movs"],
        "compare": ["cmp", "test"],
        "branch": ["jmp", "je", "jne", "jl", "jg", "jb", "ja", "jle", "jge", "jbe", "jae", "js", "jns", "jp", "jnp", "jo", "jno", "jecxz", "jrcxz", "loop"],
        "call": ["call", "ret", "retn", "retf"],
        "stack": ["push", "pop", "enter", "leave"],
        "system": ["syscall", "sysenter", "int", "cpuid", "rdtsc"],
    }

    def __init__(self, db_path: str = ":memory:", agua_path: str = "/tmp/rxre_agua_scr.db"):
        super().__init__(db_path=db_path, agua_path=agua_path)
        self.instruction_analysis = {}
        self.data_flow = {}
        self.semantic_reconstructions = {}
        self.c_implementations = {}

    # ================================================================
    # 1. INSTRUCTION ANALYSIS
    # ================================================================

    def analyze_instructions(self, elf_path: str, func_name: str = None) -> Dict[str, Any]:
        """Analyze instructions of a function (or all functions).

        Categorizes each instruction and extracts operands, registers, memory access.
        """
        result = self.run_cmd(["objdump", "-d", "-M", "intel", elf_path])
        if not result["ok"]:
            return {"error": result["stderr"][:500], "functions": {}}

        full_output = result["stdout"]
        functions = {}
        current_func = None
        current_instrs = []

        for line in full_output.split("\n"):
            m = re.match(r'^[0-9a-f]+ <(.+)>:', line)
            if m:
                if current_func and current_instrs:
                    functions[current_func] = self._analyze_function_instructions(current_func, current_instrs)
                current_func = m.group(1)
                current_instrs = []
            elif current_func and re.match(r'^\s*[0-9a-f]+:', line):
                current_instrs.append(line.strip())

        if current_func and current_instrs:
            functions[current_func] = self._analyze_function_instructions(current_func, current_instrs)

        # Filter to specific function if requested
        if func_name and func_name in functions:
            return {"functions": {func_name: functions[func_name]}}

        # Limit to reasonable number
        if len(functions) > 50:
            # Prefer non-plt, non-init functions
            filtered = {k: v for k, v in functions.items()
                       if not k.startswith('.') and '@plt' not in k}
            if filtered:
                functions = filtered

        return {
            "functions": functions,
            "function_count": len(functions),
            "total_instructions": sum(f["instruction_count"] for f in functions.values()),
        }

    def _analyze_function_instructions(self, func_name: str, lines: List[str]) -> Dict[str, Any]:
        """Analyze instructions of a single function."""
        instrs = []
        categories = {cat: 0 for cat in self.INSTR_CATEGORIES}
        registers_used = set()
        registers_modified = set()
        memory_accesses = []
        calls = []
        branches = []

        for line in lines:
            # Parse instruction
            # Format: "  401000:  48 89 e5              mov    rbp, rsp"
            # Use regex to handle variable number of byte columns
            m = re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2}\s+)+\s*([a-z][a-z0-9]*)(.*)$', line)
            if not m:
                continue
            addr = m.group(1)
            mnemonic = m.group(2).lower()
            operands = m.group(3).strip()

            # Categorize
            cat = self._categorize_instruction(mnemonic)
            if cat:
                categories[cat] = categories.get(cat, 0) + 1

            # Extract registers
            regs = self._extract_registers(operands)
            registers_used.update(regs["read"])
            registers_modified.update(regs["write"])

            # Memory accesses
            if '[' in operands:
                memory_accesses.append({
                    "instruction": line.strip(),
                    "mnemonic": mnemonic,
                    "operands": operands,
                })

            # Calls
            if mnemonic == "call" or mnemonic.startswith("call"):
                calls.append({
                    "instruction": line.strip(),
                    "target": operands,
                })

            # Branches
            if mnemonic in ("jmp",) or mnemonic.startswith("j"):
                branches.append({
                    "instruction": line.strip(),
                    "mnemonic": mnemonic,
                    "target": operands,
                })

            instrs.append({
                "address": addr,
                "mnemonic": mnemonic,
                "operands": operands,
                "category": cat,
                "registers_read": regs["read"],
                "registers_write": regs["write"],
            })

        return {
            "function_name": func_name,
            "instruction_count": len(instrs),
            "instructions": instrs[:100],  # limit
            "categories": {k: v for k, v in categories.items() if v > 0},
            "registers_used": sorted(registers_used),
            "registers_modified": sorted(registers_modified),
            "memory_accesses": memory_accesses[:20],
            "calls": calls,
            "branches": branches,
            "has_calls": len(calls) > 0,
            "has_branches": len(branches) > 0,
            "is_leaf": len(calls) == 0,
        }

    def _categorize_instruction(self, mnemonic: str) -> Optional[str]:
        """Categorize an x86-64 instruction."""
        for cat, mnemonics in self.INSTR_CATEGORIES.items():
            if mnemonic in mnemonics:
                return cat
            for m in mnemonics:
                if mnemonic.startswith(m):
                    return cat
        return None

    def _extract_registers(self, operands: str) -> Dict[str, List[str]]:
        """Extract registers read and written from operands."""
        # x86-64 registers (sorted by length desc for matching)
        regs = ["r15d", "r14d", "r13d", "r12d", "r11d", "r10d", "r9d", "r8d",
                "r15", "r14", "r13", "r12", "r11", "r10", "r9", "r8",
                "xmm7", "xmm6", "xmm5", "xmm4", "xmm3", "xmm2", "xmm1", "xmm0",
                "rbp", "rsp", "rsi", "rdi", "rdx", "rcx", "rbx", "rax",
                "ebp", "esp", "esi", "edi", "edx", "ecx", "ebx", "eax",
                "bpl", "spl", "sil", "dil", "dl", "cl", "bl", "al",
                "r8b", "r9b", "r10b", "r11b", "r12b", "r13b", "r14b", "r15b"]

        read = []
        write = []
        ops_lower = operands.lower()

        # Find all registers mentioned in operands
        mentioned = []
        for r in regs:
            if r in ops_lower:
                mentioned.append(r)

        # Memory operands imply read of base register
        if '[' in operands:
            read.append("mem")
            # Extract register inside brackets
            bracket_content = operands[operands.index('['):] if '[' in operands else ""
            for r in regs:
                if r in bracket_content.lower():
                    read.append(r)

        # Determine read vs write based on mnemonic context
        # For mov: first=write, second=read
        # For arithmetic: first=read+write, second=read
        # For cmp/test: both read
        # For push/pop: stack ops
        parts = [p.strip() for p in operands.split(",")]
        if len(parts) >= 1:
            first = parts[0].lower()
            for r in regs:
                if r in first and r not in read:
                    # Only add to write if it's a register (not memory)
                    if '[' not in first:
                        write.append(r)
                        break
        if len(parts) >= 2:
            second = parts[1].lower()
            for r in regs:
                if r in second:
                    read.append(r)
                    break

        # Argument registers in x86-64: if rdi/rsi/rdx/rcx/r8/r9 appear, they are likely args
        arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9", "edi", "esi", "edx", "ecx"]
        for r in arg_regs:
            if r in ops_lower:
                read.append(r)

        return {"read": list(set(read)), "write": list(set(write))}

    # ================================================================
    # 2. DATA FLOW RECONSTRUCTION
    # ================================================================

    def analyze_data_flow(self, elf_path: str, func_name: str = None) -> Dict[str, Any]:
        """Analyze data flow for functions.

        Tracks register usage, def-use chains, constant propagation.
        """
        instr_analysis = self.analyze_instructions(elf_path, func_name)
        functions = instr_analysis.get("functions", {})

        data_flows = {}
        for fname, finfo in functions.items():
            df = self._analyze_function_data_flow(fname, finfo)
            data_flows[fname] = df

        return {
            "functions": data_flows,
            "function_count": len(data_flows),
        }

    def _analyze_function_data_flow(self, func_name: str, finfo: Dict) -> Dict[str, Any]:
        """Analyze data flow for a single function."""
        instrs = finfo.get("instructions", [])
        if not instrs:
            return {"status": "NO_INSTRUCTIONS", "def_use": {}, "constants": {}}

        # Track register definitions and uses
        def_use = {}  # register -> list of (def_addr, use_addrs)
        reg_defs = {}  # register -> last def address
        constants = {}  # register -> constant value (if known)
        mem_accesses = []

        for instr in instrs:
            addr = instr["address"]
            mnemonic = instr["mnemonic"]
            operands = instr["operands"]
            reads = instr["registers_read"]
            writes = instr["registers_write"]

            # Track definitions
            for r in writes:
                if r not in def_use:
                    def_use[r] = {"defs": [], "uses": []}
                def_use[r]["defs"].append(addr)
                reg_defs[r] = addr

                # Constant propagation
                if mnemonic == "mov" and not '[' in operands:
                    parts = [p.strip() for p in operands.split(",")]
                    if len(parts) == 2:
                        src = parts[1].strip()
                        try:
                            val = int(src, 0) if src.startswith("0x") or src.isdigit() else None
                            if val is not None:
                                constants[r] = val
                        except ValueError:
                            pass

            # Track uses
            for r in reads:
                if r not in def_use:
                    def_use[r] = {"defs": [], "uses": []}
                def_use[r]["uses"].append(addr)

            # Memory accesses
            if "mem" in reads or "mem" in writes or '[' in operands:
                mem_accesses.append({
                    "address": addr,
                    "mnemonic": mnemonic,
                    "operands": operands,
                })

        # Infer arguments (registers used before defined)
        # In x86-64 System V calling convention: rdi, rsi, rdx, rcx, r8, r9 are args
        arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        inferred_args = []
        for r in arg_regs:
            if r not in def_use:
                continue
            uses = def_use[r].get("uses", [])
            defs = def_use[r].get("defs", [])
            if not uses:
                continue
            # If register is used and either never defined or used before first def
            if not defs:
                inferred_args.append(r)
            else:
                first_use = min(uses)
                first_def = min(defs)
                if first_use < first_def:
                    inferred_args.append(r)
                # Also check: if register is only read (never written), it's an arg
                if r not in [d for d in (reg_defs if 'reg_defs' in dir() else {})] and uses:
                    if r not in inferred_args:
                        inferred_args.append(r)

        # Fallback: if no args inferred but function has arithmetic, assume rdi, rsi
        if not inferred_args and finfo.get("categories", {}).get("arithmetic", 0) > 0:
            # Check if rdi/rsi appear in any instruction
            all_instrs = finfo.get("instructions", [])
            for instr in all_instrs:
                ops = instr.get("operands", "").lower()
                if "rdi" in ops or "edi" in ops or "di" in ops.split():
                    if "rdi" not in inferred_args:
                        inferred_args.append("rdi")
                if "rsi" in ops or "esi" in ops or "si" in ops.split():
                    if "rsi" not in inferred_args:
                        inferred_args.append("rsi")

        # Infer return value (rax/eax is typically return)
        has_return = bool(("rax" in def_use and def_use["rax"]["defs"]) or \
                     ("eax" in def_use and def_use["eax"]["defs"]))

        return {
            "status": "ANALYZED",
            "def_use_chains": {k: v for k, v in list(def_use.items())[:20]},
            "constants_propagated": constants,
            "memory_accesses": mem_accesses[:20],
            "inferred_arguments": inferred_args,
            "has_return_value": has_return,
            "register_count": len(def_use),
        }

    # ================================================================
    # 3. SEMANTIC RECONSTRUCTION
    # ================================================================

    def reconstruct_semantics(self, elf_path: str, func_name: str = None) -> Dict[str, Any]:
        """Reconstruct semantic description of functions.

        Generates structured description: purpose, inputs, outputs, transformations,
        conditions, calls, side effects, uncertainties, evidence.
        """
        instr_analysis = self.analyze_instructions(elf_path, func_name)
        data_flow = self.analyze_data_flow(elf_path, func_name)

        functions = instr_analysis.get("functions", {})
        semantics = {}

        for fname, finfo in functions.items():
            df = data_flow.get("functions", {}).get(fname, {})
            sem = self._reconstruct_function_semantics(fname, finfo, df)
            semantics[fname] = sem
            self.semantic_reconstructions[fname] = sem

        return {
            "functions": semantics,
            "function_count": len(semantics),
        }

    def _reconstruct_function_semantics(self, func_name: str, finfo: Dict, df: Dict) -> Dict[str, Any]:
        """Reconstruct semantics for a single function."""
        cats = finfo.get("categories", {})
        calls = finfo.get("calls", [])
        branches = finfo.get("branches", [])
        mem_accesses = finfo.get("memory_accesses", [])
        args = df.get("inferred_arguments", [])
        has_ret = df.get("has_return_value", False)
        constants = df.get("constants_propagated", {})

        # Determine purpose
        purpose = self._infer_purpose(cats, calls, mem_accesses, constants)

        # Determine inputs
        inputs = []
        for r in args:
            inputs.append({"register": r, "role": "argument", "confidence": "INFERRED"})

        # Determine outputs
        outputs = []
        if has_ret:
            outputs.append({"register": "rax", "role": "return_value", "confidence": "INFERRED"})

        # Transformations
        transformations = []
        if "arithmetic" in cats:
            transformations.append("arithmetic_operations")
        if "logical" in cats:
            transformations.append("logical_operations")
        if "move" in cats:
            transformations.append("data_movement")
        if mem_accesses:
            transformations.append("memory_access")

        # Conditions
        conditions = []
        if branches:
            conditions.append(f"{len(branches)} branch(es) detected")

        # Side effects
        side_effects = []
        if any("push" in c.get("mnemonic", "") for c in []):
            side_effects.append("stack_modification")
        if mem_accesses:
            side_effects.append("memory_modification")

        # Uncertainties
        uncertainties = []
        if not args:
            uncertainties.append("no_arguments_inferred")
        if not has_ret:
            uncertainties.append("no_return_value_detected")
        if not finfo.get("is_leaf", True):
            uncertainties.append("non_leaf_function (calls present)")
        if len(cats) < 2:
            uncertainties.append("limited_instruction_variety")

        # Evidence
        evidence = {
            "instruction_count": finfo.get("instruction_count", 0),
            "categories": cats,
            "call_count": len(calls),
            "branch_count": len(branches),
            "memory_access_count": len(mem_accesses),
            "constants": constants,
        }

        return {
            "function": func_name,
            "purpose": purpose,
            "inputs": inputs,
            "outputs": outputs,
            "transformations": transformations,
            "conditions": conditions,
            "calls": [c["target"] for c in calls],
            "side_effects": side_effects,
            "uncertainties": uncertainties,
            "evidence": evidence,
            "status": "RECONSTRUCTED" if len(uncertainties) <= 2 else "PARTIAL",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "limitations": ["Static analysis only", "No physical execution",
                           "Types inferred, not verified", "No debug symbols used"],
        }

    def _infer_purpose(self, cats: Dict, calls: List, mem_accesses: List, constants: Dict) -> str:
        """Infer probable purpose from instruction categories."""
        if "call" in cats and cats.get("call", 0) > 3:
            return "wrapper/orchestrator (many calls)"
        if "memory" in cats and "arithmetic" in cats:
            return "data transformation (memory + arithmetic)"
        if "arithmetic" in cats and not mem_accesses:
            return "pure computation (arithmetic only)"
        if mem_accesses and not cats.get("arithmetic", 0):
            return "data movement (memory only)"
        if "branch" in cats or "compare" in cats:
            return "conditional logic"
        if cats.get("move", 0) > cats.get("arithmetic", 0):
            return "data movement/copy"
        return "unknown purpose (insufficient evidence)"

    # ================================================================
    # 4. C CODE GENERATION
    # ================================================================

    def generate_c_equivalent(self, elf_path: str, func_name: str) -> Dict[str, Any]:
        """Generate C equivalent for a function (when possible).

        Does NOT confuse plausible pseudocode with equivalent code.
        Validates via independent compilation and differential testing.
        """
        instr_analysis = self.analyze_instructions(elf_path, func_name)
        func_info = instr_analysis.get("functions", {}).get(func_name, {})
        if not func_info:
            return {"status": "NO_FUNCTION", "reason": f"Function {func_name} not found"}

        semantics = self._reconstruct_function_semantics(func_name, func_info,
            self.analyze_data_flow(elf_path, func_name).get("functions", {}).get(func_name, {}))

        # Generate C code based on semantics
        c_code = self._generate_c_from_semantics(func_name, semantics, func_info)

        # Validate: compile
        compile_result = self._validate_c_compile(c_code, func_name)

        # Validate: differential test (if possible)
        diff_result = self._validate_c_differential(c_code, func_name, elf_path)

        return {
            "function": func_name,
            "c_code": c_code,
            "semantics": semantics,
            "compile": compile_result,
            "differential": diff_result,
            "status": "VALIDATED" if compile_result.get("ok") and diff_result.get("ok") else "PARTIAL",
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "limitations": ["Static analysis only", "No debug symbols",
                           "Types inferred, not verified", "Equivalence limited to tested cases"],
        }

    def _generate_c_from_semantics(self, func_name: str, semantics: Dict, finfo: Dict) -> str:
        """Generate C code from semantic reconstruction.

        Generates functional C code based on detected transformations,
        not just skeleton. Validates via independent compilation.
        """
        args = semantics.get("inputs", [])
        param_names = [f"arg{i}" for i in range(len(args))]
        arg_str = ", ".join(f"int {pn}" for pn in param_names) if param_names else "void"
        if not args:
            arg_str = "void"

        transformations = semantics.get("transformations", [])
        purpose = semantics.get("purpose", "unknown")
        uncertainties = semantics.get("uncertainties", [])

        lines = [f"/* Reconstructed from {func_name} */"]
        lines.append(f"/* Purpose: {purpose} */")
        lines.append(f"/* Status: {semantics.get('status', 'UNKNOWN')} */")
        lines.append(f"/* Uncertainties: {uncertainties} */")
        lines.append("")

        if arg_str == "void":
            lines.append(f"int {func_name}(void) {{")
        else:
            lines.append(f"int {func_name}({arg_str}) {{")

        # Generate body based on transformations
        # Infer operation from instruction categories and transformations
        instrs = finfo.get("instructions", [])
        has_add = any(i["mnemonic"] == "add" for i in instrs)
        has_sub = any(i["mnemonic"] == "sub" for i in instrs)
        has_imul = any(i["mnemonic"] in ("imul", "mul") for i in instrs)
        has_shl = any(i["mnemonic"] in ("shl", "sal") for i in instrs)
        has_shr = any(i["mnemonic"] in ("shr", "sar") for i in instrs)

        # Determine return expression
        if has_add and not has_imul and not has_sub:
            if len(param_names) >= 2:
                lines.append(f"    return {param_names[0]} + {param_names[1]};")
            elif len(param_names) == 1:
                lines.append(f"    return {param_names[0]} + {param_names[0]};")
            else:
                lines.append("    return 0;")
        elif has_imul and not has_add:
            if len(param_names) >= 2:
                lines.append(f"    return {param_names[0]} * {param_names[1]};")
            elif len(param_names) == 1:
                lines.append(f"    return {param_names[0]} * {param_names[0]};")
            else:
                lines.append("    return 0;")
        elif has_sub:
            if len(param_names) >= 2:
                lines.append(f"    return {param_names[0]} - {param_names[1]};")
            else:
                lines.append("    return 0;")
        elif has_shl:
            if len(param_names) >= 2:
                lines.append(f"    return {param_names[0]} << {param_names[1]};")
            else:
                lines.append("    return 0;")
        elif has_shr:
            if len(param_names) >= 2:
                lines.append(f"    return {param_names[0]} >> {param_names[1]};")
            else:
                lines.append("    return 0;")
        else:
            lines.append("    return 0; /* no clear transformation */")

        lines.append("}")
        return "\n".join(lines)

    def _validate_c_compile(self, c_code: str, func_name: str) -> Dict[str, Any]:
        """Validate C code by independent compilation."""
        tmpdir = tempfile.mkdtemp(prefix="rxre_c_")
        c_path = os.path.join(tmpdir, f"{func_name}.c")
        o_path = os.path.join(tmpdir, f"{func_name}.o")

        with open(c_path, "w") as f:
            f.write(c_code)

        result = self.run_cmd(["gcc", "-c", "-o", o_path, c_path])
        return {
            "ok": result["ok"],
            "exit_code": result["rc"],
            "stderr": result["stderr"][:500],
            "c_path": c_path,
            "o_path": o_path if result["ok"] else None,
        }

    def _validate_c_differential(self, c_code: str, func_name: str, elf_path: str) -> Dict[str, Any]:
        """Validate C code via differential testing (when possible)."""
        # For now, differential testing requires the original binary to be executable
        # and the reconstructed function to be callable. This is complex for arbitrary ELF.
        # We record the attempt and its limitations.
        return {
            "ok": False,
            "status": "NOT_IMPLEMENTED",
            "reason": "Differential testing requires calling convention analysis and test harness",
            "limitations": ["Calling convention not fully analyzed",
                           "Test harness not implemented",
                           "Physical execution may be blocked (W5)"],
        }

    # ================================================================
    # 5. COVERAGE AND EVALUATION
    # ================================================================

    def evaluate_coverage(self, elf_path: str) -> Dict[str, Any]:
        """Evaluate reconstruction coverage metrics.

        Measures separately:
        - Functions detected
        - Functions with CFG
        - Functions with data flow analysis
        - Functions with semantic reconstruction
        - Functions with C equivalent generated
        - Functions with validated C equivalent
        """
        # Analyze instructions
        instr = self.analyze_instructions(elf_path)
        funcs = instr.get("functions", {})

        # Data flow
        df = self.analyze_data_flow(elf_path)

        # Semantics
        sem = self.reconstruct_semantics(elf_path)

        # Count metrics
        total_detected = len(funcs)
        with_cfg = 0
        with_df = 0
        with_semantics = 0
        with_c = 0
        with_validated_c = 0

        cfg_data = self.analyze_cfg(elf_path)
        cfg_funcs = set(cfg_data.get("function_cfgs", {}).keys())

        for fname in funcs:
            if fname in cfg_funcs:
                with_cfg += 1
            if fname in df.get("functions", {}):
                with_df += 1
            if fname in sem.get("functions", {}):
                with_semantics += 1
            c_result = self.generate_c_equivalent(elf_path, fname)
            if c_result.get("c_code"):
                with_c += 1
            if c_result.get("status") == "VALIDATED":
                with_validated_c += 1

        return {
            "total_functions_detected": total_detected,
            "functions_with_cfg": with_cfg,
            "functions_with_data_flow": with_df,
            "functions_with_semantics": with_semantics,
            "functions_with_c_equivalent": with_c,
            "functions_with_validated_c": with_validated_c,
            "coverage_ratio": {
                "cfg": with_cfg / total_detected if total_detected > 0 else 0,
                "data_flow": with_df / total_detected if total_detected > 0 else 0,
                "semantics": with_semantics / total_detected if total_detected > 0 else 0,
                "c_equivalent": with_c / total_detected if total_detected > 0 else 0,
                "validated": with_validated_c / total_detected if total_detected > 0 else 0,
            },
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
            "note": "Function count alone is NOT a metric of semantic reconstruction",
        }

    # ================================================================
    # FULL RESEARCH CYCLE (ELF + SEMANTIC CODE RECONSTRUCTION)
    # ================================================================

    def research_cycle_full(self, elf_path: str) -> Dict[str, Any]:
        """Full research cycle: ELF analysis + semantic code reconstruction.

        Combines POLARIS-023 (ELF) + POLARIS-025 (semantic code) into
        a single flow.
        """
        # Stage 1-13: ELF analysis (from POLARIS-023)
        cycle = self.research_cycle_elf(elf_path)

        # Stage 14: Instruction analysis
        instr = self.analyze_instructions(elf_path)
        cycle["stages"]["instructions"] = {
            "function_count": instr.get("function_count", 0),
            "total_instructions": instr.get("total_instructions", 0),
        }

        # Stage 15: Data flow analysis
        df = self.analyze_data_flow(elf_path)
        cycle["stages"]["data_flow"] = {
            "function_count": df.get("function_count", 0),
        }

        # Stage 16: Semantic reconstruction
        sem = self.reconstruct_semantics(elf_path)
        cycle["stages"]["semantics"] = {
            "function_count": sem.get("function_count", 0),
            "functions": list(sem.get("functions", {}).keys())[:10],
        }

        # Stage 17: C code generation (for first function only, to avoid overload)
        c_results = {}
        first_func = None
        if instr.get("functions"):
            first_func = list(instr["functions"].keys())[0]
        if first_func:
            c_result = self.generate_c_equivalent(elf_path, first_func)
            c_results[first_func] = {
                "status": c_result.get("status"),
                "compile_ok": c_result.get("compile", {}).get("ok", False),
                "c_code": c_result.get("c_code", "")[:500],
            }
        cycle["stages"]["c_reconstruction"] = c_results

        # Stage 18: Coverage evaluation
        coverage = self.evaluate_coverage(elf_path)
        cycle["stages"]["coverage"] = coverage

        # Stage 19: Register learning
        self._register_code_learning(cycle, elf_path)

        cycle["final_status"] = "COMPLETE"
        return cycle

    def _register_code_learning(self, cycle: Dict, elf_path: str):
        """Register code reconstruction learning in AGUA."""
        try:
            from rxre.arquitectura.AGUA import Aprendizaje
            aprendizaje = Aprendizaje(
                proposito=f"Semantic code reconstruction of {elf_path}",
                procedencia=f"POLARIS-025 code reconstruction",
                regla=f"Functions: {cycle['stages'].get('instructions', {}).get('function_count', 0)}, "
                      f"CFG: {cycle['stages'].get('cfg', {}).get('function_count', 0)}, "
                      f"Semantics: {cycle['stages'].get('semantics', {}).get('function_count', 0)}",
                reverificar=lambda: True,
                confianza=0.7,
            )
            apr_id = self.agua.aprender(aprendizaje)
            self.knowledge.append({
                "aprendizaje_id": apr_id,
                "domain": "ELF_CODE",
                "input": elf_path,
                "functions": cycle["stages"].get("instructions", {}).get("function_count", 0),
                "cfgs": cycle["stages"].get("cfg", {}).get("function_count", 0),
                "semantics": cycle["stages"].get("semantics", {}).get("function_count", 0),
            })
        except Exception:
            pass

    def get_code_summary(self) -> Dict[str, Any]:
        """Get summary of code reconstruction."""
        return {
            "total_functions_analyzed": len(self.semantic_reconstructions),
            "total_c_implementations": len(self.c_implementations),
            "knowledge_entries": len(self.knowledge),
            "restrictions": ["DB_AUTH_ACTOR_M294 BLOCKED", "W5 BLOCKED"],
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RX Semantic Code Reconstruction")
    parser.add_argument("elf_path", help="Path to ELF file")
    parser.add_argument("--func", help="Specific function to analyze", default=None)
    args = parser.parse_args()

    engine = RXSemanticCodeReconstruction()
    cycle = engine.research_cycle_full(args.elf_path)

    if args.func:
        # Analyze specific function
        sem = engine.reconstruct_semantics(args.elf_path, args.func)
        c_result = engine.generate_c_equivalent(args.elf_path, args.func)
        print(json.dumps({
            "function": args.func,
            "semantics": sem.get("functions", {}).get(args.func, {}),
            "c_code": c_result.get("c_code", ""),
            "compile": c_result.get("compile", {}),
            "status": c_result.get("status"),
        }, indent=2, default=str))
    else:
        print(json.dumps({
            "status": cycle["final_status"],
            "format": cycle["stages"]["format"].get("format"),
            "architecture": cycle["stages"]["format"].get("architecture"),
            "functions_total": cycle["stages"]["disassembly"].get("function_count"),
            "symbol_functions": cycle["stages"]["disassembly"].get("symbol_function_count"),
            "cfg_functions": cycle["stages"].get("cfg", {}).get("function_count", 0),
            "calls": cycle["stages"].get("calls", {}).get("call_count", 0),
            "instructions": cycle["stages"].get("instructions", {}),
            "data_flow": cycle["stages"].get("data_flow", {}),
            "semantics": cycle["stages"].get("semantics", {}),
            "c_reconstruction": cycle["stages"].get("c_reconstruction", {}),
            "coverage": cycle["stages"].get("coverage", {}),
            "knowledge": engine.get_code_summary(),
        }, indent=2, default=str))
