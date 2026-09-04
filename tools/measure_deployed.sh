#!/usr/bin/env bash
# The standard external measurements of a deployed build, in the order the README cites them.
# Appends to docs/LOADTEST.md through tools/loadtest.py (each run writes its own block).
#
#   bash tools/measure_deployed.sh https://labelcheck.dev
#
# Wall time is measured from wherever this runs; the server's own time (the Server-Timing header,
# the whole request on the server) and the pipeline time (OCR and comparison) are reported beside it.
set -uo pipefail
URL="${1:-https://labelcheck.dev}"
cd "$(dirname "$0")/.." || exit 1
PY=./.venv/Scripts/python
[ -x "$PY" ] || PY=python
echo "=== start $(date)  host $URL"
curl -s --max-time 20 "$URL/api/v1/health" | grep -o '"git_sha":"[a-f0-9]*"'
echo "=== one person, front+back (interactive, concurrency 1, n=20)"
$PY tools/loadtest.py --url "$URL" --mode steady --endpoint verify --n 20 --concurrency 1 --interactive
echo "=== two people at once, front+back (interactive, concurrency 2, n=20)"
$PY tools/loadtest.py --url "$URL" --mode steady --endpoint verify --n 20 --concurrency 2 --interactive
echo "=== a front label alone, no statement, so the one extra round of reads runs (interactive, n=10)"
$PY tools/loadtest.py --url "$URL" --mode steady --endpoint extract --n 10 --concurrency 1 --interactive
echo "=== the batch path at capacity (100 single-image reads, concurrency = the server's workers)"
$PY tools/loadtest.py --url "$URL" --mode steady --endpoint extract --n 100 --concurrency 2
echo "=== a burst of 16 with no backoff (the 429 path)"
$PY tools/loadtest.py --url "$URL" --mode burst --endpoint extract --concurrency 16
echo "=== end $(date)"
