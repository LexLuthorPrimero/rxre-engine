#!/usr/bin/env python3
"""commands/mission_close.py — Operación de cierre de misión (RXRE-200).

Punto de entrada operativo real para invocar la transición de cierre
de una misión existente. Usa `mission_closure.close_mission()`.

No modifica zonas protegidas ni invoca transiciones masivas.
"""
import argparse, json, sys, os
sys.path.insert(0, "/home/lucas/Escritorio/rxre/tools")
from rxre.mission_closure import close_mission


def run():
    parser = argparse.ArgumentParser(description="Close a mission based on criteria evidence")
    parser.add_argument("mission_id", help="Mission identifier")
    parser.add_argument("--db", default=os.environ.get("RXRE_DB", "/home/lucas/Escritorio/rxre/tools/rxre/storage/rxre.sqlite3"),
                        help="Database path")
    args = parser.parse_args()
    result = close_mission(args.mission_id, db_path=args.db)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
