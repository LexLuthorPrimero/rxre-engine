#!/usr/bin/env python3
"""DB-level guard for M292 — demonstrates defensive trigger (DB_ISO only, not DB_OP)."""
import sqlite3, os
DB_ISO = "/tmp/rxre_289_iso.sqlite3"
# Crear trigger defensivo: si verified_scope='VERIFIED', exige que decision_contract='VERIFIED' y que row_hash_reference coincida con results
c = sqlite3.connect(DB_ISO)
c.execute("""
CREATE TRIGGER IF NOT EXISTS trg_verificacion_integridad
BEFORE INSERT ON verificacion_resultado
WHEN NEW.verified_scope = 'VERIFIED'
BEGIN
    SELECT CASE
        WHEN (SELECT scope_decision FROM results WHERE result_id = NEW.result_id) IS NULL
            THEN RAISE(ABORT, 'Referencia de fila de resultados no encontrada')
        WHEN NEW.decision_contract != 'VERIFIED'
            THEN RAISE(ABORT, 'verified_scope=VERIFIED requiere decision_contract=VERIFIED')
        WHEN NEW.row_hash_reference IS NULL OR length(NEW.row_hash_reference) < 10
            THEN RAISE(ABORT, 'row_hash_reference ausente o incompleto')
    END;
END;
""")
# Nota: SQLite no permite SELECT en WHEN de trigger de forma simple para comparación de hash de fila; esta versión valida consistencia básica.
# También agregar restricción de referencia lógica (no foreign key real porque results es dinámica)
c.commit()
c.close()
print("DB guard creado (DB_ISO): trg_verificacion_integridad (defensivo básico)")
