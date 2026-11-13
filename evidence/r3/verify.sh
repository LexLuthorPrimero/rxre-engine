#!/bin/sh
# Self-contained verification of the sealed reconstruction against sealed oracles.
# No sibling repo needed. Requires: gcc, sha256sum, sh, python3+pytest.
set -e
cd "$(dirname "$0")"
ROOT=$(pwd)/../..

echo "== 1/5 integrity (SHA-256 against published seals) =="
sha256sum -c - <<'EOFSUMS'
bfa30fb358795a7052aaff0cd0b833ccd7f77bb16658fd1aaccce48c361874d7  oracle/cases_seed20261112.txt
8333b744b3dc1985648bd54ee432c74770bb78cba18e359ee4779d0acf885873  oracle/cases_seed20261113.txt
ed5e91ef5b810a2dbf21186bfd7742fb1ffa90f55cc088329d045bc9926ec0bd  oracle/matrix_native.txt
e031d3ed6d4c6329cf7edcae55b795fbe0d3c0b121fed34839ec8563b60cf6fd  oracle/matrix_native_20261113.txt
EOFSUMS

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== 2/5 build =="
gcc -std=c11 -O2 -o "$TMP/verify2" verify2.c reconstruction/filenvercmp.c

echo "== 3/5 filenvercmp generation 1 vs native oracle =="
"$TMP/verify2" oracle/cases_seed20261112.txt oracle/matrix_native.txt

echo "== 4/5 filenvercmp generation 2 vs native oracle =="
"$TMP/verify2" oracle/cases_seed20261113.txt oracle/matrix_native_20261113.txt

echo "== 5/5 engine test suites =="
python3 -m pytest \
  "$ROOT/tools/rxre/tests/test_integridad_adv_final.py" \
  "$ROOT/tools/rxre/tests/test_contrato_uniforme.py" \
  "$ROOT/tools/rxre/tests/test_reproducibilidad_end2end.py" \
  "$ROOT/tools/rxre/tests/test_semantica_estructural_contraste.py" -q
echo "VERIFY: all steps passed"
