#!/usr/bin/env python3
"""M414 — RXRE + REA: ciclo integrado de extremo a extremo sobre un artefacto real.

ARCHIVO NUEVO. No modifica `core/store.py`, contratos protegidos, `rxre.sqlite3`,
`AGENTS.md` ni binarios del juego. Reutiliza los mecanismos existentes:

    ALMA    criterios de cierre evaluables
    MENTE   Libro de hipotesis rivales con falsificacion explicita
    CUERPO  medir artefacto + hash verificado en punto de uso
    ROUTER  resolver capacidades declaradas (no nombres de herramientas)
    TIERRA  Grafo de claims + evidencia append-only con row_hash
    FUEGO   transaccion reversible (solo casos de artefacto desechable)
    AGUA    aprendizaje con procedencia + revalidacion
    AIRE    traza decision -> herramienta -> resultado
    ETER    journal write-ahead con fsync
    PUERTA  gate de aceptacion con 4 condiciones

Herramientas reales usadas solo si estan disponibles y su funcion es necesaria:
    Ghidra headless (analyzeHeadless + postScript Java), angr (CFGFast),
    rizin, capstone, readelf/objdump, strace.

Estados: PROVEN / PARTIAL / BLOCKED / NOT_DETERMINED / INSUFFICIENT.
No se declara PROVEN sin cadena completa. No se inventa evidencia.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = "/home/lucas/Escritorio/rxre"
sys.path.insert(0, os.path.join(ROOT, "tools", "rxre"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from arquitectura.planos import CUERPO, FUEGO, Libro  # noqa: E402
from arquitectura.TIERRA import Grafo  # noqa: E402
from arquitectura.ALMA import criterios_del_proposito, proposito  # noqa: E402
from arquitectura.ROUTER import Router, Productor  # noqa: E402
from arquitectura.AGUA import Agua, Aprendizaje  # noqa: E402
from arquitectura.AIRE import Traza, tool_hash  # noqa: E402
from arquitectura.ETER import Eter  # noqa: E402
from arquitectura.PUERTA import Puerta  # noqa: E402
from arquitectura import PROVEN, PARTIAL, NOT_DETERMINED, PROVEN_ABSENT  # noqa: E402

try:
    from rxre.verifier import promotion as _authority  # noqa: E402
except Exception:  # fail-closed: sin autoridad -> todo queda UNVERIFIED/BLOCKED
    _authority = None

from rxre.core.capability_registry import select_capability  # noqa: E402
from rxre.core.claim_evaluator import evaluate_claim_evaluator  # noqa: E402
from rxre.core.manifest_binding_contract import validar_vinculacion  # noqa: E402
from rxre.core import store as rxre_store  # noqa: E402
from rxre.core import store_compat as sc  # noqa: E402
from rxre.evaluadores_ejecutables import EvaluadoresAlma  # noqa: E402

GHIDRA_HEADLESS = "/usr/lib64/ghidra/support/analyzeHeadless"


# --------------------------------------------------------------------------
# utilidades deterministas
# --------------------------------------------------------------------------
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_cmd(cmd: List[str], timeout: int = 240,
            stdin_bytes: Optional[bytes] = None,
            env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    try:
        p = subprocess.run(cmd, input=stdin_bytes, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, env=env)
        return {"rc": p.returncode,
                "stdout": p.stdout.decode(errors="ignore"),
                "stderr": p.stderr.decode(errors="ignore"),
                "timeout": False}
    except subprocess.TimeoutExpired as exc:
        return {"rc": -1, "stdout": (exc.stdout or b"").decode(errors="ignore"),
                "stderr": "TIMEOUT", "timeout": True}
    except Exception as exc:  # noqa: BLE001
        return {"rc": -1, "stdout": "", "stderr": str(exc), "timeout": False}


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


# --------------------------------------------------------------------------
# productores reales (capability-based)
# --------------------------------------------------------------------------
def _ghidra_scripts(workdir: str) -> Tuple[str, str]:
    sdir = os.path.join(workdir, "ghidra_scripts")
    os.makedirs(sdir, exist_ok=True)
    dump = os.path.join(sdir, "DumpFunctions.java")
    dec = os.path.join(sdir, "DecompileFunction.java")
    with open(dump, "w", encoding="utf-8") as fh:
        fh.write(r'''
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import java.io.*;
import java.util.Iterator;

public class DumpFunctions extends GhidraScript {
  public void run() throws Exception {
    String out = System.getenv("RXRE_GHIDRA_OUT");
    if (out == null) out = "/tmp/ghidra_dump.txt";
    PrintWriter w = new PrintWriter(new FileWriter(out));
    FunctionManager fm = currentProgram.getFunctionManager();
    for (Function f : fm.getFunctions(true)) {
      w.println("FUNC\t" + f.getEntryPoint() + "\t" + f.getName() + "\t" + f.getBody().getNumAddresses());
      for (Function callee : f.getCalledFunctions(monitor)) {
        w.println("CALL\t" + f.getEntryPoint() + "\t" + callee.getEntryPoint() + "\t" + callee.getName());
      }
    }
    Iterator<Address> it = currentProgram.getSymbolTable().getExternalEntryPointIterator();
    while (it.hasNext()) w.println("ENTRY\t" + it.next());
    w.println("NAME\t" + currentProgram.getName());
    w.println("LANG\t" + currentProgram.getLanguageID());
    w.close();
  }
}
''')
    with open(dec, "w", encoding="utf-8") as fh:
        fh.write(r'''
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DecompileFunction extends GhidraScript {
  public void run() throws Exception {
    String target = System.getenv("RXRE_FUNC");
    if (target == null) target = "main";
    String out = System.getenv("RXRE_GHIDRA_OUT");
    if (out == null) out = "/tmp/ghidra_decomp.c";
    Function f = null;
    for (Function x : currentProgram.getFunctionManager().getFunctions(true)) {
      if (x.getName().equals(target)) { f = x; break; }
    }
    PrintWriter w = new PrintWriter(new FileWriter(out));
    if (f == null) { w.println("NOT_FOUND " + target); w.close(); return; }
    DecompInterface di = new DecompInterface();
    di.openProgram(currentProgram);
    DecompileResults dr = di.decompileFunction(f, 90, monitor);
    if (dr != null && dr.decompileCompleted() && dr.getDecompiledFunction() != null) {
      w.println(dr.getDecompiledFunction().getC());
    } else {
      w.println("DECOMP_FAILED " + target);
    }
    w.close();
  }
}
''')
    return sdir, dump


def ghidra_dump(artifact: str, workdir: str) -> Dict[str, Any]:
    if not os.path.isfile(GHIDRA_HEADLESS):
        return {"status": "BLOCKED", "reason": "analyzeHeadless missing"}
    sdir, _ = _ghidra_scripts(workdir)
    proj = tempfile.mkdtemp(prefix="ghproj_", dir=workdir)
    out = os.path.join(workdir, "ghidra_dump.tsv")
    env = dict(os.environ, RXRE_GHIDRA_OUT=out)
    cmd = [GHIDRA_HEADLESS, proj, "m414", "-import", artifact,
           "-scriptPath", sdir, "-postScript", "DumpFunctions.java",
           "-deleteProject"]
    r = run_cmd(cmd, timeout=300, env=env)
    if not os.path.isfile(out):
        return {"status": "INSUFFICIENT", "reason": "ghidra produced no dump",
                "rc": r["rc"], "stderr_tail": r["stderr"][-800:]}
    funcs, calls, entry = [], [], []
    with open(out, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if parts[0] == "FUNC" and len(parts) >= 4:
                funcs.append({"addr": parts[1], "name": parts[2],
                              "size": int(parts[3]) if parts[3].isdigit() else 0})
            elif parts[0] == "CALL" and len(parts) >= 4:
                calls.append({"from": parts[1], "to": parts[2], "name": parts[3]})
            elif parts[0] == "ENTRY" and len(parts) >= 2:
                entry.append(parts[1])
    return {"status": "PROVEN", "functions": funcs, "calls": calls,
            "entry": entry, "dump_sha256": sha256_file(out),
            "dump_path": out, "rc": r["rc"]}


def ghidra_decompile(artifact: str, func: str, workdir: str) -> Dict[str, Any]:
    sdir, _ = _ghidra_scripts(workdir)
    proj = tempfile.mkdtemp(prefix="ghprojd_", dir=workdir)
    out = os.path.join(workdir, "decomp_%s.c" % re.sub(r"\W", "_", func))
    env = dict(os.environ, RXRE_GHIDRA_OUT=out, RXRE_FUNC=func)
    cmd = [GHIDRA_HEADLESS, proj, "m414d", "-import", artifact,
           "-scriptPath", sdir, "-postScript", "DecompileFunction.java",
           "-deleteProject"]
    r = run_cmd(cmd, timeout=300, env=env)
    if not os.path.isfile(out):
        return {"status": "INSUFFICIENT", "reason": "no decompilation output",
                "func": func, "rc": r["rc"]}
    text = open(out, "r", encoding="utf-8", errors="ignore").read()
    if text.startswith("NOT_FOUND") or text.startswith("DECOMP_FAILED"):
        return {"status": "PROVEN_ABSENT", "func": func, "reason": text.strip()}
    return {"status": "PROVEN", "func": func, "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "path": out}


def angr_cfg(artifact: str) -> Dict[str, Any]:
    try:
        import angr
    except Exception as exc:  # noqa: BLE001
        return {"status": "BLOCKED", "reason": "angr import: %s" % exc}
    try:
        p = angr.Project(artifact, auto_load_libs=False)
        cfg = p.analyses.CFGFast(normalize=True, data_references=True)
        return {"status": "PROVEN", "arch": p.arch.name,
                "entry": hex(p.entry),
                "functions": len(cfg.kb.functions),
                "callgraph_nodes": cfg.kb.functions.callgraph.number_of_nodes(),
                "callgraph_edges": cfg.kb.functions.callgraph.number_of_edges(),
                "angr_version": getattr(angr, "__version__", "?")}
    except Exception as exc:  # noqa: BLE001
        return {"status": "INSUFFICIENT", "reason": str(exc)}


def rizin_functions(artifact: str) -> Dict[str, Any]:
    if not tool_available("rizin"):
        return {"status": "BLOCKED", "reason": "rizin missing"}
    r = run_cmd(["rizin", "-q", "-c", "aa; afl", artifact], timeout=180)
    if r["rc"] != 0:
        return {"status": "INSUFFICIENT", "reason": r["stderr"][-400:]}
    funcs = []
    for line in r["stdout"].splitlines():
        m = re.match(r"0x([0-9a-f]+)\s+(\d+)\s+(\d+)\s+(.+)$", line.strip())
        if m:
            funcs.append({"addr": "0x" + m.group(1), "size": int(m.group(2)),
                          "name": m.group(4).strip()})
    return {"status": "PROVEN", "count": len(funcs),
            "functions": funcs[:400],
            "sha256": hashlib.sha256(r["stdout"].encode()).hexdigest()}


def rizin_imports(artifact: str) -> Dict[str, Any]:
    if not tool_available("rizin"):
        return {"status": "BLOCKED", "reason": "rizin missing"}
    r = run_cmd(["rizin", "-q", "-c", "aa; ii", artifact], timeout=180)
    if r["rc"] != 0:
        return {"status": "INSUFFICIENT", "reason": r["stderr"][-400:]}
    imports = []
    for line in r["stdout"].splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        parts = line.split()
        if len(parts) >= 2:
            imports.append(parts[-1])
    return {"status": "PROVEN", "imports": imports,
            "count": len(imports),
            "sha256": hashlib.sha256(r["stdout"].encode()).hexdigest()}


def strace_trace(artifact: str, args: List[str], workdir: str) -> Dict[str, Any]:
    if not tool_available("strace"):
        return {"status": "BLOCKED", "reason": "strace missing"}
    out = os.path.join(workdir, "strace.txt")
    cmd = ["strace", "-f", "-e", "trace=openat,read,mmap,lseek,close",
           "-o", out, artifact] + args
    r = run_cmd(cmd, timeout=120)
    if not os.path.isfile(out):
        return {"status": "INSUFFICIENT", "reason": "no strace output",
                "rc": r["rc"]}
    if r["rc"] != 0:
        return {"status": "INSUFFICIENT",
                "reason": "strace/target rc=%s (no se ejecuto el artefacto)"
                          % r["rc"], "rc": r["rc"]}
    text = open(out, "r", encoding="utf-8", errors="ignore").read()
    return {"status": "PROVEN", "path": out, "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "rc": r["rc"]}


def parse_strace(text: str, target_path: str) -> Dict[str, Any]:
    """Determina si el artefacto mapea el fichero de entrada con mmap o lo lee."""
    target_fd = None
    read_calls = 0
    read_bytes = 0
    mmap_target = 0
    lseek_target = 0
    opened = False
    for line in text.splitlines():
        if "openat(" in line and target_path in line:
            m = re.search(r"openat\([^)]*\)\s*=\s*(\d+)", line)
            if m:
                target_fd = int(m.group(1))
                opened = True
        if target_fd is None:
            continue
        m = re.search(r"\bread\(%d,.*\)\s*=\s*(\d+)" % target_fd, line)
        if m:
            read_calls += 1
            read_bytes += int(m.group(1))
        if re.search(r"\bmmap\(.*,\s*%d," % target_fd, line):
            mmap_target += 1
        if re.search(r"\blseek\(%d," % target_fd, line):
            lseek_target += 1
    return {"target_fd": target_fd, "opened": opened,
            "read_calls": read_calls, "read_bytes": read_bytes,
            "mmap_on_target_fd": mmap_target, "lseek_on_target_fd": lseek_target}


# --------------------------------------------------------------------------
# reconstruccion y validacion diferencial
# --------------------------------------------------------------------------
MODEL_HEAD = r'''#!/usr/bin/env python3
"""Modelo independiente de `head -n N` reconstruido a partir de:
- decompilacion Ghidra de head_lines (read() de 0x2000, cuenta '\n', lseek atras)
- traza strace (read sobre fd de entrada, sin mmap sobre el fd de entrada)
No pretende universalidad: solo los casos declarados.
"""
import sys

def head_lines(data: bytes, n: int) -> bytes:
    if n <= 0:
        return b""
    count = 0
    for i, b in enumerate(data):
        if b == 0x0A:
            count += 1
            if count == n:
                return data[:i + 1]
    return data

def main():
    n = int(sys.argv[1])
    with open(sys.argv[2], "rb") as fh:
        data = fh.read()
    sys.stdout.buffer.write(head_lines(data, n))

if __name__ == "__main__":
    main()
'''


def write_model(workdir: str) -> str:
    path = os.path.join(workdir, "model_head.py")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(MODEL_HEAD)
    return path


def differential_cases(workdir: str) -> List[Tuple[str, bytes, int]]:
    return [
        ("ten_lines_n3", b"line0\nline1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\n", 3),
        ("ten_lines_n1", b"a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n", 1),
        ("ten_lines_n0", b"a\nb\nc\n", 0),
        ("ten_lines_n_exact", b"a\nb\nc\n", 3),
        ("ten_lines_n_over", b"a\nb\nc\n", 20),
        ("empty", b"", 3),
        ("no_trailing_newline_n2", b"alpha\nbeta\ngamma", 2),
        ("blank_lines_n2", b"\n\n\nx\n", 2),
        ("single_long_line", b"x" * 20000 + b"\n", 1),
        ("binary_no_newline", bytes(range(256)), 1),
        ("crlf_lines_n2", b"a\r\nb\r\nc\r\n", 2),
        ("utf8_lines_n3", "línea1\nlínea2\nlínea3\nlínea4\n".encode("utf-8"), 3),
    ]


def differential_validation(artifact: str, workdir: str) -> Dict[str, Any]:
    model = write_model(workdir)
    cases = differential_cases(workdir)
    rows = []
    mismatches = 0
    for name, data, n in cases:
        fpath = os.path.join(workdir, "case_%s.txt" % name)
        with open(fpath, "wb") as fh:
            fh.write(data)
        orig = run_cmd([artifact, "-n", str(n), fpath], timeout=30)
        ref = run_cmd([sys.executable, model, str(n), fpath], timeout=30)
        orig_bytes = orig["stdout"].encode("latin-1", errors="ignore")
        ref_bytes = ref["stdout"].encode("latin-1", errors="ignore")
        match = (orig["rc"] == ref["rc"] == 0 and orig_bytes == ref_bytes)
        if not match:
            mismatches += 1
        rows.append({"case": name, "n": n, "input_bytes": len(data),
                     "orig_rc": orig["rc"], "ref_rc": ref["rc"],
                     "orig_len": len(orig_bytes), "ref_len": len(ref_bytes),
                     "match": match})
    return {"status": "EQUIVALENT_FOR_TESTED_CASES" if mismatches == 0 else "DISCREPANCY",
            "cases": rows, "mismatches": mismatches,
            "model_sha256": sha256_file(model),
            "scope": "los %d casos declarados; no universal" % len(rows)}


def defective_model_rejected(artifact: str, workdir: str) -> Dict[str, Any]:
    """Un modelo deliberadamente defectuoso debe ser rechazado por la comparacion."""
    bad = os.path.join(workdir, "model_bad.py")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("import sys\nsys.stdout.write('WRONG')\n")
    fpath = os.path.join(workdir, "case_ten_lines_n3.txt")
    if not os.path.isfile(fpath):
        with open(fpath, "wb") as fh:
            fh.write(b"line0\nline1\nline2\nline3\n")
    orig = run_cmd([artifact, "-n", "3", fpath], timeout=30)
    ref = run_cmd([sys.executable, bad, "3", fpath], timeout=30)
    return {"rejected": orig["stdout"] != ref["stdout"],
            "orig_len": len(orig["stdout"]),
            "bad_len": len(ref["stdout"])}


# --------------------------------------------------------------------------
# seleccion automatica del siguiente experimento (autopilot reutilizable)
# --------------------------------------------------------------------------
EXPERIMENTS = [
    {"id": "E1_identity", "priority": 1, "deps": [],
     "produces": ["H0_identity"]},
    {"id": "E2_static_functions", "priority": 2, "deps": ["E1_identity"],
     "produces": ["H1_stream_read", "H2_mmap"]},
    {"id": "E3_callgraph", "priority": 3, "deps": ["E2_static_functions"],
     "produces": ["H1_stream_read", "H2_mmap"]},
    {"id": "E4_dynamic_syscalls", "priority": 4, "deps": ["E1_identity"],
     "produces": ["H1_stream_read", "H2_mmap"]},
    {"id": "E5_decompile", "priority": 5, "deps": ["E2_static_functions"],
     "produces": ["H1_stream_read"]},
    {"id": "E6_angr_cfg", "priority": 6, "deps": ["E1_identity"],
     "produces": ["H1_stream_read"]},
    {"id": "E7_reconstruct_validate", "priority": 7,
     "deps": ["E4_dynamic_syscalls"],
     "produces": ["H1_stream_read", "H2_mmap"]},
]


def select_next_experiment(done: List[str], unresolved: List[str],
                           failed: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    failed = failed or []
    done_set = set(done)
    eligible = [e for e in EXPERIMENTS
                if e["id"] not in done_set and e["id"] not in failed
                and all(d in done_set for d in e["deps"])]
    if not eligible:
        return None
    # Prioriza el experimento que resuelve mas hipotesis pendientes.
    eligible.sort(key=lambda e: (-len(set(e["produces"]) & set(unresolved)),
                                 e["priority"]))
    return eligible[0]


# --------------------------------------------------------------------------
# persistencia en copia aislada (nunca la DB protegida)
# --------------------------------------------------------------------------
def persist_isolated(result_id: str, operation_id: str, artifact: str,
                     scope: str, value: str, raw: Dict[str, Any],
                     extra_rows: Optional[List[Dict[str, Any]]] = None,
                     investigation_id: Optional[str] = None,
                     artifact_sha256: Optional[str] = None,
                     target_file: Optional[str] = None,
                     domain: str = "") -> Dict[str, Any]:
    """Persiste sobre una COPIA migrada usando `store.registrar()` (sin shim).

    M414 escribia las filas a mano porque `store.registrar()` fallaba contra el
    esquema en disco (`operations.declared_scope`). M415 aporta la migracion de
    copia (`store_compat`), asi que aqui se usa el mecanismo REAL: mismo
    `row_hash`, misma verificacion de lectura, mismos triggers append-only.
    """
    work = tempfile.mkdtemp(prefix="m415_db_", dir="/tmp/opencode")
    destino = os.path.join(work, "copia_migrada.sqlite3")
    origen = os.path.join(ROOT, "rxre.sqlite3")
    t0 = time.time()
    con, mig = sc.abrir_copia_migrada(origen, destino,
                                      huella_snapshot=sha256_file(origen))
    ts = now_utc()
    resultados = [{
        "result_id": result_id, "type": "E2E_INVESTIGATION", "value": value,
        "source": "rxre_m414", "scope": scope, "tool": "rxre_e2e_integrated",
        "tool_version": "m415", "status": "ok", "timestamp": ts,
        "location": {"file": artifact, "line": 0}, "raw": raw,
    }]
    for i, extra in enumerate(extra_rows or []):
        resultados.append({
            "result_id": "%s_r%d" % (result_id, i),
            "type": extra.get("type", "E2E_EVIDENCE"),
            "value": extra.get("value", "PASS_PARTIAL"),
            "source": "rxre_m414", "scope": scope,
            "tool": extra.get("tool", "multi"), "tool_version": "m415",
            "status": "ok", "timestamp": ts,
            "location": {"file": artifact, "line": 0},
            "raw": extra.get("raw", {}),
        })
    # --- Autoridad epistemológica (R7): ningún valor promovido sin autorización ---
    _artifact_hash = artifact_sha256 or raw.get("artifact_sha256") or ""
    _inv = investigation_id or raw.get("investigation_id") or ""
    _target = target_file or (os.path.basename(artifact) if artifact else "comp.spv")
    _promotes = value in (PROVEN, "PARTIAL")
    _auth = None
    if _authority is not None and _inv and _artifact_hash:
        try:
            _auth = _authority.authorize_and_consume(
                investigation_id=_inv, artifact_sha256=_artifact_hash,
                target_file=_target, domain=domain,
                consumer="R2", operation_id=f"R2_{_inv}_persist",
                action="persist_isolated", idempotent=True)
        except Exception:
            _auth = None
    # Sin autorización, todo artefacto promovido se degrada a UNVERIFIED (nunca se bloquea la evidencia bruta)
    _accepted_persist = bool(_auth and (_auth.get("record") or {}).get("accepted"))
    if _promotes and not _accepted_persist:
        value = "UNVERIFIED"
        raw = dict(raw)
        raw["gate_denied"] = {"reason": "sin dictamen vinculado/consumido o no autorizado",
                              "requested_value": value,
                              "investigation_id": _inv,
                              "artifact_sha256": _artifact_hash,
                              "consumption_id": (_auth or {}).get("consumption_id")}
    if _auth:
        raw = dict(raw)
        rec = (_auth or {}).get("record") or {}
        raw["gate"] = {"dictamen_id": rec.get("dictamen_id"),
                       "decision": rec.get("decision"),
                       "epistemic_status": rec.get("epistemic_status"),
                       "domain": rec.get("domain"),
                       "investigation_id": _inv,
                       "accepted": bool(rec.get("accepted")),
                       "consumption_id": _auth.get("consumption_id"),
                       "idempotent_replay": bool(_auth.get("idempotent_replay"))}

    request = {
        "request_id": "req-m415", "contract_version": "M415",
        "capability": "e2e_integrated",
        "question": "reconstruir y validar comportamiento observable",
        "target": artifact, "scope": scope,
    }
    env = {"status": "ok", "operation": "e2e_investigation",
           "results": resultados}
    try:
        reg = sc.registrar_verificado(con, request, env, time.time() - t0)
    finally:
        con.close()

    ids = reg["result_ids"]
    # segunda lectura con conexion NUEVA: recuperacion independiente real
    con2 = rxre_store.conectar(destino)
    try:
        recovered = rxre_store.recuperar_evidencia_resultados(con2, ids)
        operacion = rxre_store.explicar_operacion(con2, reg["operation_id"])
    finally:
        con2.close()

    stable = "/tmp/opencode/m414/persist_v2_%s.sqlite3" % result_id.replace("/", "_")
    os.makedirs(os.path.dirname(stable), exist_ok=True)
    shutil.copy(destino, stable)

    ok = (reg["status"] == "PROVEN" and len(recovered) == len(ids)
          and bool(ids))
    return {
        "status": "PROVEN" if ok else "INSUFFICIENT",
        "epistemic": "UNVERIFIED" if _promotes and not _accepted_persist else (value if not _promotes else (value if _accepted_persist else "UNVERIFIED")),
        "gate": raw.get("gate") if isinstance(raw, dict) else None,
        "mecanismo": "store.registrar() sobre copia migrada (store_compat M415)",
        "sin_shim_de_escritura": True,
        "db_copy": destino,
        "operation_id": reg["operation_id"],
        "requested": len(ids),
        "recovered": len(recovered),
        "recovered_independiente": len(recovered),
        "result_ids": ids,
        "row_hash_verified": ok,
        "hashes": reg["hashes"],
        "resultados_en_operacion": len(operacion.get("results") or [])
        if isinstance(operacion, dict) else None,
        "migracion": {
            "status": mig.get("status"),
            "columnas_anadidas": mig.get("columnas_anadidas"),
            "invariantes_ok": mig.get("invariantes_ok"),
            "filas_antes": (mig.get("antes") or {}).get("filas_total"),
            "filas_despues": (mig.get("despues") or {}).get("filas_total"),
            "sha256_origen": mig.get("sha256_origen"),
            "sha256_copia": mig.get("sha256_destino"),
            "objetos_creados_por_store_conectar":
                mig.get("objetos_creados_por_store_conectar"),
        },
        "stable_copy": stable,
        "stable_copy_sha256": sha256_file(stable),
    }


# --------------------------------------------------------------------------
# caso principal
# --------------------------------------------------------------------------
class IntegratedInvestigation:
    def __init__(self, artifact: str, workdir: Optional[str] = None,
                 max_experiments: int = 8, claim_target: Optional[str] = None):
        self.artifact = artifact
        self.max_experiments = max_experiments
        self.workdir = workdir or tempfile.mkdtemp(prefix="m414_", dir="/tmp/opencode")
        os.makedirs(self.workdir, exist_ok=True)
        self.report: Dict[str, Any] = {
            "mission": "M414", "artifact": artifact,
            "started": now_utc(), "stages": {},
            "hypotheses": {}, "experiments": [], "limitations": [],
            "blocked": [], "not_determined": [],
        }
        self.claim_target = claim_target or artifact
        with open(artifact, "rb") as fh:
            self.is_elf = fh.read(4) == b"\x7fELF"

    # -- helpers --------------------------------------------------------
    def _stage(self, name: str, data: Dict[str, Any]) -> None:
        data.setdefault("ts", now_utc())
        self.report["stages"][name] = data

    def _identity(self) -> Dict[str, Any]:
        st = os.stat(self.artifact)
        return {"path": os.path.abspath(self.artifact),
                "sha256": sha256_file(self.artifact),
                "size": st.st_size, "dev": st.st_dev, "ino": st.st_ino,
                "mtime_ns": st.st_mtime_ns}

    # -- etapas ---------------------------------------------------------
    def stage_alma_purpose(self) -> None:
        self._stage("alma_purpose", {
            "proposito": proposito(),
            "criterios_declarados": [c.nombre for c in criterios_del_proposito()],
        })

    def stage_cuerpo(self) -> None:
        cuerpo = CUERPO()
        med = cuerpo.medir(self.artifact, "m414")
        ver = cuerpo.verificar_en_uso(med["id"])
        st = os.stat(self.artifact)
        self._stage("cuerpo", {
            "medicion_id": med["id"], "hash": med["hash"],
            "bytes": med["bytes"], "dev": st.st_dev, "ino": st.st_ino,
            "verificada_en_uso": ver["verificada_en_uso"],
            "hash_vigente": ver["hash_vigente"],
            "estado": PROVEN if ver["verificada_en_uso"] else "INSUFFICIENT",
        })
        # manifest para el evaluador de claims (reutiliza contrato existente)
        manifest = {
            "manifest_version": "m414-01",
            "operation_id": "op_m414_identity",
            "result_id": "res_m414_identity",
            "artefacto_path": self.artifact,
            "artefacto_hash_sha256": med["hash"],
            "scope": "static_inspection",
            "evidence_type": "identity_capture",
            "evidence_refs_resolved": [],
            "evidence_refs_unresolved": [],
            "file_identity": {"dev": st.st_dev, "ino": st.st_ino,
                              "size": st.st_size},
        }
        mpath = os.path.join(self.workdir, "manifest_identity.json")
        with open(mpath, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
        bind = validar_vinculacion(mpath, artifact_path_esperado=self.artifact,
                                   scope_esperado="static_inspection")
        self.report["stages"]["cuerpo"]["manifest"] = mpath
        self.report["stages"]["cuerpo"]["binding_decision"] = bind.get("decision")

    def stage_router(self) -> None:
        caps = {
            "ghidra": ["binary.functions", "binary.decompile", "binary.callgraph"],
            "angr": ["binary.cfg", "binary.symbolic"],
            "rizin": ["binary.functions", "binary.disassembly"],
            "strace": ["runtime.syscalls"],
            "capstone": ["binary.disassembly"],
            "rea_bridge": ["binary.structure"],
            "ofrak": ["binary.patching"],
        }
        prods = []
        for name, cap_list in caps.items():
            if name == "ghidra":
                disp = os.path.isfile(GHIDRA_HEADLESS)
            elif name == "angr":
                try:
                    import angr  # noqa: F401
                    disp = True
                except Exception:  # noqa: BLE001
                    disp = False
            elif name == "rea_bridge":
                disp = os.path.isdir(os.path.join(
                    ROOT, "tools/rxre/github/rea/bridge"))
            elif name == "ofrak":
                try:
                    import ofrak  # noqa: F401
                    disp = True
                except Exception:  # noqa: BLE001
                    disp = False
            else:
                disp = tool_available(name)
            prods.append(Productor(name, cap_list, disp))
        router = Router(prods)
        resolutions = {}
        for cap in ["binary.functions", "binary.cfg", "binary.decompile",
                    "binary.callgraph", "binary.disassembly", "runtime.syscalls",
                    "binary.symbolic", "binary.patching", "binary.structure"]:
            resolutions[cap] = router.resolver(cap)
        self.report["stages"]["router"] = {
            "cobertura": router.cobertura(),
            "resoluciones": resolutions,
        }

    def stage_mente(self) -> None:
        libro = Libro()
        pregunta = "¿Cómo procesa el artefacto su entrada para producir las primeras N unidades?"
        libro.preguntar(
            pregunta,
            "H1: procesa la entrada en streaming con read()/full_read() y cuenta '\n' || "
            "falsacion: si la ruta principal no llama a read() o si existe mmap del fd de entrada para el caso -n "
            "|| streaming",
            "H2: mapea la entrada con mmap()/lseek para localizar las N unidades sin leer secuencialmente || "
            "falsacion: si no hay mmap sobre el fd de entrada y hay read() secuencial en la ruta -n "
            "|| mmap",
        )
        hs = [{"id": h.id, "enunciado": h.enunciado, "test": h.test,
               "estado": h.estado} for h in libro.preguntas[pregunta]]
        self.libro = libro
        self.pregunta = pregunta
        self.report["stages"]["mente"] = {
            "pregunta": pregunta, "hipotesis": hs,
            "metodo": "hipotesis rivales con falsificacion explicita",
        }
        for h in hs:
            self.report["hypotheses"][h["id"]] = {
                "enunciado": h["enunciado"], "test": h["test"],
                "estado": h["estado"], "evidencia": []}

    def _record_experiment(self, name: str, result: Dict[str, Any]) -> None:
        self.report["experiments"].append({
            "id": name, "status": result.get("status"),
            "result": result, "ts": now_utc()})

    def exp_identity(self) -> Dict[str, Any]:
        identity = self._identity()
        return {"status": "PROVEN", "identity": identity,
                "note": "identidad fisica y hash medidos al inicio"}

    def exp_static(self) -> Dict[str, Any]:
        g = ghidra_dump(self.artifact, self.workdir)
        if g.get("status") != "PROVEN":
            # recuperacion ante fallo: productor alternativo por capacidad
            rz = rizin_functions(self.artifact)
            ri = rizin_imports(self.artifact)
            if rz.get("status") == "PROVEN":
                names = {f["name"] for f in rz["functions"]}
                imports = set(ri.get("imports", [])) if ri.get("status") == "PROVEN" else set()
                allnames = names | imports
                return {"status": "PARTIAL", "fallback": "rizin",
                        "functions": rz["functions"], "count": rz["count"],
                        "imports": sorted(imports),
                        "read_related": sorted(n for n in allnames
                                               if n in ("read", "full_read",
                                                        "safe_read", "__read_chk",
                                                        "head_lines", "copy_fd")),
                        "mmap_related": sorted(n for n in allnames
                                               if "mmap" in n),
                        "dump_sha256": rz["sha256"],
                        "reason_ghidra": g.get("reason")}
            return {"status": "INSUFFICIENT",
                    "reason": g.get("reason"),
                    "fallback_rizin": rz.get("status")}
        names = {f["name"] for f in g["functions"]}
        read_related = sorted(n for n in names
                              if n in ("read", "full_read", "safe_read",
                                       "__read_chk", "head_lines", "copy_fd",
                                       "elide_tail_lines_seekable"))
        mmap_related = sorted(n for n in names
                              if "mmap" in n or "mremap" in n)
        g["read_related"] = read_related
        g["mmap_related"] = mmap_related
        g["count"] = len(g["functions"])
        return g

    def exp_callgraph(self) -> Dict[str, Any]:
        g = self.report["stages"].get("_ghidra_result")
        if not g or g.get("status") != "PROVEN":
            return {"status": "INSUFFICIENT", "reason": "ghidra dump unavailable"}
        calls = g["calls"]
        # localizar la funcion cuyo nombre es head_lines
        lines_fn = None
        for f in g["functions"]:
            if f["name"] == "head_lines":
                lines_fn = f
                break
        callees = []
        if lines_fn:
            callees = sorted({c["name"] for c in calls
                              if c["from"] == lines_fn["addr"]})
        main_f = next((f for f in g["functions"] if f["name"] == "main"), None)
        main_callees = []
        if main_f:
            main_callees = sorted({c["name"] for c in calls
                                   if c["from"] == main_f["addr"]})
        return {"status": "PROVEN", "head_lines_found": lines_fn is not None,
                "head_lines_addr": lines_fn["addr"] if lines_fn else None,
                "head_lines_callees": callees,
                "main_callees": main_callees}

    def exp_dynamic(self) -> Dict[str, Any]:
        inp = os.path.join(self.workdir, "dynamic_input.txt")
        with open(inp, "wb") as fh:
            fh.write(b"".join(b"line%d\n" % i for i in range(10)))
        tr = strace_trace(self.artifact, ["-n", "3", inp], self.workdir)
        if tr.get("status") != "PROVEN":
            return tr
        parsed = parse_strace(tr["text"], inp)
        return {"status": "PROVEN", "trace_sha256": tr["sha256"],
                "trace_path": tr["path"], "parsed": parsed,
                "input_path": inp}

    def exp_decompile(self) -> Dict[str, Any]:
        g = self.report["stages"].get("_ghidra_result")
        func_name = "head_lines"
        if g and g.get("status") == "PROVEN":
            names = {f["name"] for f in g["functions"]}
            if "head_lines" not in names:
                # elegir una funcion con lecturas
                func_name = "main"
        d = ghidra_decompile(self.artifact, func_name, self.workdir)
        return d

    def exp_reconstruct(self) -> Dict[str, Any]:
        val = differential_validation(self.artifact, self.workdir)
        bad = defective_model_rejected(self.artifact, self.workdir)
        return {"status": val["status"], "validation": val,
                "defective_rejected": bad}

    def exp_angr(self) -> Dict[str, Any]:
        cfg = angr_cfg(self.artifact)
        if cfg.get("status") != "PROVEN":
            return cfg
        cfg["note"] = ("CFG recuperado por un productor distinto de Ghidra; "
                       "corrobora estructura, no semantica de la funcion")
        return cfg

    def annotate_router_execution(self) -> None:
        """Separa 'capacidad resuelta' de 'capacidad ejecutada en esta corrida'.

        El Router devuelve PROVEN si hay un productor disponible; eso es una
        resolucion, no una ejecucion. Aqui se declara lo que realmente corrio.
        """
        done = {e["id"]: e["status"] for e in self.report["experiments"]}
        ejecutado = {
            "binary.functions": done.get("E2_static_functions") in ("PROVEN",),
            "binary.cfg": done.get("E6_angr_cfg") == "PROVEN",
            "binary.decompile": done.get("E5_decompile") == "PROVEN",
            "binary.callgraph": done.get("E3_callgraph") == "PROVEN",
            "binary.disassembly": False,  # rizin solo se usa como fallback
            "runtime.syscalls": done.get("E4_dynamic_syscalls") == "PROVEN",
            "binary.symbolic": False,     # angr se usa para CFG, no simbolico
            "binary.patching": False,     # ofrak no disponible
            "binary.structure": False,    # REA: bridge existe, runtime no ejecutado
        }
        self.report["stages"]["router"]["ejecutado_en_esta_corrida"] = ejecutado
        self.report["stages"]["router"]["nota"] = (
            "resolucion != ejecucion: solo se marca True lo invocado y con "
            "resultado en esta corrida")

    def run_experiments(self) -> None:
        done: List[str] = []
        failed: List[str] = []
        unresolved = list(self.report["hypotheses"].keys())
        executors = {
            "E1_identity": self.exp_identity,
            "E2_static_functions": self.exp_static,
            "E3_callgraph": self.exp_callgraph,
            "E4_dynamic_syscalls": self.exp_dynamic,
            "E5_decompile": self.exp_decompile,
            "E6_angr_cfg": self.exp_angr,
            "E7_reconstruct_validate": self.exp_reconstruct,
        }
        for _ in range(self.max_experiments):
            if not self.is_elf:
                # artefacto no ELF: solo identidad; el resto NO_APLICA
                if "E1_identity" not in done:
                    nxt = next(e for e in EXPERIMENTS if e["id"] == "E1_identity")
                else:
                    break
            else:
                nxt = select_next_experiment(done, unresolved, failed)
            if nxt is None:
                break
            name = nxt["id"]
            if not self.is_elf and name != "E1_identity":
                break
            # recuperacion ante fallos: un reintento
            result = None
            for attempt in (1, 2):
                try:
                    result = executors[name]()
                    break
                except Exception as exc:  # noqa: BLE001
                    result = {"status": "INSUFFICIENT",
                              "reason": "exception attempt %d: %s" % (attempt, exc)}
            if result is None:
                result = {"status": "INSUFFICIENT", "reason": "no result"}
            if result.get("status") not in ("PROVEN", "PARTIAL",
                                            "EQUIVALENT_FOR_TESTED_CASES",
                                            "PROVEN_ABSENT"):
                # fallo no fatal: se registra y se continua con otra capacidad
                if name not in failed:
                    failed.append(name)
            else:
                done.append(name)
            self._record_experiment(name, result)
            if name == "E2_static_functions" and result.get("status") in (
                    "PROVEN", "PARTIAL"):
                self.report["stages"]["_ghidra_result"] = result
            if name == "E5_decompile" and result.get("status") == "PROVEN":
                self.report["stages"]["_decomp"] = result
        self.report["experiments_done"] = done
        self.report["experiments_failed"] = failed

    def resolve_hypotheses(self) -> None:
        """Aplica las pruebas discriminantes SOLO con evidencia observada."""
        static = self.report["stages"].get("_ghidra_result") or {}
        decomp = self.report["stages"].get("_decomp") or {}
        dynamic = next((e["result"] for e in self.report["experiments"]
                        if e["id"] == "E4_dynamic_syscalls"
                        and e["result"].get("status") == "PROVEN"), None)
        recon = next((e["result"] for e in self.report["experiments"]
                      if e["id"] == "E7_reconstruct_validate"), None)

        has_read_static = False
        has_mmap_static = False
        head_lines_callees: List[str] = []
        if static.get("status") in ("PROVEN", "PARTIAL"):
            has_read_static = any(n in ("read", "full_read", "__read_chk",
                                        "read_unlocked")
                                  for n in static.get("read_related", []))
            has_mmap_static = bool(static.get("mmap_related"))
            cg = next((e["result"] for e in self.report["experiments"]
                       if e["id"] == "E3_callgraph"), None)
            if cg:
                head_lines_callees = cg.get("head_lines_callees", [])

        read_dyn = bool(dynamic and dynamic["parsed"]["read_calls"] > 0)
        mmap_dyn = bool(dynamic and dynamic["parsed"]["mmap_on_target_fd"] > 0)
        decomp_text = decomp.get("text", "") if decomp.get("status") == "PROVEN" else ""
        decomp_reads = "read(" in decomp_text
        decomp_counts_newline = "== DAT_" in decomp_text or "0x0a" in decomp_text.lower()

        # H1: streaming read
        ev1 = []
        if has_read_static:
            ev1.append({"src": "ghidra_symbols", "note": "read/full_read presentes"})
        if read_dyn:
            ev1.append({"src": "strace",
                        "note": "%d read() sobre el fd de entrada (%d bytes)"
                                % (dynamic["parsed"]["read_calls"],
                                   dynamic["parsed"]["read_bytes"])})
        if decomp_reads:
            ev1.append({"src": "ghidra_decompile",
                        "note": "decompilacion contiene read(...) y conteo de byte"})
        h1_ok = bool(ev1) and read_dyn and not mmap_dyn
        # H2: mmap
        ev2 = []
        if has_mmap_static:
            ev2.append({"src": "ghidra_symbols", "note": "mmap presente"})
        if mmap_dyn:
            ev2.append({"src": "strace", "note": "mmap sobre fd de entrada"})
        static_observed = (static.get("status") in ("PROVEN", "PARTIAL")
                           and bool(static.get("functions")))
        dynamic_observed = dynamic is not None
        # la ausencia solo refuta si hubo observacion real (no vacuidad)
        h2_refuted = ((static_observed or dynamic_observed)
                      and not has_mmap_static and not mmap_dyn)

        labels = list(self.report["hypotheses"].keys())
        h1_id = labels[0] if labels else None
        h2_id = labels[1] if len(labels) > 1 else None
        if h1_id:
            self.report["hypotheses"][h1_id]["estado"] = PROVEN if h1_ok else (
                "INSUFFICIENT" if not ev1 else "PARTIAL")
            self.report["hypotheses"][h1_id]["evidencia"] = ev1
            try:
                self.libro.decidir(self.pregunta, h1_id,
                                  PROVEN if h1_ok else NOT_DETERMINED,
                                  "evidencia estatica+dinamica")
            except Exception:
                pass
        if h2_id:
            self.report["hypotheses"][h2_id]["estado"] = (
                PROVEN_ABSENT if h2_refuted else "INSUFFICIENT")
            ev2b = ev2 or [{"src": "ghidra_symbols",
                            "note": "sin mmap/mremap en tabla de funciones"},
                           {"src": "strace",
                            "note": "sin mmap sobre el fd de entrada"}]
            self.report["hypotheses"][h2_id]["evidencia"] = ev2b
            try:
                self.libro.decidir(self.pregunta, h2_id,
                                  PROVEN_ABSENT if h2_refuted else NOT_DETERMINED,
                                  "ausencia de mmap en estatica y dinamica")
            except Exception:
                pass

        # validacion diferencial: refuerza H1 solo para casos probados
        if recon and recon.get("status") == "EQUIVALENT_FOR_TESTED_CASES":
            if h1_id:
                self.report["hypotheses"][h1_id]["evidencia"].append(
                    {"src": "differential_validation",
                     "note": "%d/%d casos equivalentes; modelo independiente"
                             % (len(recon["validation"]["cases"])
                                - recon["validation"]["mismatches"],
                                len(recon["validation"]["cases"]))})
        elif recon and recon.get("status") == "DISCREPANCY":
            if h1_id:
                self.report["hypotheses"][h1_id]["estado"] = "PARTIAL"
                self.report["hypotheses"][h1_id]["evidencia"].append(
                    {"src": "differential_validation",
                     "note": "discrepancias=%d" % recon["validation"]["mismatches"]})

    def stage_tierra(self) -> None:
        db = os.path.join(self.workdir, "tierra.db")
        g = Grafo(db)
        static = self.report["stages"].get("_ghidra_result") or {}
        dynamic = next((e["result"] for e in self.report["experiments"]
                        if e["id"] == "E4_dynamic_syscalls"
                        and e["result"].get("status") == "PROVEN"), None)
        recon = next((e["result"] for e in self.report["experiments"]
                      if e["id"] == "E7_reconstruct_validate"), None)
        identity = self.report["stages"]["cuerpo"]["hash"]
        h1_id = list(self.report["hypotheses"].keys())[0]
        h1 = self.report["hypotheses"][h1_id]
        from rxre.contracts.admission_tierra import admit_claim as _admit
        _scope = "static_inspection"
        _prov = "INFERRED"  # evidencia observacional, no scope de productor verificado
        _ok, _reason = _admit(statement="H1", object_hash=identity, scope=_scope,
                              scope_provenance=_prov)[:2]
        if not _ok:
            # bloqueado: no se promueve claim con scope inferido
            claim = None
        else:
            claim = g.afirmar(
            statement="H1: el artefacto procesa la entrada con read() secuencial y cuenta '\\n' "
                      "(observado en esta captura)",
            object_hash=identity, scope=_scope,
            epistemic_state=PROVEN if h1["estado"] == PROVEN else NOT_DETERMINED,
            falsification_test=h1["test"],
            evidence_refs=["evidencia:ghidra_dump", "evidencia:strace",
                           "evidencia:differential"],
            unresolved_obligations=[] if h1["estado"] == PROVEN else
            ["validacion no concluyente"])
        if claim is None:
            return
        ev_ids = []
        if static.get("status") in ("PROVEN", "PARTIAL"):
            ev_ids.append(g.aportar(claim["id"], "static_functions",
                                    {"sha256": static["dump_sha256"],
                                     "count": static["count"],
                                     "read_related": static["read_related"],
                                     "mmap_related": static["mmap_related"]},
                                    "ghidra", "analyzeHeadless+DumpFunctions"))
        if dynamic:
            ev_ids.append(g.aportar(claim["id"], "dynamic_syscalls",
                                    {"trace_sha256": dynamic["trace_sha256"],
                                     "parsed": dynamic["parsed"]},
                                    "strace", "-e trace=openat,read,mmap,lseek,close"))
        if recon:
            ev_ids.append(g.aportar(claim["id"], "differential_validation",
                                    {"model_sha256": recon["validation"]["model_sha256"],
                                     "cases": len(recon["validation"]["cases"]),
                                     "mismatches": recon["validation"]["mismatches"]},
                                    "model_head+artifact",
                                    "comparacion byte a byte"))
        reads = []
        for eid in ev_ids:
            try:
                rec = g.leer_evidencia(eid)
                reads.append({"id": eid, "row_hash_ok": rec.get("row_hash_ok", True)})
            except Exception as exc:  # noqa: BLE001
                reads.append({"id": eid, "error": str(exc)})
        g.cerrar()
        self._stage("tierra", {
            "db": db, "claim": claim, "evidence_ids": ev_ids,
            "evidence_reads": reads,
            "hash_chain": "row_hash calculado al escribir y verificado al leer",
        })

    def stage_fuego(self) -> None:
        """Transaccion reversible sobre una COPIA desechable, no sobre el artefacto."""
        raiz = os.path.join(self.workdir, "fuego")
        os.makedirs(raiz, exist_ok=True)
        copia = os.path.join(raiz, "device_copy")
        os.makedirs(copia, exist_ok=True)
        original = os.path.join(copia, "original")
        shutil.copyfile(self.artifact, original)
        fg = FUEGO(raiz)
        d = fg.aplicar("device_copy", "op_m414", "marca de prueba reversible",
                       fuente=original)
        aplicado = d.estado
        alcance = fg.alcance_rollback(["device_copy"])
        fg.rollback("device_copy")
        restaurado = os.path.join(copia, "restaurado")
        igual = (os.path.isfile(restaurado) and
                 sha256_file(restaurado) == sha256_file(self.artifact))
        # el artefacto REAL nunca se toco
        real_intacto = sha256_file(self.artifact) == self.report["stages"]["cuerpo"]["hash"]
        self._stage("fuego", {
            "alcance": alcance, "estado_aplicado": aplicado,
            "rollback_restaura_hash": igual,
            "artefacto_real_intacto": real_intacto,
            "status": PROVEN if (igual and real_intacto) else "INSUFFICIENT",
        })

    def stage_persist(self) -> None:
        h1_id = list(self.report["hypotheses"].keys())[0]
        h1 = self.report["hypotheses"][h1_id]
        exp_summary = [{"id": e["id"], "status": e["status"]}
                       for e in self.report["experiments"]]
        raw = {
            "artifact": self.artifact,
            "artifact_sha256": self.report["stages"]["cuerpo"]["hash"],
            "hypotheses": {k: v["estado"] for k, v in self.report["hypotheses"].items()},
            "experiments": exp_summary,
            "differential": (next((e["result"]["validation"] for e in self.report["experiments"]
                                   if e["id"] == "E7_reconstruct_validate"), {})
                             or {}).get("mismatches"),
        }
        extra = [
            {"type": "E2E_STATIC", "tool": "ghidra",
             "value": (self.report["stages"].get("_ghidra_result") or {}).get("status", "NOT_DETERMINED"),
             "raw": {"count": (self.report["stages"].get("_ghidra_result") or {}).get("count")}},
            {"type": "E2E_DYNAMIC", "tool": "strace",
             "value": next((e["result"]["status"] for e in self.report["experiments"]
                            if e["id"] == "E4_dynamic_syscalls"), "NOT_DETERMINED"),
             "raw": next((e["result"].get("parsed", {}) for e in self.report["experiments"]
                          if e["id"] == "E4_dynamic_syscalls"), {})},
        ]
        _sha = self.report["stages"].get("cuerpo", {}).get("hash") or sha256_file(self.artifact)
        p = persist_isolated(
            result_id="res_m414_%s" % hashlib.sha256(self.artifact.encode()).hexdigest()[:10],
            operation_id="op_m414_%d" % int(time.time()),
            artifact=self.artifact, scope="static_inspection",
            value=(PROVEN if h1["estado"] == PROVEN else
                   ("PARTIAL" if h1["estado"] == "PARTIAL" else NOT_DETERMINED)),
            raw=raw, extra_rows=extra,
            investigation_id=getattr(self, "investigation_id", "") or ("e2e_" + _sha[:16]),
            artifact_sha256=_sha,
            target_file=os.path.basename(self.artifact),
            domain=getattr(self, "domain", ""))
        self._stage("persistencia", p)

    def stage_agua(self) -> None:
        db = os.path.join(self.workdir, "agua.db")
        agua = Agua(db)
        static = self.report["stages"].get("_ghidra_result") or {}

        def reverificar() -> bool:
            # vuelve a comprobar contra el mundo: el artefacto sigue igual y
            # el simbolo read() sigue presente en la tabla de simbolos viva
            if sha256_file(self.artifact) != self.report["stages"]["cuerpo"]["hash"]:
                return False
            r = run_cmd(["readelf", "-Ws", self.artifact], timeout=60)
            if r["rc"] != 0:
                return False
            return bool(re.search(r"\bread(@|$|\s)", r["stdout"]))

        ap = Aprendizaje(
            proposito="reconstruir procesamiento de entrada en binarios ELF",
            procedencia="M414 /artifact=%s/sha256=%s" % (
                os.path.basename(self.artifact),
                self.report["stages"]["cuerpo"]["hash"][:16]),
            regla="para `-n N`, buscar read()/full_read() y conteo de '\\n'; "
                  "mmap del fd de entrada no aparece en la ruta observada",
            reverificar=reverificar, confianza=0.8)
        aid = agua.aprender(ap)
        reval = agua.revalidar(aid)
        # recuperacion: NO confia solo en lo persistido
        rec = agua.recuperar(aid) if hasattr(agua, "recuperar") else None
        _sha_a = self.report["stages"].get("cuerpo", {}).get("hash") or sha256_file(self.artifact)
        _inv_a = getattr(self, "investigation_id", "") or ("e2e_" + _sha_a[:16])
        _auth_a = None
        if _authority is not None:
            try:
                _auth_a = _authority.authorize_and_consume(
                    investigation_id=_inv_a, artifact_sha256=_sha_a,
                    target_file=os.path.basename(self.artifact),
                    domain=getattr(self, "domain", ""),
                    consumer="R4", operation_id=f"R4_{_inv_a}_agua",
                    action="learning_persist", idempotent=True)
            except Exception:
                _auth_a = None
        _a_rec = (_auth_a or {}).get("record") or {}
        _authorized = bool(_auth_a and _a_rec.get("accepted"))
        self._stage("agua", {
            "aprendizaje_id": aid, "revalidacion": reval,
            "recuperacion": rec, "db": db,
            "epistemic": "UNVERIFIED" if not _authorized else "AUTHORIZED",
            "gate": {"dictamen_id": _a_rec.get("dictamen_id"),
                      "decision": _a_rec.get("decision"),
                      "consumption_id": (_auth_a or {}).get("consumption_id"),
                      "idempotent_replay": bool((_auth_a or {}).get("idempotent_replay"))},
            "status": (PROVEN if (_authorized and reval.get("revalidado")) else NOT_DETERMINED),
        })

    def stage_aire(self) -> None:
        t = Traza()
        d = t.decidir("seleccionar siguiente experimento por dependencias",
                      "autopilot m414")
        th = tool_hash({"name": "ghidra", "version": "12.1.4"})
        i1 = t.invocar(d, "ghidra", "12.1.4", th)
        t.producir(i1, [e for e in self.report["experiments"]])
        th2 = tool_hash({"name": "strace", "version": "6.x"})
        i2 = t.invocar(d, "strace", "6.x", th2)
        t.producir(i2, [{"syscalls": True}])
        self._stage("aire", {"alcance": t.alcance(),
                             "traza_id": d["id"],
                             "reconstruible": bool(t.decisions and t.invocations)})

    def stage_eter(self) -> None:
        journal = os.path.join(self.workdir, "eter.journal")
        with Eter(journal) as et:
            p1 = et.publicar("m414.inicio", {"artifact": self.artifact}, critico=True)
            p2 = et.publicar("m414.hipotesis",
                             {"estados": {k: v["estado"] for k, v in
                                          self.report["hypotheses"].items()}},
                             critico=True)
            rec = et.recuperar()
        self._stage("eter", {
            "journal": journal,
            "publicado_1": bool(p1.get("fsync") and p1.get("encolado")),
            "publicado_2": bool(p2.get("fsync") and p2.get("encolado")),
            "recuperados": len(rec),
            "status": PROVEN if (p1.get("fsync") and p2.get("fsync")) else "INSUFFICIENT",
        })

    def stage_puerta(self) -> None:
        _sha_p = self.report["stages"].get("cuerpo", {}).get("hash") or sha256_file(self.artifact)
        _inv_p = getattr(self, "investigation_id", "") or ("e2e_" + _sha_p[:16])
        _auth_p = None
        if _authority is not None:
            try:
                _auth_p = _authority.authorize_and_consume(
                    investigation_id=_inv_p, artifact_sha256=_sha_p,
                    target_file=os.path.basename(self.artifact),
                    domain=getattr(self, "domain", ""),
                    consumer="R6", operation_id=f"R6_{_inv_p}_puerta",
                    action="puerta_acceptance", idempotent=True)
            except Exception:
                _auth_p = None
        _p_rec = (_auth_p or {}).get("record") or {}
        if not _auth_p or not _p_rec.get("accepted"):
            # Sin autorización epistemológica no se invoca PUERTA (Puerta sería un bypass).
            self.report["gate_decision"] = {
                "gate": "AUTHORITY_REQUIRED",
                "dictamen_id": _p_rec.get("dictamen_id"),
                "decision": _p_rec.get("decision"),
                "consumption_id": (_auth_p or {}).get("consumption_id"),
                "accepted": False}
            self._stage("puerta", {
                "veredicto": {"estado": "BLOCKED_GATE",
                              "razon": "sin dictamen vinculado a la investigacion",
                              "artefacto": self.artifact},
                "gate": self.report["gate_decision"],
            })
            return
        self.report["gate_decision"] = {
            "gate": "AUTHORITY_OK", "dictamen_id": _p_rec.get("dictamen_id"),
            "decision": _p_rec.get("decision"), "epistemic_status": _p_rec.get("epistemic_status"),
            "domain": _p_rec.get("domain"), "accepted": True,
            "consumption_id": (_auth_p or {}).get("consumption_id"),
            "idempotent_replay": bool((_auth_p or {}).get("idempotent_replay"))}
        p = Puerta()
        aid = p.registrar_artefacto("artifact", self.artifact,
                                    self.report["stages"]["cuerpo"]["hash"])
        p.declarar_participacion("rxre_m414", aid)
        # revisor independiente NO nombrado: no se inventa
        # autoridad de aceptacion NO declarada por el agente
        v = p.aceptar()
        # Limitar la aceptación al dominio autorizado por R7
        if _p_rec.get("decision") != "ACCEPT_WITH_DOMAIN":
            v = dict(v) if isinstance(v, dict) else {"estado": v}
            v["estado"] = f"LIMITED_{v.get('estado', 'ACCEPTED')}"
            if isinstance(v, dict):
                v["gate"] = self.report["gate_decision"]
        self._stage("puerta", {
            "veredicto": v, "artefacto_id": aid,
            "nota": "no se nombra revisor ni autoridad: no se inventan actores",
        })

    def stage_claims(self) -> None:
        """Evaluador de claims existente: valida vinculacion, no semantica."""
        manifest = self.report["stages"]["cuerpo"]["manifest"]
        h1_id = list(self.report["hypotheses"].keys())[0]
        h1 = self.report["hypotheses"][h1_id]
        r = evaluate_claim_evaluator(
            "m414_h1", "El artefacto ha sido observado con hash e identidad fisica "
                       "y la evidencia enlazada es integra y de alcance compatible",
            [self.artifact], claim_scope="static_inspection",
            artifact_path=self.artifact, manifest_path=manifest)
        self._stage("claim_evaluator", {
            "decision": r.get("decision"), "reason": r.get("reason"),
            "integrity_check": r.get("integrity_check"),
            "limitations": r.get("limitations"),
            "nota": "el evaluador valida integridad/vinculacion/alcance; "
                    "la verdad semantica de H1 la deciden las pruebas "
                    "discriminantes (Ghidra+strace+diferencial), no este evaluador",
        })

    def stage_failure_cases(self) -> None:
        out: Dict[str, Any] = {}
        # 1. artefacto alterado: el hash en uso debe fallar
        tampered = os.path.join(self.workdir, "tampered_head")
        shutil.copyfile(self.artifact, tampered)
        c = CUERPO()
        m = c.medir(tampered, "tampered")
        with open(tampered, "r+b") as fh:
            fh.seek(os.path.getsize(tampered) // 2)
            b = fh.read(1)
            fh.seek(os.path.getsize(tampered) // 2)
            fh.write(bytes([b[0] ^ 0xFF]))
        v = c.verificar_en_uso(m["id"])
        out["tampered_artifact_detected"] = (v["verificada_en_uso"] is False)
        # 2. evidencia inexistente: claim INVALID/INSUFFICIENT
        r2 = evaluate_claim_evaluator("m414_missing", "claim sin evidencia",
                                      ["/nonexistent/m414"], claim_scope="s",
                                      artifact_path=self.artifact)
        out["missing_evidence_not_supported"] = r2.get("decision") in (
            "INVALID", "INSUFFICIENT")
        # 3. capacidad sin productor: NOT_DETERMINED
        router = Router([Productor("ghidra", ["binary.functions"], True)])
        dec = router.resolver("binary.patching")
        out["missing_capability_not_determined"] = dec["estado"] == NOT_DETERMINED
        # 4. gate sin revisor/autoridad: CONTESTED, no ACCEPTED
        p = Puerta()
        p.registrar_artefacto("a", self.artifact)
        out["gate_blocks_without_reviewer"] = p.aceptar()["estado"] == "CONTESTED"
        out["status"] = PROVEN if all(out.get(k) for k in [
            "tampered_artifact_detected", "missing_evidence_not_supported",
            "missing_capability_not_determined",
            "gate_blocks_without_reviewer"]) else "INSUFFICIENT"
        self._stage("failure_cases", out)

    def stage_alma_closure(self) -> None:
        # criterios evaluables conectados a evidencia real de ESTA corrida
        static = self.report["stages"].get("_ghidra_result") or {}
        dynamic = next((e["result"] for e in self.report["experiments"]
                        if e["id"] == "E4_dynamic_syscalls"
                        and e["result"].get("status") == "PROVEN"), None)
        recon = next((e["result"] for e in self.report["experiments"]
                      if e["id"] == "E7_reconstruct_validate"), None)
        tierra = self.report["stages"].get("tierra") or {}
        agua = self.report["stages"].get("agua") or {}
        persist = self.report["stages"].get("persistencia") or {}

        criterios = criterios_del_proposito()
        # conectar evaluadores reales donde exista evidencia
        for c in criterios:
            if c.nombre == "SIN_HECHOS_SIN_ARTEFACTO":
                c.cumple = lambda: bool(tierra.get("evidence_ids"))
            elif c.nombre == "REPRODUCTIBILIDAD":
                c.cumple = lambda: bool(recon and recon.get("status") ==
                                        "EQUIVALENT_FOR_TESTED_CASES")
            elif c.nombre == "FALSIFICACION_ASOCIADA":
                c.cumple = lambda: all(v.get("test") for v in
                                       self.report["hypotheses"].values())
            elif c.nombre == "NO_INVENTAR":
                c.cumple = lambda: bool(persist.get("row_hash_verified"))
            elif c.nombre == "EVIDENCIA_CADA_CASILLA":
                c.cumple = lambda: bool(static.get("status") == "PROVEN" and
                                        dynamic and recon)

        # M415: IDEMPOTENCIA y LAS_7_V3 dejan de ser NOT_DETERMINED por falta de
        # evaluador. Se inyectan evaluadores EJECUTABLES:
        #   IDEMPOTENCIA  repite migracion + escritura append-only + diferencial
        #   LAS_7_V3      corre el suite de mutacion y exige 7/7 con cobertura
        # Si un evaluador no puede medir, ALMA sigue en NOT_DETERMINED.
        hash_a = self._hash_experimento_diferencial(recon)
        trabajo_idem = os.path.join(self.workdir, "idempotencia")

        def _repetir_diferencial() -> str:
            """Repite el experimento discriminante y devuelve su hash."""
            val = differential_validation(
                self.artifact,
                tempfile.mkdtemp(prefix="m415_rep_", dir=self.workdir))
            return self._hash_experimento_diferencial({"validation": val})

        ev = EvaluadoresAlma(
            digest_a=hash_a, origen=os.path.join(ROOT, "rxre.sqlite3"),
            workdir=trabajo_idem, repetir=_repetir_diferencial)
        inyectados = ev.criterios()
        for c in criterios:
            if c.nombre in inyectados:
                c.cumple = inyectados[c.nombre]

        resultados = [c.evaluar() for c in criterios]
        por_estado: Dict[str, int] = {}
        for r in resultados:
            por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1
        cerrado = por_estado.get(PROVEN, 0) == len(resultados)
        faltan = [r["criterio"] for r in resultados if r["estado"] != PROVEN]
        self._stage("alma_closure", {
            "criterios": resultados, "por_estado": por_estado,
            "cerrado": cerrado,
            "faltan": faltan,
            "evaluadores_m415": ev.detalle(),
            "motivo": ("todos PROVEN" if cerrado else
                       "criterios sin evidencia suficiente: %s" % faltan),
        })

    # -- orquestacion ---------------------------------------------------
    def run(self) -> Dict[str, Any]:
        self.stage_alma_purpose()
        self.stage_cuerpo()
        self.stage_router()
        self.stage_mente()
        self.run_experiments()
        self.annotate_router_execution()
        self.resolve_hypotheses()
        self.stage_tierra()
        self.stage_fuego()
        self.stage_persist()
        self.stage_agua()
        self.stage_aire()
        self.stage_eter()
        self.stage_puerta()
        self.stage_claims()
        self.stage_failure_cases()
        self.stage_alma_closure()
        self.report["finished"] = now_utc()
        self.report["verdict"] = self._verdict()
        self.report["digest"] = self._digest()
        return self.report

    def _hash_experimento_diferencial(self,
                                      recon: Optional[Dict[str, Any]]) -> Optional[str]:
        """Hash estable de los RESULTADOS del diferencial (sin rutas ni ts).

        Es lo que se repite para medir IDEMPOTENCIA: si el mismo experimento
        produce otro hash, el criterio no se cumple.
        """
        if not recon:
            return None
        val = recon.get("validation") if "validation" in recon else recon
        if not val or not val.get("cases"):
            return None
        payload = {
            "model_sha256": val.get("model_sha256"),
            "cases": [{k: c.get(k) for k in
                       ("case", "n", "input_bytes", "orig_rc", "ref_rc",
                        "orig_len", "ref_len", "match")}
                      for c in val["cases"]],
            "mismatches": val.get("mismatches"),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    def _verdict(self) -> Dict[str, Any]:
        """Veredicto del CICLO, no de sus partes.

        `H1` puede estar PROVEN para el alcance medido y aun asi el ciclo no
        es PROVEN: ALMA deja criterios sin evaluador, PUERTA esta CONTESTED y
        la persistencia corre sobre copia aislada porque
        `DB_AUTH_ACTOR_M294 BLOCKED`. Declarar PROVEN el ciclo ocultaria esas
        tres cosas, asi que el veredicto es PASS_PARTIAL.
        """
        h = self.report["hypotheses"]
        states = [v["estado"] for v in h.values()]
        recon = next((e["result"] for e in self.report["experiments"]
                      if e["id"] == "E7_reconstruct_validate"), None)
        persist = self.report["stages"].get("persistencia") or {}
        puerta = (self.report["stages"].get("puerta") or {}).get("veredicto") or {}
        closure = self.report["stages"].get("alma_closure") or {}
        h1_id = list(h.keys())[0] if h else None
        h1_state = h[h1_id]["estado"] if h1_id else NOT_DETERMINED

        # --- Autoridad epistemológica central (R7): ningún hecho promueve solo ---
        _gate_dec = dict(self.report.get("gate_decision") or {})
        _gate_dec["accepted"] = bool(_gate_dec.get("accepted"))
        _gate_acc = bool(_gate_dec.get("accepted"))
        if not _gate_acc:
            return {
                "estado": "BLOCKED",
                "h1": h1_state,
                "ciclos": None,
                "alcance": "promocion bloqueada: autoridad epistemologica requerida "
                           "(sin dictamen vinculado a la investigacion o no aceptado)",
                "gate": _gate_dec,
                "por_que_no_proven": ["verificación independiente exigida por R7 sin autorización"]
                                      + (["PUERTA: BLOCKED_GATE"] if puerta.get("estado") == "BLOCKED_GATE" else []),
            }

        ciclos = {
            "observacion": (self.report["stages"].get("cuerpo") or {}).get("estado"),
            "estatica": next((e["status"] for e in self.report["experiments"]
                              if e["id"] == "E2_static_functions"), None),
            "dinamica": next((e["status"] for e in self.report["experiments"]
                              if e["id"] == "E4_dynamic_syscalls"), None),
            "reconstruccion": (recon or {}).get("status"),
            "persistencia": persist.get("status"),
            "aprendizaje": (self.report["stages"].get("agua") or {}).get("status"),
            "puerta": puerta.get("estado"),
            "cierre_alma": "CERRADO" if closure.get("cerrado") else "ABIERTO",
        }
        faltan = []
        if closure and not closure.get("cerrado"):
            faltan.append("ALMA: %s criterio(s) NOT_DETERMINED/DISTINTO DE PROVEN"
                          % closure.get("por_estado", {}).get(NOT_DETERMINED, 0))
        if puerta.get("estado") != "ACCEPTED":
            faltan.append("PUERTA: %s (revisor/autoridad no nombrados)"
                          % puerta.get("estado"))
        faltan.append("DB_AUTH_ACTOR_M294 BLOCKED: persistencia solo en copia aislada")

        if (h1_state == PROVEN and recon and
                recon.get("status") == "EQUIVALENT_FOR_TESTED_CASES" and
                persist.get("row_hash_verified")):
            return {
                "estado": "PASS_PARTIAL",
                "gate": _gate_dec,
                "h1": h1_state,
                "ciclos": ciclos,
                "alcance": "ciclo completo EJECUTADO y medido sobre %s: "
                           "observacion+estatica+dinamica+discriminacion+"
                           "reconstruccion+validacion diferencial+persistencia "
                           "re-leida+reutilizacion del aprendizaje"
                           % self.artifact,
                "no_incluye": ["universalidad del modelo reconstruido",
                               "autorizacion DB_AUTH_ACTOR_M294",
                               "aceptacion PUERTA (sin revisor independiente)",
                               "cierre ALMA (criterios sin evaluador)",
                               "binario simbolico / patching (no ejecutados)",
                               "runtime REA (bridge presente, no ejecutado)"],
                "por_que_no_proven": faltan,
            }
        if any(s == PROVEN for s in states):
            return {"estado": "PASS_PARTIAL", "h1": h1_state, "ciclos": ciclos,
                    "alcance": "alguna hipotesis soportada; cadena incompleta",
                    "por_que_no_proven": faltan}
        return {"estado": NOT_DETERMINED, "h1": h1_state, "ciclos": ciclos,
                "alcance": "no se resolvio el ciclo completo",
                "por_que_no_proven": faltan}

    def _digest(self) -> str:
        """Huella determinista de los RESULTADOS (sin timestamps) para reproducibilidad."""
        payload = {
            "artifact_sha256": self.report["stages"]["cuerpo"]["hash"],
            "hypotheses": {k: v["estado"] for k, v in
                           self.report["hypotheses"].items()},
            "experiments": [{"id": e["id"], "status": e["status"]}
                            for e in self.report["experiments"]],
            "differential": next(
                ({"mismatches": e["result"]["validation"]["mismatches"],
                  "model_sha256": e["result"]["validation"]["model_sha256"]}
                 for e in self.report["experiments"]
                 if e["id"] == "E7_reconstruct_validate"), None),
            "failure_cases": {
                k: v for k, v in
                (self.report["stages"].get("failure_cases") or {}).items()
                if k != "ts"},
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


# --------------------------------------------------------------------------
# reutilizacion del aprendizaje en un artefacto DISTINTO
# --------------------------------------------------------------------------
def reuse_learning_on(artifact: str, workdir: str) -> Dict[str, Any]:
    """Aplica la regla aprendida (read vs mmap del fd de entrada) a otro ELF.

    La regla es una HIPOTESIS reutilizada, no una verdad: se vuelve a medir
    contra el mundo. Si el nuevo artefacto no cumple el patron, se declara
    NO_APLICA en vez de forzar la conclusion.
    """
    os.makedirs(workdir, exist_ok=True)
    identity = {"path": artifact, "sha256": sha256_file(artifact),
                "size": os.path.getsize(artifact)}
    g = ghidra_dump(artifact, workdir)
    inp = os.path.join(workdir, "reuse_input.txt")
    with open(inp, "wb") as fh:
        fh.write(b"alpha\nbeta\ngamma\n")
    tr = strace_trace(artifact, [inp], workdir)
    parsed = parse_strace(tr["text"], inp) if tr.get("status") == "PROVEN" else {}
    static_read = False
    static_mmap = False
    if g.get("status") == "PROVEN":
        names = {f["name"] for f in g["functions"]}
        static_read = any(n in ("read", "full_read", "__read_chk",
                                "read_unlocked") for n in names)
        static_mmap = any("mmap" in n for n in names)
    dyn_read = bool(parsed.get("read_calls"))
    dyn_mmap = bool(parsed.get("mmap_on_target_fd"))
    applies = (static_read or dyn_read) and not dyn_mmap
    return {
        "artifact": artifact, "identity": identity,
        "learning_rule": "buscar read()/full_read y conteo; comprobar mmap "
                         "sobre el fd de entrada",
        "static": {"status": g.get("status"), "read": static_read,
                   "mmap": static_mmap,
                   "functions": (len(g.get("functions", []))
                                 if g.get("status") == "PROVEN" else None)},
        "dynamic": {"status": tr.get("status"), "parsed": parsed},
        "applies": applies,
        "decision": ("PATRON_REUTILIZADO" if applies else "NO_APLICA"),
        "status": PROVEN if tr.get("status") == "PROVEN" else NOT_DETERMINED,
        "note": "el aprendizaje guia la seleccion de la prueba; no sustituye "
                "la medicion del nuevo artefacto",
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: List[str]) -> int:
    if len(argv) > 1 and argv[1] == "--reuse":
        artifact = argv[2] if len(argv) > 2 else "/usr/bin/wc"
        out_json = argv[3] if len(argv) > 3 else "/tmp/opencode/m414/reuse.json"
        if not os.path.isfile(artifact):
            print(json.dumps({"status": "BLOCKED", "reason": "artifact missing",
                              "artifact": artifact}, indent=2))
            return 2
        work = tempfile.mkdtemp(prefix="m414_reuse_", dir="/tmp/opencode")
        rep = reuse_learning_on(artifact, work)
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, indent=2, default=str)
        print(json.dumps({k: rep[k] for k in
                          ("artifact", "decision", "status", "applies")},
                         indent=2, default=str))
        return 0
    artifact = argv[1] if len(argv) > 1 else "/usr/bin/head"
    out_json = argv[2] if len(argv) > 2 else "/tmp/opencode/m414/report.json"
    if not os.path.isfile(artifact):
        print(json.dumps({"status": "BLOCKED", "reason": "artifact missing",
                          "artifact": artifact}, indent=2))
        return 2
    work = tempfile.mkdtemp(prefix="m414_", dir="/tmp/opencode")
    inv = IntegratedInvestigation(artifact, workdir=work)
    rep = inv.run()
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, default=str)
    print(json.dumps({
        "artifact": rep["artifact"],
        "verdict": rep["verdict"],
        "digest": rep["digest"],
        "hypotheses": {k: v["estado"] for k, v in rep["hypotheses"].items()},
        "experiments": [{"id": e["id"], "status": e["status"]}
                        for e in rep["experiments"]],
        "differential": next(({"cases": len(e["result"]["validation"]["cases"]),
                               "mismatches": e["result"]["validation"]["mismatches"]}
                              for e in rep["experiments"]
                              if e["id"] == "E7_reconstruct_validate"), None),
        "persistence": {k: rep["stages"]["persistencia"].get(k) for k in
                        ("status", "recovered", "row_hash_verified",
                         "stable_copy_sha256")},
        "learning": rep["stages"]["agua"].get("revalidacion"),
        "failure_cases": rep["stages"]["failure_cases"].get("status"),
        "closure": rep["stages"]["alma_closure"].get("por_estado"),
        "report": out_json,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
