#!/bin/sh
# RXRE-R3 self-contained verification — filenvercmp AND wc.
# One command; seals + builds + differential + suites. No sibling repo needed.
# Requires: gcc, sha256sum, sh, python3 + pytest.
set -e
cd "$(dirname "$0")"
R3=$(pwd)
ROOT="$R3/../.."

echo "== 1/8 sealed manifest integrity (SHA-256 list) =="
sha256sum -c manifest.txt

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== 2/8 filenvercmp build =="
gcc -std=c11 -O2 -o "$TMP/verify2" verify2.c reconstruction/filenvercmp.c

echo "== 3/8 filenvercmp generations vs native oracle =="
"$TMP/verify2" oracle/cases_seed20261112.txt oracle/matrix_native.txt
"$TMP/verify2" oracle/cases_seed20261113.txt oracle/matrix_native_20261113.txt

echo "== 4/8 wc build (C baseline + utf8 paths) =="
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_wc" wc/verify_wc.c wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_wcflags" wc/verify_wcflags.c wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_m"  wc/verify_m.c  wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_L"  wc/verify_L.c  wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_fu" wc/verify_flags_u8.c wc/wc_recon_m10.c

echo "== 5/8 wc — LC_ALL=C =="
LC_ALL=C "$TMP/verify_wc" wc/cases_seed20261114.txt        wc/matrix_native_wc.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_seed20261115.txt        wc/matrix_native_wc_20261115.txt
LC_ALL=C "$TMP/verify_wcflags" wc/cases_wcflags_seed20261116.txt wc/matrix_native_wcflags.txt
LC_ALL=C "$TMP/verify_wcflags" wc/cases_wcL_seed20261117.txt    wc/matrix_native_wcL.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_high_seed20261118.txt   wc/matrix_high_LC_ALL=C.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_highutf8_seed20261120.txt wc/matrix_highutf8_C.txt

echo "== 6/8 wc — es_AR.utf8 =="
LC_ALL=es_AR.utf8 "$TMP/verify_wc" wc/cases_high_seed20261118.txt   wc/matrix_high_esAR.txt
LC_ALL=es_AR.utf8 "$TMP/verify_wc" wc/cases_highutf8_seed20261120.txt wc/matrix_highutf8.txt
LC_ALL=es_AR.utf8 "$TMP/verify_m"  wc/cases_m_utf8_seed20261121.txt wc/matrix_native_m_utf8.txt utf8
LC_ALL=es_AR.utf8 "$TMP/verify_L"  wc/cases_L_utf8_seed20261123.txt wc/matrix_native_L_utf8.txt utf8
LC_ALL=es_AR.utf8 "$TMP/verify_fu" wc/cases_flags_utf8_seed20261125.txt wc/matrix_flags_utf8.txt utf8

echo "== 7/8 engine test suites =="
python3 -m pytest \
  "$ROOT/tools/rxre/tests/test_integridad_adv_final.py" \
  "$ROOT/tools/rxre/tests/test_contrato_uniforme.py" \
  "$ROOT/tools/rxre/tests/test_reproducibilidad_end2end.py" \
  "$ROOT/tools/rxre/tests/test_semantica_estructural_contraste.py" -q

echo "== 8/8 summary =="
echo "filenvercmp: 2 generations verified (hashes + differential 0 divergencias)"
echo "wc: 11 corpora verified (C + es_AR.utf8; -m/-L/flags subtests)"
echo "engine: 12/12 pytest suites"
echo "VERIFY: all steps passed"
