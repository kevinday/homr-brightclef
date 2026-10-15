# homr 0.7.0+brightclef.export3

A separately built, **modified** copy of [homr](https://github.com/liebharc/homr)
0.7.0, the optical music recognition program behind Brightclef's photo import.
Its MusicXML exporter writes a clef that the decoder joined
to notes or rests of the other staff as a clef, instead of a zero-length or
phantom rest. A separate opt-in native CLI flag preserves private pre-export
symbol evidence. Recognition and the musical exporter are unchanged from export1.

This directory is self-contained and licensed under the GNU AGPL v3 (`LICENSE`,
`NOTICE.md`). It imports nothing from Brightclef, and Brightclef imports
nothing from it: Brightclef runs the built program as a subprocess and reads
its output files. `SOURCE-PACKAGE.md` lists the proposed corresponding source
and the open licensing and provenance questions.

## What the program does differently

homr 0.7.0 hands each decoded chord group to the exporter by its first symbol.
When the decoder groups a clef change on one staff with a note or rest on the
other, the clef is lost:
- if a note comes first, the clef becomes a zero-length rest;
- if the clef comes first, it becomes a full-length phantom rest that pushes
  the note later;
- inside a triplet, the stray rest also breaks the tuplet's timing.

`patches/0001-split-mixed-clef-chords.patch` splits such a group, after tuplet
marks are assigned, into its clef(s) followed by its notes and rests. This is
the clef part of upstream commit `33baa326`, which is not yet released.

Upstream also splits key and time signatures, barlines, repeats and voltas
joined to notes. This build deliberately leaves those exactly as 0.7.0 writes
them; `tests/` proves that byte for byte against the real 0.7.0 wheel.

## Native file interface

```
cd <private working directory>
<venv>/bin/homr [--debug] [--capture-symbols] page.png
```

- **Input:** one image path, relative to the working directory. Brightclef
  passes a basename.
- **Output:** `page.musicxml` beside the input. With `--debug`, also homr's
  debug PNGs, including the notehead-mask and bar-marker images.
- **Exit status:** 0 when the MusicXML was written. Otherwise non-zero; for
  example, "No staffs found" on stderr when the page has no staves.
- **stdout/stderr:** diagnostics only, including OCR'd title text. They are
  not an interface: Brightclef discards stdout and uses stderr only to choose
  one stable refusal class.
- **Models:** the program downloads its ONNX checkpoints on **every** run if
  they are missing (`homr/main.py`, `download_weights`). Provision them once
  with `homr --init`, and verify them, before the first image. A worker image
  does this at build time and then runs with no network.

## Build, qualify, install

Requirements: Python 3.10+ (CPython 3.11 for the runtime closure), `patch`, and
network access to PyPI.

```bash
# 1. Model-free qualification: builds, installs the modified and the stock
#    program into new venvs under WORK, runs tests/ against both.
engines/homr/build/qualify.sh --python python3.11 --work /tmp/homr-qualify

# 2. Build only.
python3 engines/homr/build/build.py --out dist/
#    -> homr-0.7.0+brightclef.export3-py3-none-any.whl
#       homr-0.7.0+brightclef.export3.tar.gz
#       homr-0.7.0+brightclef.export3-corresponding-source.tar.gz
#       build-manifest.json

# 3. Install a recognition runtime into a NEW venv (never an existing one).
engines/homr/build/install.sh --python python3.11 --venv /opt/homr --closure runtime \
  --wheel dist/homr-0.7.0+brightclef.export3-py3-none-any.whl \
  --wheel-sha256 <hash from build-manifest.json>
/opt/homr/bin/homr --init        # fetches the checkpoints: a separately approved step
```

`build.py` checks every input and every file:
- the upstream sdist hash;
- the base and patched hashes of each file a patch touches;
- that the other 43 upstream files are unchanged;
- that only the notice and declared diagnostic module are added.

The export1 predecessor reproduced byte-identically under CPython 3.11 and
3.12 on 2026-10-13. Export2 is qualified separately; its build manifest records
the exact interpreter and output hashes. `install.sh` installs only the hash-locked closure, then checks the
installed version, the patched exporter's hash and the notice.

Brightclef's worker image runs exactly these steps:
- `build.py` in a `homr-build` stage;
- `install.sh --closure runtime` into `/opt/homr`, with the wheel hash pinned
  in `ARG HOMR_WHEEL_SHA256`;
- `homr --init`;
- the model check (`verify_homr_models.py`).

### Dependency locks

- `requirements/runtime-linux-py311.txt`: the recognition program's closure.
  It holds homr's own dependencies at the exact versions in upstream
  `poetry.lock` at `v0.7.0` (`requirements/constraints.txt`), with hashes for
  both x86_64 and aarch64 Linux wheels.
- `requirements/exporter-only.txt`: what the exporter tests import (musicxml,
  numpy).
- `requirements/sdist-build-tools.txt`: setuptools, to build the one sdist-only
  dependency, antlr4-python3-runtime 4.9.3, without build isolation.

To regenerate:

```bash
uv pip compile requirements/runtime.in -c requirements/constraints.txt --python-version 3.11 \
  --python-platform x86_64-manylinux_2_28 --generate-hashes --no-header \
  --only-binary :all: --no-binary antlr4-python3-runtime -o requirements/runtime-linux-py311.txt
```

Pinning to upstream's lock is a choice, not a measurement. Whether these
versions equal the closure inside the currently deployed worker image, which
installed `homr[cpu]==0.7.0` unpinned, has not been checked.

## Version compatibility

| Build | `homr` reports | Exporter SHA-256 | Mixed clef groups | Debug rasters |
|---|---|---|---|---|
| this build | `0.7.0+brightclef.export3` | `40da256c…7b9` | written as clefs | identical code to 0.7.0 |
| prior private build | `0.7.0+brightclef.export2` | `40da256c…7b9` | written as clefs; same program, earlier maintainer text | identical code to 0.7.0 |
| prior private build | `0.7.0+brightclef.export1` | `40da256c…7b9` | written as clefs; no native capture | identical code to 0.7.0 |
| upstream (rollback) | `0.7.0` | `e518ca08…26` | zero-length/phantom rest (known loss) | — |

Brightclef's worker accepts only these four builds:
- `HOMR_EXPECTED_VERSION` must name one of them and equal the installed
  version;
- with a model manifest configured, the installed exporter must hash to that
  build's value.

All four reviewed builds share the debug-raster code, so geometry observation works with
either. Receipts record the exact `engineVersion`, which tells you which
exporter produced a score. A new upstream release is **not** compatible until
it has been qualified the same way and added there; never switch to a newer
version automatically.

## Failure behaviour

- **Build or install mismatch** (sdist, patch, file, wheel, closure, version,
  exporter or notice): the script stops, and nothing is installed or changed
  outside its own new directory.
- **Worker startup with the wrong build:** `HomrRuntime.verify` refuses
  - an unreviewed `HOMR_EXPECTED_VERSION`;
  - an installed version that differs from it;
  - a model or exporter hash that differs.

  The worker then does not read pages.
- **Per page:** unchanged from 0.7.0. The worker maps a timeout, launch
  failure, non-zero exit, missing output or "No staffs found" to its fixed
  failure classes, and never copies engine text into receipts or logs.
- **Group shapes the backport leaves alone** (clef plus key, barline, repeat or
  volta joined to notes) are exported exactly as 0.7.0 exports them, so they
  are not repaired, and are no worse.

## Rollback

1. Revert the image/configuration change: the Dockerfile's homr stage and
   install lines, and `HOMR_EXPECTED_VERSION=0.7.0`. The installed `homr` must
   then report `0.7.0` with exporter `e518ca08…`, which `verify` checks.
2. Expect the known loss to return. Under 0.7.0 a clef joined to notes is again
   lost, so affected pages are mis-exported, not refused. Scores read under
   rollback carry `engineVersion: 0.7.0`; treat them as unqualified for mixed
   clefs, and re-read them once this build is restored.
3. Do not restore the earlier in-process exporter patch as a rollback. That
   in-process patching is what this separately built program replaces.

Delivered scores and retained evidence are never rewritten by either
direction.

## Maintenance

- One patch series, one pinned upstream base, one build version per change
  (`export1`, `export2`, `export3`, …), each with notices, tests and a corresponding-source
  archive.
- Drop the patch once an upstream release passes the same qualification.
  Upstream `33baa326` follows an independent-staff-clock change (`df36447`)
  that alters timing generally, so an upgrade is a separate qualification of
  every collected sample, not a drop-in.

## Engine-side tools

`tools/replay_symbol_capture.py` re-exports retained decoder symbol captures
with whichever homr is installed in that interpreter, for stock-versus-modified
comparisons. Captures are private and the tool is diagnostic only: Brightclef's
ordinary production calls do not exchange internal symbols. An explicitly
requested private diagnostic now retains the native JSON file; engine-side
tooling interprets its symbols. This additional interface needs to remain in
the combined-work/source-scope review.

## Standalone source-package build

The `SOURCE-FILES.txt` allowlist controls the source archive; unlisted local
files are excluded and missing or symlinked listed inputs are refused. The
included `Dockerfile` uses only this component as its context and builds the
engine with its Linux runtime closure. Its entrypoint is the native HOMR CLI.
Model-free recipe checks resolve the standalone and worker install arguments
and require their wheel filenames and SHA-256 pins to match `UPSTREAM.lock.json`.
The manifest-driven `qualify.sh` installation exercises the exporter-only closure.
These checks do not qualify a full recognition runtime or OCR parity.
The `build` target fetches no models. The full runtime target installs
RapidOCR's bundled OCR models as a dependency, but does not initialize HOMR
checkpoints. Building the runtime target therefore downloads OCR models.
Running recognition without provisioned HOMR checkpoints makes the program
download them from upstream on first use. Title OCR behavior is unchanged.

From the extracted source archive, run:

```sh
python3 component/build/build.py --sdist upstream/homr-0.7.0.tar.gz --out /tmp/homr-source-rebuild
# Model-free Linux source-build check (does not build the runtime target):
docker build --target build -t homr-export3-source-check component
```

The source-only package excludes Brightclef, private captures, credentials and
weights. Exclusion does not settle whether the combined-work analysis requires
additional integration source. See `SOURCE-PACKAGE.md` before any publication.

## Opt-in pre-export capture (since export2)

`--capture-symbols` writes `<image stem>.model-symbols.json` immediately before
XML export. It requires one existing image file; directories, missing inputs
and `--init` combinations are refused before main() provisions models. Ordinary calls produce no capture. The engine creates the file
exclusively with mode 0600, even under umask 0; existing files or symlinks are
refused, never overwritten. Capture failure fails the diagnostic invocation.
No title, logs, image pixels or reference score enters this file.

The existing schemaVersion 1 fields are retained: producer
`homr-decoded-symbols-before-xml`, engineVersion, sourceSha256,
exportPreservation and staffs. Each staff contains only rhythm, pitch, lift,
articulation, slur and position strings. Bounds are 64 staves, 100000 total
symbols, 128 characters per field and 64 MiB encoded JSON. Old captures remain
readable by `tools/replay_symbol_capture.py`.

The additive engineIdentity contains the engine version, hashes of main.py,
music_xml_generator.py, symbol_capture.py and the installed modification
notice, the three selected segmentation/encoder/decoder checkpoint relative
paths and SHA-256 hashes, and the selected GPU/CoreML configuration. Its
manifestSha256 is the SHA-256 of the other identity fields encoded as JSON
with sorted keys and compact separators. Input and identities are hashed
before recognition and rechecked before writing. Missing/changed files refuse
capture; no model is fetched by the capture module. This records musical model
identity, not OCR model identity or a claim of recognition equivalence.

The collector asks only through this flag and validates the private file,
source binding, exact reviewed code identity, model-manifest hashes when
configured and bounded schema. It refuses unavailable, stale or malformed
capture, preserving a failed custody receipt. It neither imports engine code
nor changes engine runtime behavior through injection. Export1/stock ordinary
reads remain supported, but cannot satisfy a new raw-symbol capture request.

The owner accepted these engineering requirements. Implementing them does not
approve a runtime switch, merge, legal clearance or real-piece acceptance.
Model-free tests substitute authored predictions for perception and run the
real installed CLI function bodies and exporter; they do not certify inference.
