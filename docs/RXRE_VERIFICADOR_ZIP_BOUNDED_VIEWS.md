# `tools/rxre/parity/rea_verify_zip_bounded_views.py` — verificador acotado de ZIP bounded view de REA

**Qué hace.** Genera tres fixtures ZIP sintéticas, invoca el `dist/` real de REA (escritura que REA usa en producción: `scanZipDirectory`), y compara el resultado con un oráculo Python independiente "el decoder de producción manda":

1. Campo Unicode Path **final** gana sobre uno anterior (uno `hidden/` y uno `settings.json` → settings.json en la vista).
2. CRC inválido en el campo final ⇒ caída al nombre almacenado (no resurrección de un reclamo anterior).
3. Flag UTF-8 del nombre almacenado domina cualquier campo Unicode Path (almacenado se conserva).

**Veredicto por fixture**: `PARITY | DIVERGENT | INCONCLUSIVE`. INCONCLUSIVE cuando no hay `--rea-dist` o `REA_DIST_DIR` válido o falta `node` en el PATH. Nada se afirma como verificado sin veredicto `PARITY` en el mismo host.

**Uso.**
```bash
export REA_DIST_DIR=/ruta/al/REA/dist
python3 tools/rxre/parity/rea_verify_zip_bounded_views.py --json
```

**Salida ejemplo.**
```
verdict: PARITY
  conflicting_fields       PARITY
  bad_final_crc            PARITY
  utf8_flag_precedence     PARITY
```

**En `origin/main` (pre-fix) reporta DIVERGENT en 2/3 fixtures.** En la rama de fix `fix/desktop-zip-unicode-path-last-field` reporta PARITY. Esto no sustituye verificación de terceros sobre REA; tampoco certifica que `zip.js` y el implementador de resultado concuerden en todos los casos posibles — sólo en estos.

**Contrato**: sin cambio al manifiesto (65 artefactos sellados intactos) ni a la puerta (`verify.sh` no invoca esta herramienta por diseño). Terceros: **NOT_EXECUTED**.
