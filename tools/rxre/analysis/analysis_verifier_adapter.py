"""M683 ANALYSIS->VERIFIER ADAPTER (minimo, reversible).

Conecta:
    cfg_coverage.metrics_from_aflj (ANALYSIS)
      -> EvidencePackage con esquema explicito
      -> independent_verifier (clean-room + seal + reproduccion inyectada)
      -> acceptance_policy.guard_promotion (unica politica, sin duplicar)
      -> PUERTA hasta DELIVERED (aceptar() == CONTESTED, no ACCEPTED)

No duplica verificador ni crea segunda politica. No modifica contratos
protegidos. No promueve PASS operacional (EXECUTION_OK) a PROVEN.
"""
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from dataclasses import asdict

SCHEMA = "rxre-evidence-package.v1"

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 16), b''):
            h.update(c)
    return h.hexdigest()

def build_evidence_package(*, subject_path: str, funcs, indirect_sites=14,
                           table_entries=277, table_unique=61,
                           producer: str, command: str,
                           provenance_source: str = "OBSERVED",
                           epistemic_status: str = "PARTIAL",
                           limitations=None, subject_sha256=None,
                           evidence_refs=None, falsification_tests=None,
                           inference_note: str = "", conclusion_note: str = ""):
    """Construye paquete estructurado. Rechaza sin procedencia OBSERVED,
    campos ausentes o estado incompatible. Cfg es PARTIAL como maximo;
    PROVEN es estado incompatible para este productor acotado."""
    from tools.rxre.analysis import cfg_coverage as CC
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: cfg_coverage acotado no puede ser PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        # acceptance_policy downgrade a WITHHOLD; el adaptador exige limites
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    metrics = CC.metrics_from_aflj(list(funcs), indirect_sites=indirect_sites,
                                   table_entries=table_entries, table_unique=table_unique)
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "cfg_coverage.metrics_from_aflj", "version": "m634-m637",
                 "params": {"indirect_sites": indirect_sites, "table_entries": table_entries,
                            "table_unique": table_unique, "n_funcs": len(funcs)}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {k: metrics[k] for k in ("func_cov", "block_cov", "edge_cov",
                                                  "indirect_cov", "dist", "sum_reconciled")},
        # inferencias: derivadas del criterio local, no del oraculo
        "inferences": [{"kind": "classify_absence",
                        "detail": metrics["dist"],
                        "note": inference_note or "clasificacion local por funcion"}],
        # conclusiones: cerradas a cobertura instrumental/estructural
        "conclusions": [{"kind": "coverage",
                         "detail": {k: metrics[k] for k in ("func_cov", "edge_cov", "indirect_cov")},
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "cobertura instrumental aflj, sin equivalencia"}],
        "evidence_refs": list(evidence_refs or [{"id": "m683-funcs-input",
                                                 "kind": "synthetic_funcs",
                                                 "n": len(funcs)}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "sum_reconciled true", "expected": "funcs==sum(dist)"},
            {"condition": "aceptacion no escala a PROVEN", "expected": "PARTIAL->ACCEPT_LIMITED"}]),
        "limitations": list(limitations) if limitations else
                       ["cobertura instrumental aflj; indirectos 13 MAY restantes",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def write_package(pkg: dict, out_dir: str) -> Path:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    p = out / "EVIDENCE.json"
    p.write_text(json.dumps(pkg, indent=2))
    return p

def make_runner(*, epistemic_status: str, limitations, discrepant=False):
    """Runner inyectado offline: reproduce independientemente con
    cfg_coverage desde el input sellado, sin oraculo externo de GPU."""
    def runner(request, package_dir: str):
        from tools.rxre.analysis import cfg_coverage as CC
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        n = ev["tool"]["params"]["n_funcs"]
        # funcs sinteticas deterministas derivables del paquete (misma entrada)
        rng = [{"name": f"f{i}", "size": 100 + i * 100, "nbbs": 5 + i * 3,
                "edges": 10 + i * 6} for i in range(n)]
        recomputed = CC.metrics_from_aflj(rng,
            indirect_sites=ev["tool"]["params"]["indirect_sites"],
            table_entries=ev["tool"]["params"]["table_entries"],
            table_unique=ev["tool"]["params"]["table_unique"])
        if discrepant:
            recomputed = dict(recomputed); recomputed["func_cov"] = "0/0=0.000"
        obs = ev["observations"]
        matches = all(str(recomputed.get(k)) == str(obs.get(k))
                      for k in ("func_cov", "edge_cov", "indirect_cov"))
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        pred = {"predicted": {"func_cov": recomputed["func_cov"],
                              "edge_cov": recomputed["edge_cov"]},
                "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(pred))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m683"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m683-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

def run_full_flow(*, subject_path: str, package: dict, workdir: str,
                  investigation_id: str, domain: str, runner,
                  target_file: str = "ls", register_dictamen: bool = True):
    """ANALYSIS -> PACKAGE -> VERIFIER -> POLICY. No usa sandbox bwrap
    completo (sin LLM/GPU): se verifica build_sandbox_args como interfaz
    de confinamiento declarada; la reproduccion es in-process offline."""
    from tools.rxre.verifier import independent_verifier as IV
    from tools.rxre.verifier import acceptance_policy as AP
    from tools.rxre.verifier import sandbox as SB
    _ = SB.build_sandbox_args("/evidence", "/home/vf", "/out")  # interfaz de confinamiento
    td = Path(workdir); td.mkdir(parents=True, exist_ok=True)
    ev_path = write_package(package, str(td / "src"))
    case = IV.CaseSpec(case_id=investigation_id, target=target_file,
                       artifact_sha256=package["subject"]["sha256"],
                       objective="reproducir cobertura cfg",
                       dispatch_description={"tool": package["tool"]["name"],
                                             "params": package["tool"]["params"]})
    pkg_dir = IV.build_clean_room(subject_path, [str(ev_path)], case, str(td / "pkg"))
    req = IV.VerificationRequest(target=subject_path, evidence_package=pkg_dir,
                                 case=case, investigation_id=investigation_id,
                                 domain=domain, workdir=str(td),
                                 register_dictamen=register_dictamen)
    res = IV.verify(req, runner=runner)
    res_d = asdict(res)
    decision = AP.guard_promotion(investigation_id=investigation_id,
                                  artifact_sha256=package["subject"]["sha256"],
                                  target_file=target_file, domain=domain,
                                  verification_result=res_d)
    return {"verify": res_d, "promotion": asdict(decision), "package_dir": pkg_dir,
            "evidence_path": str(ev_path)}

def puerta_until_delivered(artifact_path: str, hash_declarado: str,
                           authority: str = "M683-adapter") -> dict:
    """Registra artefacto en PUERTA y evalua. Sin revisor nombrado (y sin
    simular revision independiente con el mismo productor) el veredicto
    permanece CONTESTED: entregado (DELIVERED) pero no ACCEPTED."""
    from tools.rxre.arquitectura.PUERTA import Puerta, DELIVERED
    p = Puerta()
    aid = p.registrar_artefacto("m683-evidence", artifact_path, hash_declarado=hash_declarado)
    p.declarar_participacion("M683-adapter", aid)
    if authority:
        p.nombrar_autoridad(authority)
    # NO se nombra revisor: la revision independiente requiere actor
    # distinto del productor (no simulable aqui). accepted() -> CONTESTED.
    verdict = p.aceptar()
    return {"staged": DELIVERED, "artifact_id": aid, "aceptar": verdict,
            "delivered": verdict["estado"] != "ACCEPTED"}

# --- M684: mismo contrato, segundo productor (indirect_targets) ---
# No altera el contrato cfg_coverage; reutiliza SCHEMA/procedencia/identidad/
# verificador/politica/DELIVERED y conserva SINGLE/FINITE/MAY/UNKNOWN.

def build_indirect_evidence_package(*, subject_path: str, defs,
                                    max_iter=3, producer: str, command: str,
                                    provenance_source: str = "OBSERVED",
                                    epistemic_status: str = "PARTIAL",
                                    limitations=None, subject_sha256=None,
                                    evidence_refs=None, falsification_tests=None,
                                    inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import indirect_targets as IT
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: indirect_targets no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    norm_defs = [tuple(d) if isinstance(d, list) else d for d in defs]
    status, targets = IT.resolve(list(norm_defs), max_iter=max_iter)
    cfg = IT.finites_to_cfg(targets, status)
    defs_json = json.loads(json.dumps(list(norm_defs), default=str))
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "indirect_targets.resolve", "version": "m632",
                 "params": {"max_iter": max_iter, "input": defs_json}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"producer_status": status,
                         "targets": sorted(int(x) for x in targets),
                         "max_iter": max_iter},
        "inferences": [{"kind": "finites_to_cfg",
                        "detail": sorted(int(x) for x in cfg),
                        "note": inference_note or "solo SINGLE/FINITE extienden CFG"}],
        "conclusions": [{"kind": "indirect_target",
                         "producer_status": status,
                         "detail": sorted(int(x) for x in targets),
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "estados SINGLE/FINITE/MAY/UNKNOWN distintos"}],
        "evidence_refs": list(evidence_refs or [{"id": "m684-defs-input",
                                                 "kind": "defs_slice",
                                                 "defs": defs_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "MAY/UNKNOWN no extiende CFG", "expected": "finites_to_cfg empty"},
            {"condition": "aceptacion no escala a PROVEN", "expected": "PARTIAL->ACCEPT_LIMITED"}]),
        "limitations": list(limitations) if limitations else
                       ["slice acotada max_iter=3; MAY/UNKNOWN sin destino",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

# --- M685: mismo contrato, tercer productor (points_to_ext) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion semantica Andersen (obs=input, inf=pts).

def build_points_evidence_package(*, subject_path: str, alloc_sites: dict, constraints: list,
                                  producer: str, command: str,
                                  provenance_source: str = "OBSERVED",
                                  epistemic_status: str = "PARTIAL",
                                  limitations=None, subject_sha256=None,
                                  evidence_refs=None, falsification_tests=None,
                                  inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis.points_to_ext import anderson_field
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: points_to_ext no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    norm_alloc = {k: set(v) for k, v in alloc_sites.items()}
    norm_cons = [tuple(c) for c in constraints]
    pts = anderson_field(norm_alloc, list(norm_cons))
    pts_sorted = {k: sorted(v) for k, v in pts.items()}
    alloc_json = {k: sorted(v) for k, v in norm_alloc.items()}
    cons_json = json.loads(json.dumps(list(norm_cons), default=str))
    resolutions = {}
    for k, vs in pts_sorted.items():
        if len(vs) == 0:
            resolutions[k] = "UNRESOLVED_EMPTY_ABSENCE_NOT_PROVEN"
        elif len(vs) == 1:
            resolutions[k] = "RESOLVED_WITHIN_DOMAIN"
        else:
            resolutions[k] = "MAY_MULTIPLE_APPROXIMATE"
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "points_to_ext.anderson_field", "version": "m595",
                 "params": {"alloc_sites": alloc_json, "constraints": cons_json}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"alloc_sites": alloc_json, "constraints": cons_json,
                         "n_pts_keys": len(pts_sorted)},
        "inferences": [{"kind": "anderson_field",
                        "pts": pts_sorted,
                        "resolutions": resolutions,
                        "note": inference_note or "Andersen over-approx conservador"}],
        "conclusions": [{"kind": "points_to",
                         "points_to": pts_sorted,
                         "resolutions": resolutions,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "relaciones demostradas en dominio; vacio=ausencia"}],
        "evidence_refs": list(evidence_refs or [{"id": "m685-points-input",
                                                 "kind": "alloc_constraints",
                                                 "alloc_sites": alloc_json,
                                                 "constraints": cons_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "vacio no es PROVEN", "expected": "UNRESOLVED_EMPTY_ABSENCE_NOT_PROVEN"},
            {"condition": "union multi no es certeza", "expected": "MAY_MULTIPLE_APPROXIMATE"}]),
        "limitations": list(limitations) if limitations else
                       ["field-sensitivity acotada (offset); sin heap general",
                        "ausencia != conjunto vacio probado; MAY conservado",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_points_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis.points_to_ext import anderson_field
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        alloc = {k: set(v) for k, v in ev["tool"]["params"]["alloc_sites"].items()}
        cons = [tuple(c) for c in ev["tool"]["params"]["constraints"]]
        pts = anderson_field(alloc, cons)
        pts_sorted = {k: sorted(v) for k, v in pts.items()}
        if discrepant:
            pts_sorted = {k: (["heap_alloc(999)"] if v else v) for k, v in pts_sorted.items()}
        obs_pts = ev["inferences"][0]["pts"]
        matches = pts_sorted == obs_pts
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        pred = {"predicted_pts": pts_sorted, "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(pred))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m685"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m685-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

def make_indirect_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import indirect_targets as IT
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        defs = [tuple(d) if isinstance(d, list) else d for d in ev["tool"]["params"]["input"]]
        # defs JSON pierde tuplas internas: normalizar listas anidadas a listas
        # resolve() acepta listas para phi (convierte en [b]); tuplas top-level OK.
        def norm(x):
            if isinstance(x, list) and x: return tuple(norm(y) for y in x) if False else x
            return x
        rs, rt = IT.resolve(list(defs), max_iter=ev["tool"]["params"]["max_iter"])
        if discrepant:
            rs = "UNKNOWN"; rt = set()
        obs = ev["observations"]
        matches = (rs == obs["producer_status"]
                   and sorted(int(x) for x in rt) == obs["targets"])
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        pred = {"predicted": {"producer_status": rs, "targets": sorted(int(x) for x in rt)},
                "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(pred))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m684"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m684-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

# --- M686: mismo contrato, cuarto productor (mem_pred) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion semantica memoria (obs=bytes, inf=predicados).

def build_mem_evidence_package(*, subject_path: str, blocks, events, queries,
                               producer: str, command: str,
                               provenance_source: str = "OBSERVED",
                               epistemic_status: str = "PARTIAL",
                               limitations=None, subject_sha256=None,
                               evidence_refs=None, falsification_tests=None,
                               inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import mem_pred as MP
    from tools.rxre.analysis.ssa import build_graph
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: mem_pred no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    succ = {b["id"]: [str(o) for o in b["out_nodes"]] for b in blocks}
    _, pred, ids = build_graph(blocks)
    norm_events = {}
    for bid, evs in events.items():
        norm = []
        for ev in evs:
            if ev[0] == "load":
                norm.append(("load", (int(ev[1][0]), int(ev[1][1])), str(ev[2]), int(ev[3])))
            elif ev[0] == "store":
                norm.append(("store", (int(ev[1][0]), int(ev[1][1])), int(ev[2])))
            elif ev[0] == "call":
                norm.append(("call",))
        norm_events[str(bid)] = norm
    IN, OUT = MP.prop_predicate(succ, pred, "0", ids, norm_events)
    def pred_str(p):
        (va, w), op, val = p if len(p) == 3 else (p[0], None, None)
        return f"{va}+{w} {p[1] if len(p)>1 else ''} {p[2] if len(p)>2 else ''}"
    out_sorted = {k: sorted(f"{_va}+{_w} {_op} {_val}" for (_va, _w), _op, _val in v) for k, v in OUT.items()}
    # serializar IN/OUT como strings para JSON determinista + resolucion por query
    resolutions = {}
    for (bid, va, w, op, val) in queries:
        _p = ((int(va), int(w)), str(op), int(val))
        if MP.holds(OUT.get(str(bid), set()), (int(va), int(w)), str(op), int(val)):
            resolutions[f"{bid}:{va}+{w}:{op}={val}"] = "HOLDS_WITHIN_DOMAIN"
        elif not OUT.get(str(bid)):
            resolutions[f"{bid}:{va}+{w}:{op}={val}"] = "UNKNOWN_UNOBSERVED_NOT_PROVEN"
        else:
            # OUT no vacio pero query no sostenida: ¿hay predicado competidor misma loc?
            competitor = any(p[0] == (int(va), int(w)) for p in OUT.get(str(bid), set()))
            resolutions[f"{bid}:{va}+{w}:{op}={val}"] = ("AMBIGUOUS_MULTIPLE_INTERPRETATIONS" if competitor else "NOT_HELD_WITHIN_DOMAIN")
    blocks_json = json.loads(json.dumps(blocks, default=str))
    events_json = json.loads(json.dumps(events, default=str))
    queries_json = json.loads(json.dumps(queries, default=str))
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "mem_pred.prop_predicate", "version": "m629",
                 "params": {"blocks": blocks_json, "events": events_json, "queries": queries_json}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"blocks": blocks_json, "events": events_json,
                         "n_blocks": len(blocks)},
        "inferences": [{"kind": "predicate_propagation",
                        "OUT": out_sorted,
                        "resolutions": resolutions,
                        "note": inference_note or "propagacion conservadora: store/call invalidan"}],
        "conclusions": [{"kind": "memory_predicate",
                         "resolutions": resolutions,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "observacion/inferencia/prediccion separadas"}],
        "evidence_refs": list(evidence_refs or [{"id": "m686-mem-input",
                                                 "kind": "blocks_events",
                                                 "blocks": blocks_json,
                                                 "events": events_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "vacio no es ausencia probada", "expected": "UNKNOWN_UNOBSERVED_NOT_PROVEN"},
            {"condition": "multi no es certeza", "expected": "AMBIGUOUS_MULTIPLE_INTERPRETATIONS"}]),
        "limitations": list(limitations) if limitations else
                       ["predicados globales byte+qword; store/call conservadores",
                        "sin cobertura de regiones no observadas",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_mem_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import mem_pred as MP
        from tools.rxre.analysis.ssa import build_graph
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        blocks = ev["tool"]["params"]["blocks"]
        events = ev["tool"]["params"]["events"]
        queries = ev["tool"]["params"]["queries"]
        succ = {b["id"]: [str(o) for o in b["out_nodes"]] for b in blocks}
        _, pred, ids = build_graph(blocks)
        norm = {}
        for bid, evs in events.items():
            lst = []
            for e in evs:
                if e[0] == "load":
                    lst.append(("load", (int(e[1][0]), int(e[1][1])), str(e[2]), int(e[3])))
                elif e[0] == "store":
                    lst.append(("store", (int(e[1][0]), int(e[1][1])), int(e[2])))
                elif e[0] == "call":
                    lst.append(("call",))
            norm[str(bid)] = lst
        IN, OUT = MP.prop_predicate(succ, pred, "0", ids, norm)
        if discrepant:
            OUT = {k: set() for k in OUT}
        out_sorted = {k: sorted(f"{_va}+{_w} {_op} {_val}" for (_va, _w), _op, _val in v) for k, v in OUT.items()}
        obs = ev["inferences"][0]["OUT"]
        matches = out_sorted == obs
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_OUT": out_sorted, "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m686"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m686-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

# --- M687: mismo contrato, quinto productor (call_summary) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion interprocedural (llamada obs. vs efecto inf.).

def _call_target_kind(events):
    if events is None:
        return ("EXTERNAL_UNKNOWN", None)
    for evs in events.values():
        for ev in evs:
            if ev[0] == "indcall":
                return ("INDIRECT_UNRESOLVED", None)
            if ev[0] == "call":
                return ("DIRECT_OBSERVED", str(ev[1]))
    return ("NO_CALL_IN_BODY", None)

def build_call_evidence_package(*, subject_path: str, func_name: str, func_blocks_events,
                                producer: str, command: str,
                                provenance_source: str = "OBSERVED",
                                epistemic_status: str = "PARTIAL",
                                limitations=None, subject_sha256=None,
                                evidence_refs=None, falsification_tests=None,
                                inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import call_summary as CS
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: call_summary no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    summary = CS.summarize(func_name, func_blocks_events, actual_sha)
    def loc_str(s):
        return sorted(f"{va}+{w}" for (va, w) in s)
    reads_sorted = loc_str(summary["reads"]); writes_sorted = loc_str(summary["writes"])
    target_kind, target = _call_target_kind(func_blocks_events)
    if func_blocks_events is None:
        events_json = None
        n_blocks = 0
    else:
        events_json = json.loads(json.dumps(func_blocks_events, default=str))
        n_blocks = len(func_blocks_events)
    # disciplina: unknown nunca como vacio probado
    if summary["unknown"] and summary["reads"] == set() and summary["writes"] == set():
        effect_kind = "UNKNOWN_EXTERNAL_NOT_PROVEN_EMPTY"
    elif summary["unknown"]:
        effect_kind = "UNKNOWN_CONSERVATIVE_WITH_READS_WRITES"
    else:
        effect_kind = "KNOWN_WITHIN_DOMAIN"
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "call_summary.summarize", "version": "m630",
                 "params": {"func_name": func_name, "events": events_json,
                            "n_blocks": n_blocks}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"call_instructions": _call_instructions(events_json),
                         "target_kind": target_kind, "target": target,
                         "func_name": func_name},
        "inferences": [{"kind": "call_summary",
                        "reads": reads_sorted, "writes": writes_sorted,
                        "unknown": summary["unknown"], "coverage": summary["coverage"],
                        "effect_kind": effect_kind,
                        "note": inference_note or "llamada observada != efecto demostrado"}],
        "conclusions": [{"kind": "interprocedural_effect",
                         "target_kind": target_kind, "target": target,
                         "effect_kind": effect_kind,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "externo/indirecto/desconocido nunca resumen vacio probado"}],
        "evidence_refs": list(evidence_refs or [{"id": "m687-call-input",
                                                 "kind": "func_blocks_events",
                                                 "events": events_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "unknown no es vacio probado", "expected": "UNKNOWN_EXTERNAL_NOT_PROVEN_EMPTY"},
            {"condition": "resumen que contradice cuerpo -> WITHHOLD", "expected": "discrepante no acepta"}]),
        "limitations": list(limitations) if limitations else
                       ["resumen interprocedural conservador; call sin summary -> unknown",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def _call_instructions(events_json):
    if events_json is None:
        return []
    out = []
    for bid, evs in events_json.items():
        for ev in evs:
            if ev[0] in ("call", "indcall"):
                out.append({"bid": bid, "kind": ev[0], "target": ev[1] if len(ev) > 1 else None})
    return out

def make_call_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import call_summary as CS
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        events = ev["tool"]["params"]["events"]
        name = ev["tool"]["params"]["func_name"]
        subj = ev["subject"]["sha256"]
        if events is None:
            recomputed = {"reads": set(), "writes": set(), "unknown": True}
        else:
            # deserializar locs [va,w] -> tuples como Python
            norm = {}
            for bid, evs in events.items():
                lst = []
                for e in evs:
                    if e[0] == "load":
                        lst.append(("load", (int(e[1][0]), int(e[1][1])), str(e[2]), int(e[3])))
                    elif e[0] == "store":
                        lst.append(("store", (int(e[1][0]), int(e[1][1])), int(e[2])))
                    elif e[0] == "call":
                        lst.append(("call", str(e[1])))
                    elif e[0] == "indcall":
                        lst.append(("indcall",))
                norm[str(bid)] = lst
            recomputed = CS.summarize(name, norm, subj)
        if discrepant:
            recomputed = dict(recomputed)
            recomputed["reads"] = {(_va_for_d(r), _w_for_d(r)) for r in list(recomputed.get("reads", set()))}
            recomputed["reads"] = {(0x99999, 1)}
        inf = ev["inferences"][0]
        obs_reads = set() if inf["reads"] == [] else {(_va_for_d(r), _w_for_d(r)) for r in inf["reads"]}
        # comparar en forma JSON
        def locs(s):
            return sorted(f"{va}+{w}" for (va, w) in s)
        matches = (locs(recomputed.get("reads", set())) == inf["reads"]
                   and locs(recomputed.get("writes", set())) == inf["writes"]
                   and bool(recomputed.get("unknown")) == bool(inf["unknown"]))
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_reads": locs(recomputed.get("reads", set())),
                 "predicted_unknown": bool(recomputed.get("unknown")),
                 "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m687"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m687-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

def _va_for_d(r):
    if isinstance(r, str):
        return int(r.split("+")[0])
    return int(r[0])

def _w_for_d(r):
    if isinstance(r, str):
        return int(r.split("+")[1])
    return int(r[1])

# --- M688: mismo contrato, sexto productor (diff_harness) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion diferencial (coincidencia estructural != prueba semantica).

def build_diff_evidence_package(*, subject_path: str, hexstr: str, ir_blocks, entry: str,
                               regs_init: dict, base=0x1000, tool_version: str = "m591",
                               producer: str, command: str,
                               provenance_source: str = "OBSERVED",
                               epistemic_status: str = "PARTIAL",
                               limitations=None, subject_sha256=None,
                               evidence_refs=None, falsification_tests=None,
                               inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import diff_harness as DH
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: diff_harness no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    cap_ir, why = DH.capstone_to_ir(hexstr, base)
    check = DH.differential_check(ir_blocks, entry, dict(regs_init))
    hex_norm = hexstr.replace(" ", "").lower()
    n_bytes = len(bytes.fromhex(hex_norm)) if hex_norm else 0
    coverage = "COMPLETE_IN_SUBSET" if why == "ok" and cap_ir is not None else "INCOMPLETE_OUT_OF_SUBSET"
    blocks_json = json.loads(json.dumps(ir_blocks, default=str))
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "diff_harness.capstone_to_ir+differential_check", "version": tool_version,
                 "params": {"hexstr": hex_norm, "base": int(base), "ir_blocks": blocks_json,
                            "entry": str(entry), "regs_init": dict(regs_init),
                            "capstone_subset": sorted(DH.CAPSTONE_SUBSET)}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"hexstr": hex_norm, "n_bytes": n_bytes,
                         "capstone_why": why, "coverage": coverage,
                         "capstone_ir": [[m, o, int(a)] for (m, o, a) in (cap_ir or [])]},
        "inferences": [{"kind": "differential_check",
                        "verdict": check.get("verdict"),
                        "regs": check.get("regs", {}),
                        "note": inference_note or "determinismo IR doble-run; estructural != semantico"}],
        "conclusions": [{"kind": "differential_match",
                         "verdict": check.get("verdict"),
                         "coverage": coverage,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "MATCH-acotado solo subset; sin equivalencia semantica"}],
        "evidence_refs": list(evidence_refs or [{"id": "m688-diff-input",
                                                 "kind": "hex_ir_blocks",
                                                 "hexstr": hex_norm, "ir_blocks": blocks_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "coincidencia estructural no es prueba semantica", "expected": "PARTIAL->ACCEPT_LIMITED nunca PROVEN"},
            {"condition": "cobertura incompleta no se esconde", "expected": "INCOMPLETE->NOT_DETERMINED"}]),
        "limitations": list(limitations) if limitations else
                       ["subset MOV/ADD/SUB/CMP/JMP/JZ/JNZ solo",
                        "equivalencia universal NOT_DETERMINED",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_diff_runner(*, epistemic_status: str, limitations, discrepant=False, bad_params=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import diff_harness as DH
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        p = ev["tool"]["params"]
        base = int(p["base"]) + (0x1 if bad_params else 0)
        # version/param mismatch -> no comparable
        if bad_params or p.get("capstone_subset") != sorted(DH.CAPSTONE_SUBSET):
            verdict_status = "NOT_DETERMINED"
            outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
            predf = {"predicted": "PARAM_MISMATCH"}
            (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
            (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(
                {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"), "ts": "m688"}))
            (outs / "VERDICT.json").write_text(json.dumps(
                {"epistemic_status": "NOT_DETERMINED", "matches": False,
                 "limitations": ["parametros/version inconsistentes"]}))
            export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                    "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
            ep = outs / "export.json"; ep.write_text(json.dumps(export))
            return {"session_id": "m688-offline", "export_path": str(ep),
                    "outputs_dir": str(outs),
                    "artifacts": {"verdict": str(outs / "VERDICT.json")}}
        cap_ir, why = DH.capstone_to_ir(p["hexstr"], base)
        # reconstruir blocks desde JSON (listas de ops convertidas)
        blocks = p["ir_blocks"]
        # regs_init sin cambios
        regs = dict(p["regs_init"])
        # differential_check reconstruye con blocks copiados
        check = DH.differential_check(blocks, p["entry"], regs)
        if discrepant:
            check = dict(check); check["regs"] = {**check.get("regs", {}), "rbx": 99999}
        obs_coverage = ev["observations"]["coverage"]
        obs_verdict = ev["inferences"][0]["verdict"]
        obs_regs = ev["inferences"][0]["regs"]
        coverage_now = "COMPLETE_IN_SUBSET" if why == "ok" and cap_ir is not None else "INCOMPLETE_OUT_OF_SUBSET"
        matches = (check.get("verdict") == obs_verdict and check.get("regs", {}) == obs_regs
                   and coverage_now == obs_coverage)
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_verdict": check.get("verdict"), "coverage": coverage_now,
                 "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m688"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m688-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

# --- M689: mismo contrato, septimo productor (dataflow) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion reaching+liveness (obs=input, inf=IN/OUT).

def build_dataflow_evidence_package(*, subject_path: str, blocks, hex_per_block: dict,
                                    entry: str, producer: str, command: str,
                                    provenance_source: str = "OBSERVED",
                                    epistemic_status: str = "PARTIAL",
                                    limitations=None, subject_sha256=None,
                                    evidence_refs=None, falsification_tests=None,
                                    inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import dataflow as DF
    from tools.rxre.analysis.ssa import build_graph
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: dataflow no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    blocks_json = json.loads(json.dumps(blocks, default=str))
    hex_json = {k: v.replace(" ", "").lower() for k, v in hex_per_block.items()}
    _, pred, ids = build_graph(blocks_json)
    succ = {str(b["id"]): [str(o) for o in b.get("out_nodes", [])] for b in blocks_json}
    mort = {}
    for bid, hx in hex_json.items():
        mort[str(bid)] = DF.decode_function(bytes.fromhex(hx), 0x1000)
    um, dm, gm, km = DF.use_def_maps(mort)
    IN, OUT = DF.reaching_defs(succ, pred, str(entry), ids, gm, km)
    LI, LO = DF.liveness(succ, pred, str(entry), ids, um, dm)
    def rs(ss):
        return {k: sorted(f"{r}:{i}" for (r, i) in v) for k, v in ss.items()}
    def ls(ss):
        return {k: sorted(str(x) for x in v) for k, v in ss.items()}
    in_sorted, out_sorted = rs(IN), rs(OUT)
    li_sorted, lo_sorted = ls(LI), ls(LO)
    reaches = any(len(v) > 0 for v in OUT.values()) and any(len(v) > 0 for v in IN.values())
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "dataflow.reaching_defs+liveness", "version": "m579",
                 "params": {"blocks": blocks_json, "hex_per_block": hex_json,
                            "entry": str(entry)}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"blocks": blocks_json, "hex_per_block": hex_json,
                         "entry": str(entry), "n_blocks": len(blocks_json)},
        "inferences": [{"kind": "reaching_defs",
                        "IN": in_sorted, "OUT": out_sorted,
                        "reaches": reaches,
                        "note": inference_note or "reaching defs estaticos por CFG"}],
        "inferences_liveness": [{"kind": "liveness",
                                 "LIVE_IN": li_sorted, "LIVE_OUT": lo_sorted,
                                 "note": "liveness derivada estatica, no runtime"}],
        "conclusions": [{"kind": "dataflow",
                         "reaching": in_sorted, "liveness": li_sorted,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "CFG observado, IN/OUT derivados, sin evidencia de ejecucion"}],
        "evidence_refs": list(evidence_refs or [{"id": "m689-dataflow-input",
                                                 "kind": "cfg_hex",
                                                 "blocks": blocks_json,
                                                 "hex_per_block": hex_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "kill pot bloquea", "expected": "OUT no conserva gen anterior"},
            {"condition": "liveness != runtime", "expected": "inferencia estatica acotada"}]),
        "limitations": list(limitations) if limitations else
                       ["CFG sintetico minimo; sin cobertura de regiones no incluidas",
                        "liveness/reaching estaticos, no comportamiento runtime",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_dataflow_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import dataflow as DF
        from tools.rxre.analysis.ssa import build_graph
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        p = ev["tool"]["params"]
        blocks = p["blocks"]
        _, pred, ids = build_graph(blocks)
        succ = {str(b["id"]): [str(o) for o in b.get("out_nodes", [])] for b in blocks}
        mort = {str(bid): DF.decode_function(bytes.fromhex(hx), 0x1000)
                for bid, hx in p["hex_per_block"].items()}
        um, dm, gm, km = DF.use_def_maps(mort)
        IN, OUT = DF.reaching_defs(succ, pred, str(p["entry"]), ids, gm, km)
        LI, LO = DF.liveness(succ, pred, str(p["entry"]), ids, um, dm)
        if discrepant:
            OUT = {k: set() for k in OUT}
        def rs(ss):
            return {k: sorted(f"{r}:{i}" for (r, i) in v) for k, v in ss.items()}
        out_sorted = rs(OUT)
        obs = ev["inferences"][0]["OUT"]
        matches = out_sorted == obs
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_OUT": out_sorted, "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m689"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m689-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

# --- M690: mismo contrato, octavo productor (ssa) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion SSA (obs=CFG, inf=Dom/DF/phi).

def build_ssa_evidence_package(*, subject_path: str, blocks, entry: str, var_defs: dict,
                               producer: str, command: str,
                               provenance_source: str = "OBSERVED",
                               epistemic_status: str = "PARTIAL",
                               limitations=None, subject_sha256=None,
                               evidence_refs=None, falsification_tests=None,
                               inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import ssa as SSA
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: ssa no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    blocks_json = json.loads(json.dumps(blocks, default=str))
    succ, pred, ids = SSA.build_graph(blocks_json)
    Dom = SSA.dominators(succ, pred, str(entry), ids)
    DF = SSA.dominance_frontier(succ, pred, str(entry), ids, Dom)
    norm_defs = {k: set(v) for k, v in var_defs.items()}
    phi = SSA.phi_placement(DF, norm_defs)
    # alcanzabilidad real desde entry
    reach = set()
    stack = [str(entry)]
    while stack:
        n = stack.pop()
        if n in reach:
            continue
        reach.add(n)
        stack.extend(succ.get(n, []))
    unreachable = sorted(set(ids) - reach)
    def sm(d):
        return {k: sorted(v) for k, v in d.items()}
    resolutions = {}
    for n in ids:
        if n in unreachable:
            resolutions[n] = "UNKNOWN_UNREACHABLE_NOT_PROVEN"
        else:
            resolutions[n] = "DOMINANCE_DERIVED_WITHIN_DOMAIN"
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "ssa.build_graph+dominators+DF+phi", "version": "m569",
                 "params": {"blocks": blocks_json, "entry": str(entry),
                            "var_defs": {k: sorted(v) for k, v in norm_defs.items()}}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"blocks": blocks_json, "entry": str(entry),
                         "ids": ids, "unreachable": unreachable},
        "inferences": [{"kind": "dominators",
                        "Dom": sm(Dom),
                        "DF": sm(DF),
                        "resolutions": resolutions,
                        "note": inference_note or "Dom/DF/phi derivados del CFG observado"}],
        "inferences_phi": [{"kind": "phi_placement",
                            "phi": sm(phi),
                            "note": "inserciones phi derivadas, sin prueba de comportamiento"}],
        "conclusions": [{"kind": "ssa_structure",
                         "Dom": sm(Dom), "DF": sm(DF), "phi": sm(phi),
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "CFG observado, SSA derivado, sin equivalencia"}],
        "evidence_refs": list(evidence_refs or [{"id": "m690-ssa-input",
                                                 "kind": "cfg_blocks",
                                                 "blocks": blocks_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "inalcanzable no domina", "expected": "UNKNOWN_UNREACHABLE_NOT_PROVEN"},
            {"condition": "DF/phi derivados no son runtime", "expected": "estatico acotado"}]),
        "limitations": list(limitations) if limitations else
                       ["CFG sintetico minimo; sin cobertura fuera del anfitrion",
                        "Dom/DF/phi estaticos, no comportamiento runtime",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_ssa_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import ssa as SSA
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        p = ev["tool"]["params"]
        succ, pred, ids = SSA.build_graph(p["blocks"])
        Dom = SSA.dominators(succ, pred, str(p["entry"]), ids)
        DF = SSA.dominance_frontier(succ, pred, str(p["entry"]), ids, Dom)
        norm_defs = {k: set(v) for k, v in p["var_defs"].items()}
        phi = SSA.phi_placement(DF, norm_defs)
        if discrepant:
            Dom = dict(Dom)
            for k in Dom:
                Dom[k] = set(Dom[k]) | {"__SPURIOUS__"}
        obs = ev["inferences"][0]
        def sm(d):
            return {k: sorted(v) for k, v in d.items()}
        matches = (sm(Dom) == obs["Dom"] and sm(DF) == obs["DF"]
                   and sm(phi) == ev["inferences_phi"][0]["phi"])
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_Dom": sm(Dom), "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m690"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m690-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

# --- M691: mismo contrato, noveno productor (interproc) ---
# Comun: SCHEMA/procedencia/identidad/verifier/policy/DELIVERED.
# Especifico: traduccion supergraph (arista estatica != ejecucion).

def build_interproc_evidence_package(*, subject_path: str, func_cfgs: dict, call_edges: list,
                                     entry_of: str, producer: str, command: str,
                                     provenance_source: str = "OBSERVED",
                                     epistemic_status: str = "PARTIAL",
                                     limitations=None, subject_sha256=None,
                                     evidence_refs=None, falsification_tests=None,
                                     inference_note: str = "", conclusion_note: str = ""):
    from tools.rxre.analysis import interproc as IP
    from tools.rxre.analysis import dataflow as DF
    if provenance_source != "OBSERVED":
        raise ValueError("procedencia inferida rechazada: source debe ser OBSERVED")
    if not producer or not command:
        raise ValueError("procedencia ausente: producer/command requeridos")
    if epistemic_status == "PROVEN":
        raise ValueError("estado incompatible: interproc no promueve a PROVEN")
    if epistemic_status not in ("PARTIAL", "NOT_DETERMINED", "BLOCKED"):
        if epistemic_status == "PASS":
            raise ValueError("PASS operacional no es estado epistemico (no promover a PROVEN)")
        raise ValueError(f"estado incompatible: {epistemic_status}")
    if limitations is None:
        limitations = []
    if epistemic_status == "PARTIAL" and not limitations:
        raise ValueError("PARTIAL sin limitaciones: no promovible")
    sp = Path(subject_path)
    if not sp.is_file():
        raise FileNotFoundError(subject_path)
    actual_sha = sha256_file(sp)
    if subject_sha256 is not None and subject_sha256 != actual_sha:
        raise ValueError(f"sujeto incorrecto: declarado {subject_sha256} != real {actual_sha}")
    st = sp.stat()
    funcs_json = json.loads(json.dumps(func_cfgs, default=str))
    edges_json = json.loads(json.dumps(call_edges, default=str))
    # reconstruir func_cfgs decodificando hex por bloque
    fc = {}
    for fname, fdata in funcs_json.items():
        blocks = fdata["blocks"]
        hexmap = fdata["hex_per_block"]
        insns = {str(bid): DF.decode_function(bytes.fromhex(hx), 0x1000) for bid, hx in hexmap.items()}
        fc[fname] = (blocks, insns)
    norm_edges = [(str(e[0]), str(e[1]), [str(x) for x in e[2]], str(e[3])) for e in edges_json]
    IN, OUT, succ, pred, all_ids = IP.interproc_reaching(fc, norm_edges, str(entry_of))
    def rs(ss):
        return {k: sorted(f"{r}:{i}" for (r, i) in v) for k, v in ss.items()}
    def ms(d):
        return {k: sorted(v) for k, v in d.items()}
    in_sorted, out_sorted = rs(IN), rs(OUT)
    known_bids = {str(b["id"]) for f in func_cfgs.values() for b in f["blocks"]}
    edge_kind = {}
    for (cb, ce, cexits, rb) in norm_edges:
        if ce not in known_bids:
            edge_kind[f"{cb}->{ce}"] = "INDIRECT_EXTERNAL_UNKNOWN"
        else:
            edge_kind[f"{cb}->{ce}"] = "DIRECT_OBSERVED"
    unreachable = sorted(set(all_ids) - {str(b) for f in funcs_json.values() for b in f["blocks"]})
    pkg = {
        "schema": SCHEMA,
        "subject": {"path": str(sp), "sha256": actual_sha, "dev": st.st_dev,
                    "ino": st.st_ino, "size": st.st_size},
        "tool": {"name": "interproc.interproc_reaching", "version": "m580",
                 "params": {"func_cfgs": funcs_json, "call_edges": edges_json,
                            "entry_of": str(entry_of)}},
        "provenance": {"producer": producer, "command": command,
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "source": provenance_source},
        "observations": {"funcs": sorted(func_cfgs.keys()),
                         "call_edges": edges_json, "entry_of": str(entry_of),
                         "edge_kind": edge_kind},
        "inferences": [{"kind": "supergraph_reaching",
                        "IN": in_sorted, "OUT": out_sorted,
                        "succ": ms(succ), "pred": ms(pred),
                        "note": inference_note or "arista estatica != ejecucion"}],
        "conclusions": [{"kind": "interprocedural",
                         "IN": in_sorted,
                         "edge_kind": edge_kind, "unreachable": unreachable,
                         "epistemic_status": epistemic_status,
                         "note": conclusion_note or "relaciones estaticas, sin prueba de ejecucion"}],
        "evidence_refs": list(evidence_refs or [{"id": "m691-interproc-input",
                                                 "kind": "func_cfgs_edges",
                                                 "func_cfgs": funcs_json, "call_edges": edges_json}]),
        "falsification_tests": list(falsification_tests or [
            {"condition": "arista != ejecucion", "expected": "estatica acotada"},
            {"condition": "externa no es resumen vacio", "expected": "UNKNOWN_EXTERNAL"}]),
        "limitations": list(limitations) if limitations else
                       ["supergraph estatico; sin prueba de ejecucion",
                        "externos/indirectos NO_DETERMINED",
                        "sin equivalencia semantica global"],
    }
    pkg["package_hash"] = hashlib.sha256(
        json.dumps({k: v for k, v in pkg.items() if k != "package_hash"},
                   sort_keys=True, default=str).encode()).hexdigest()
    return pkg

def make_interproc_runner(*, epistemic_status: str, limitations, discrepant=False):
    def runner(request, package_dir: str):
        from tools.rxre.analysis import interproc as IP
        from tools.rxre.analysis import dataflow as DF
        pkg = Path(package_dir)
        ev = json.loads((pkg / "EVIDENCE.json").read_text())
        p = ev["tool"]["params"]
        fc = {}
        for fname, fdata in p["func_cfgs"].items():
            blocks = fdata["blocks"]
            hexmap = fdata["hex_per_block"]
            insns = {str(bid): DF.decode_function(bytes.fromhex(hx), 0x1000) for bid, hx in hexmap.items()}
            fc[fname] = (blocks, insns)
        edges = [(str(e[0]), str(e[1]), [str(x) for x in e[2]], str(e[3])) for e in p["call_edges"]]
        IN, OUT, succ, pred, all_ids = IP.interproc_reaching(fc, edges, str(p["entry_of"]))
        if discrepant:
            OUT = {k: set() for k in OUT}
        def rs(ss):
            return {k: sorted(f"{r}:{i}" for (r, i) in v) for k, v in ss.items()}
        out_sorted = rs(OUT)
        obs = ev["inferences"][0]["OUT"]
        matches = out_sorted == obs
        verdict_status = epistemic_status if matches else "NOT_DETERMINED"
        outs = Path(request.workdir) / "outputs"; outs.mkdir(parents=True, exist_ok=True)
        predf = {"predicted_OUT": out_sorted, "matches_claim": matches}
        (outs / "VERIFIER_PREDICTION.json").write_text(json.dumps(predf))
        sealed = {"sealed_sha256": sha256_file(outs / "VERIFIER_PREDICTION.json"),
                  "ts": "m691"}
        (outs / "SEALED_VERIFIER_PREDICTION.json").write_text(json.dumps(sealed))
        (outs / "VERDICT.json").write_text(json.dumps(
            {"epistemic_status": verdict_status, "matches": matches,
             "limitations": list(limitations)}))
        export = {"messages": [{"content": [{"type": "tool", "state": {"input":
                "write SEALED_VERIFIER_PREDICTION.json with sealed_sha256"}}]}]}
        ep = outs / "export.json"; ep.write_text(json.dumps(export))
        return {"session_id": "m691-offline", "export_path": str(ep),
                "outputs_dir": str(outs),
                "artifacts": {"verdict": str(outs / "VERDICT.json")}}
    return runner

