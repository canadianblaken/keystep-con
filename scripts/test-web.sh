#!/bin/sh
# Build the KeyStep Con page and run its three headless-Chrome suites; prints counts and anything not ok.
cd "$(dirname "$0")/../web" && sh build.sh || exit 1
C="${CHROME:-google-chrome}"
OUT=$(mktemp -d)
FAIL=0
for t in functional ccmap tour-walk; do
  CHROME="$C" TIMEOUT=300000 node tests/cdp.mjs "file://$PWD/keystep-interactive-manual.html" tests/$t.js > "$OUT/$t.txt"
  echo "$t: $(grep -ci '": "ok"' "$OUT/$t.txt") ok"
  if grep -vi '": "ok"\|^{\|^}\|ERRORS: none' "$OUT/$t.txt"; then FAIL=1; fi
done
exit $FAIL
