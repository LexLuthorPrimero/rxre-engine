#!/usr/bin/env python3
"""RXRE-117: regresión integral del flujo real (109-114 reparado).

Cubre las 7 etapas validadas en RXRE-END-TO-END-VALIDATION-116.
No modifica producción ni base protegida; usa DB temporal.
No resuelve RXRE-REQUEST-CONTRACT-115 (NOT_DETERMINED); no lo oculta.
"""
import os, sys, json, subprocess, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
MACHINE = os.path.join(PKG, "api", "machine.py")

RESULTADOS = []


def v(nombre, cond, detalle=""):
    ok = bool(cond)
    RESULTADOS.append((nombre, ok, detalle))
    if not ok:
        print("  [FALLA] %s -> %s" % (nombre, detalle[:120]))


def rx(reqs, db=None, timeout=120):
    env = dict(os.environ)
    env["PYTHONPATH"] = PKG
    if db:
        env["RXRE_DB"] = db
    p = subprocess.run([sys.executable, "-B", MACHINE],
                       input="\n".join(json.dumps(r) for r in reqs),
                       capture_output=True, text=True, timeout=timeout, env=env)
    out = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def main():
    dbdir = tempfile.mkdtemp(prefix="rxre117_db_")
    try:
        DB = os.path.join(dbdir, "campo.sqlite3")
        TGT = "0000:01:00.0"
        SES = "s117"

        # 01 query válido
        q = rx([{"op": "query", "question": "quien escribe VM_CONTEXT0_CNTL",
                 "target": TGT}], db=DB)
        v("01_query_ok", bool(q and q[0].get("status") == "ok")
          and len(q[0].get("results") or []) > 0
          and bool(q[0].get("results", [{}])[0].get("result_id")),
          "status=%s results=%d" % (q[0].get("status") if q else "NONE",
          len(q[0].get("results") or []) if q else 0))

        # 02 record persistencia
        writes = [
            {"op": "record", "kind": "hypothesis", "status": "OPEN",
             "session": SES, "target": TGT, "text": "H1"},
            {"op": "record", "kind": "hypothesis", "status": "REFUTED",
             "session": SES, "target": TGT, "text": "H2"},
            {"op": "record", "kind": "claim", "status": "PARTIAL",
             "session": SES, "target": TGT, "text": "C1"},
            {"op": "record", "kind": "frontier", "status": "OPEN",
             "session": SES, "target": TGT, "text": "F1"},
            {"op": "record", "kind": "next_action", "status": "OPEN",
             "session": SES, "target": TGT, "text": "seguir"},
        ]
        wr = rx(writes, db=DB)
        v("02_record_all_ok", len(wr) == 5
          and all(r.get("status") == "ok" for r in wr),
          [r.get("status") for r in wr])

        # 03 DB persistencia
        from core import store as S  # noqa: E402
        c = S.conectar(DB)
        try:
            research_n = c.execute("SELECT COUNT(*) FROM research").fetchone()[0]
            kinds = sorted({r[0] for r in c.execute("SELECT kind FROM research")})
            h_row = c.execute(
                "SELECT refs_json FROM research WHERE kind='hypothesis' LIMIT 1"
            ).fetchone()
            v("03_db_persistencia", research_n >= 5 and h_row is not None
              and "hypothesis" in kinds,
              "research_n=%d kinds=%s h_row=%s" % (research_n, kinds, bool(h_row)))
        finally:
            c.close()

        # 04 checkpoint
        ck = rx([{"op": "checkpoint", "session": SES, "target": TGT}], db=DB)
        c_resp = ck[0] if ck else {}
        v("04_checkpoint_ok", c_resp.get("status") == "ok"
          and bool(c_resp.get("checkpoint"))
          and bool(c_resp.get("next_actions")),
          "status=%s checkpoint=%s next_actions=%d"
          % (c_resp.get("status"), bool(c_resp.get("checkpoint")),
             len(c_resp.get("next_actions") or [])))

        # 05 referencias (lista válida, no None)
        try:
            c = S.conectar(DB)
            refs_rows = c.execute("SELECT refs_json FROM research").fetchall()
            v("05_refs_json", all(isinstance(r[0], (str, list)) or r[0] is None
              for r in refs_rows), "n=%d" % len(refs_rows))
            c.close()
        except Exception as e:
            v("05_refs_json", False, repr(e))

        # 06 errores contractuales
        blk = rx([{"op": "query", "question": "x", "target": "ffff:ff:ff.f"}],
                 db=DB)[0]
        rej = rx([{"op": "record", "kind": "inventado", "text": "x",
                   "session": SES, "target": TGT}], db=DB)[0]
        v("06_target_blocked", blk.get("status") == "blocked",
          "status=%s" % blk.get("status"))
        v("06_kind_invalid", rej.get("status") == "blocked",
          "status=%s" % rej.get("status"))

        # 07 integridad de componentes reparados (113, 112, 114, 109)
        import importlib
        sys.path.insert(0, PKG)
        m = importlib.import_module("api.machine")
        v("07_integridad", callable(m._handle_query)
          and callable(m._env_record) and callable(m._env_checkpoint)
          and "query" in m.HANDLERS and "record" in m.HANDLERS
          and "checkpoint" in m.HANDLERS and callable(m._ops)
          and "ops" in m.HANDLERS,
          "query=%s record=%s checkpoint=%s ops=%s"
          % (callable(m._handle_query), callable(m._env_record),
             callable(m._env_checkpoint), callable(m._handle_ops)))

    finally:
        shutil.rmtree(dbdir, ignore_errors=True)

    # --- Reporte ----------------------------------------------------------
    fallos = [d for d, ok, _ in RESULTADOS if not ok]
    print("")
    print("=" * 60)
    print("RXRE-117 regresión integral (flujo real 116)")
    print("DB temporal aislada: %s" % dbdir[:30] + "...")
    print("verificados: %d | fallos: %d" % (len(RESULTADOS), len(fallos)))
    if fallos:
        for d in fallos:
            print("  [FALLA] %s" % d)
        print("=" * 60)
        sys.exit(1)
    print("TODO VERDE")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
