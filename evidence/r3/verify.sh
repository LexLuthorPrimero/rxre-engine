#!/bin/sh
# RXRE-R3 self-contained verification — filenvercmp AND wc.
# One command; seals + builds + differential + suites. No sibling repo needed.
# Requires: gcc, sha256sum, sh, python3 + pytest.
set -e
cd "$(dirname "$0")"
R3=$(pwd)
ROOT="$R3/../.."

echo "== 1/9 sealed manifest integrity (SHA-256 list) =="
sha256sum -c manifest.txt

echo "== 2/9 native binary identity (fail-closed) =="
LS_SHA=$(sha256sum /usr/bin/ls 2>/dev/null | awk '{print $1}')
WC_SHA=$(sha256sum /usr/bin/wc 2>/dev/null | awk '{print $1}')
LS_ID=54e936d37decdad9ecaf189b1de347605a0a99037ec87bd17679b6cbde871a0c
WC_ID=81d614595c717be908fce809713702efd35ce5a56f5ab7cbc497d1a61eb1a38f
if [ "$LS_SHA" != "$LS_ID" ]; then
  echo "FAIL-CLOSED: /usr/bin/ls sha256=$LS_SHA (expected $LS_ID) - refuse to certify oracle" >&2; exit 3
fi
if [ "$WC_SHA" != "$WC_ID" ]; then
  echo "FAIL-CLOSED: /usr/bin/wc sha256=$WC_SHA (expected $WC_ID) - refuse to certify oracle" >&2; exit 4
fi
echo "native identity OK: /usr/bin/ls=$LS_SHA /usr/bin/wc=$WC_SHA"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== 3/9 filenvercmp build =="
gcc -std=c11 -O2 -o "$TMP/verify2" verify2.c reconstruction/filenvercmp.c

echo "== 4/9 filenvercmp generations vs native oracle =="
"$TMP/verify2" oracle/cases_seed20261112.txt oracle/matrix_native.txt
"$TMP/verify2" oracle/cases_seed20261113.txt oracle/matrix_native_20261113.txt

echo "== 5/9 wc build (C baseline + utf8 paths) =="
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_wc" wc/verify_wc.c wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_wcflags" wc/verify_wcflags.c wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_m"  wc/verify_m.c  wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_L"  wc/verify_L.c  wc/wc_recon_m10.c
gcc -std=c11 -Wall -Wextra -Werror -pedantic -O2 -o "$TMP/verify_fu" wc/verify_flags_u8.c wc/wc_recon_m10.c

echo "== 6/9 wc — LC_ALL=C =="
LC_ALL=C "$TMP/verify_wc" wc/cases_seed20261114.txt        wc/matrix_native_wc.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_seed20261115.txt        wc/matrix_native_wc_20261115.txt
LC_ALL=C "$TMP/verify_wcflags" wc/cases_wcflags_seed20261116.txt wc/matrix_native_wcflags.txt
LC_ALL=C "$TMP/verify_wcflags" wc/cases_wcL_seed20261117.txt    wc/matrix_native_wcL.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_high_seed20261118.txt   wc/matrix_high_LC_ALL=C.txt
LC_ALL=C "$TMP/verify_wc" wc/cases_highutf8_seed20261120.txt wc/matrix_highutf8_C.txt

echo "== 7/9 wc — es_AR.utf8 =="
LC_ALL=es_AR.utf8 "$TMP/verify_wc" wc/cases_high_seed20261118.txt   wc/matrix_high_esAR.txt
LC_ALL=es_AR.utf8 "$TMP/verify_wc" wc/cases_highutf8_seed20261120.txt wc/matrix_highutf8.txt
LC_ALL=es_AR.utf8 "$TMP/verify_m"  wc/cases_m_utf8_seed20261121.txt wc/matrix_native_m_utf8.txt utf8
LC_ALL=es_AR.utf8 "$TMP/verify_L"  wc/cases_L_utf8_seed20261123.txt wc/matrix_native_L_utf8.txt utf8
LC_ALL=es_AR.utf8 "$TMP/verify_fu" wc/cases_flags_utf8_seed20261125.txt wc/matrix_flags_utf8.txt utf8

echo "== 8/9 engine test suites =="
PYTEST_OUT=$(python3 -m pytest \
  "$ROOT/tools/rxre/tests/test_integridad_adv_final.py" \
  "$ROOT/tools/rxre/tests/test_contrato_uniforme.py" \
  "$ROOT/tools/rxre/tests/test_reproducibilidad_end2end.py" \
  "$ROOT/tools/rxre/tests/test_semantica_estructural_contraste.py" -q)
printf '%s\n' "$PYTEST_OUT"
PYTEST_COUNT=$(printf '%s\n' "$PYTEST_OUT" | tail -1 | grep -oE '[0-9]+ passed' | awk '{print $1}')

echo "== 9/9 summary =="
echo "filenvercmp: 2 generations verified (hashes + differential 0 divergencias)"
echo "wc: 11 corpora verified (C + es_AR.utf8; -m/-L/flags subtests)"
echo "engine: ${PYTEST_COUNT} pytest tests passed (count reported by pytest itself)"
echo "VERIFY: all steps passed"
