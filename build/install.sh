#!/usr/bin/env bash
# Install a built engine into a NEW, dedicated virtual environment.
#
#   build/install.sh --python PY --venv DIR --wheel WHEEL --wheel-sha256 HEX \
#                    --closure runtime|exporter-only
#
# DIR must not exist. This never upgrades or overwrites an existing engine, so a
# shared or production environment cannot be replaced by accident.
#
# --closure runtime        the full recognition program (requirements/runtime-linux-py311.txt)
# --closure exporter-only  only what the model-free exporter tests import
#
# Dependencies come only from the hash-pinned closure and are installed with
# --no-deps, so nothing unpinned is resolved. The one sdist-only dependency
# (antlr4-python3-runtime) is built with the hash-pinned setuptools in
# requirements/sdist-build-tools.txt and no build isolation.
#
# The exporter-only closure installs no models. The runtime closure installs
# RapidOCR bundled OCR models; HOMR checkpoints are NOT installed here. `homr` fetches its ONNX checkpoints from GitHub
# on EVERY invocation if they are missing (homr/main.py download_weights), so
# do not run the program on an image until the reviewed checkpoints are in place:
# provision them with `homr --init` as a separately approved step, then verify
# them against the checkpoint hashes in SOURCE-PACKAGE.md section 5.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="" VENV="" WHEEL="" WHEEL_SHA="" CLOSURE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    --wheel) WHEEL="$2"; shift 2 ;;
    --wheel-sha256) WHEEL_SHA="$2"; shift 2 ;;
    --closure) CLOSURE="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
for v in PYTHON VENV WHEEL WHEEL_SHA CLOSURE; do [ -n "${!v}" ] || { echo "missing required argument ($v)" >&2; exit 2; }; done
case "$CLOSURE" in
  runtime) REQS="$HERE/requirements/runtime-linux-py311.txt" ;;
  exporter-only) REQS="$HERE/requirements/exporter-only.txt" ;;
  *) echo "--closure must be runtime or exporter-only" >&2; exit 2 ;;
esac
[ ! -e "$VENV" ] || { echo "refusing to install into an existing path: $VENV" >&2; exit 2; }
sha() { "$PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"; }
[ "$(sha "$WHEEL")" = "$WHEEL_SHA" ] || { echo "wheel sha256 mismatch" >&2; exit 1; }

"$PYTHON" -m venv "$VENV"
PIP=("$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --no-cache-dir --no-deps --require-hashes)
if [ "$CLOSURE" = runtime ]; then
  "${PIP[@]}" --only-binary=:all: -r "$HERE/requirements/sdist-build-tools.txt"
  "${PIP[@]}" --no-build-isolation --only-binary=:all: --no-binary=antlr4-python3-runtime -r "$REQS"
else
  "${PIP[@]}" --only-binary=:all: -r "$REQS"
fi
"$VENV/bin/python" -m pip install --quiet --disable-pip-version-check --no-cache-dir --no-deps "$WHEEL"

# The installed program must be exactly the reviewed build.
"$VENV/bin/python" - "$HERE/UPSTREAM.lock.json" <<'PY'
import hashlib, importlib.metadata, importlib.util, json, pathlib, sys
lock = json.load(open(sys.argv[1]))
version = importlib.metadata.version("homr")
if version != lock["buildVersion"]:
    sys.exit(f"installed version {version} is not {lock['buildVersion']}")
package = pathlib.Path(importlib.util.find_spec("homr").origin).parent
for name, digests in lock["files"].items():
    if name.startswith("homr/"):
        got = hashlib.sha256((package / name[len("homr/"):]).read_bytes()).hexdigest()
        if got != digests["patchedSha256"]:
            sys.exit(f"installed {name} is not the reviewed modified file")
component = pathlib.Path(sys.argv[1]).parent
for name, spec in lock["addedFiles"].items():
    installed = package / name[len("homr/"):]
    if not installed.is_file() or hashlib.sha256(installed.read_bytes()).hexdigest() != hashlib.sha256((component / spec["from"]).read_bytes()).hexdigest():
        sys.exit(f"installed program differs from reviewed added file {name}")
print(f"installed homr {version}")
PY
if [ "$CLOSURE" = runtime ]; then "$VENV/bin/python" -m pip check; fi
echo "engine executable: $VENV/bin/homr"
