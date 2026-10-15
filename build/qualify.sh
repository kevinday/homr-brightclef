#!/usr/bin/env bash
# Build the modified engine and run its model-free qualification.
#
#   build/qualify.sh --python python3.11 --work DIR [--sdist homr-0.7.0.tar.gz]
#
# DIR must not exist. Everything is created inside it, so nothing shared is
# touched:
#   DIR/dist           the build outputs and build-manifest.json
#   DIR/modified       the built program with the exporter-only closure
#   DIR/stock          the unmodified homr 0.7.0 wheel (hash-checked) with the same closure
#   DIR/streams.*.json every control stream exported by each program
# then runs tests/ in DIR/modified with HOMR_STOCK_PYTHON=DIR/stock/bin/python.
#
# No image, model or recognition is used, and nothing is downloaded except the
# hash-pinned upstream sdist and wheel and the hash-pinned Python packages.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="" WORK="" SDIST=()
while [ $# -gt 0 ]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --work) WORK="$2"; shift 2 ;;
    --sdist) SDIST=(--sdist "$2"); shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$PYTHON" ] && [ -n "$WORK" ] || { echo "usage: qualify.sh --python PY --work DIR [--sdist PATH]" >&2; exit 2; }
[ ! -e "$WORK" ] || { echo "refusing to reuse an existing path: $WORK" >&2; exit 2; }
mkdir -p "$WORK"; WORK="$(cd "$WORK" && pwd)"
lock() { "$PYTHON" -c 'import json,sys; d=json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d[k]
print(d)' "$HERE/UPSTREAM.lock.json" "$1"; }

"$PYTHON" "$HERE/build/build.py" --out "$WORK/dist" "${SDIST[@]}"
VERSION="$(lock buildVersion)"
WHEEL="$WORK/dist/homr-$VERSION-py3-none-any.whl"
WHEEL_SHA="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["outputs"][sys.argv[2]])' "$WORK/dist/build-manifest.json" "$(basename "$WHEEL")")"
bash "$HERE/build/install.sh" --python "$PYTHON" --venv "$WORK/modified" --wheel "$WHEEL" \
  --wheel-sha256 "$WHEEL_SHA" --closure exporter-only

# The unmodified release, for the differential tests.
"$PYTHON" -m venv "$WORK/stock"
STOCK_PIP=("$WORK/stock/bin/python" -m pip install --quiet --disable-pip-version-check --no-cache-dir --no-deps)
"${STOCK_PIP[@]}" --require-hashes --only-binary=:all: -r "$HERE/requirements/exporter-only.txt"
STOCK_WHEEL="$WORK/homr-0.7.0-py3-none-any.whl"
"$PYTHON" -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' \
  "https://files.pythonhosted.org/packages/py3/h/homr/homr-0.7.0-py3-none-any.whl" "$STOCK_WHEEL"
[ "$("$PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$STOCK_WHEEL")" = "$(lock upstream.publishedWheelSha256)" ] \
  || { echo "upstream wheel sha256 mismatch" >&2; exit 1; }
"${STOCK_PIP[@]}" "$STOCK_WHEEL"

"$WORK/stock/bin/python" "$HERE/tests/export_streams.py" "$WORK/streams.stock.json"
"$WORK/modified/bin/python" "$HERE/tests/export_streams.py" "$WORK/streams.modified.json"
cd "$HERE"
HOMR_STOCK_PYTHON="$WORK/stock/bin/python" PYTHONDONTWRITEBYTECODE=1 \
  "$WORK/modified/bin/python" -m unittest discover -s tests -v
