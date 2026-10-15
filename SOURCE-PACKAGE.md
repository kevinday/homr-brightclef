# Corresponding source

This directory is the complete source of **homr 0.7.0+brightclef.export3**, a
modified version of [homr](https://github.com/liebharc/homr) 0.7.0 by
Christian Liebhardt and contributors. It is licensed under the GNU Affero
General Public License version 3 (`LICENSE`), with no additional permissions.
`NOTICE.md` lists every modification and its date. Fourdot Tech LLC
(<support@fourdottech.com>) maintains this modified version for Brightclef.

## 1. The program and its identity

| Item | Value |
|---|---|
| Program | `homr` 0.7.0+brightclef.export3, a modified version of homr 0.7.0 |
| Upstream | <https://github.com/liebharc/homr>, tag `v0.7.0` = `8b5dcf7d7bdd1a47911dc0c661c573b957271eab` |
| Upstream sdist | `homr-0.7.0.tar.gz`, SHA-256 `4078b9e70c16a1250288d92e065528bbd8712617339749407f057aebab9cfb7d` (its `homr/` tree is byte-identical to the tag) |
| Upstream wheel, used only for the stock comparison tests | SHA-256 `84c6028df06e60b1aff158c9049d1876b22137144e319b61bacc41518842c4a9` |
| Licence | GNU AGPL v3 (`LICENSE`, byte-identical to upstream's) |
| Changes | `patches/0001` (MusicXML exporter: clefs joined to notes), `patches/0002` (version, build backend), `patches/0003` (opt-in `--capture-symbols` diagnostic), plus added `homr/BRIGHTCLEF-NOTICE.md` and `homr/symbol_capture.py`; see `NOTICE.md` |
| Build outputs | the wheel, the sdist and `…-corresponding-source.tar.gz`, all hashed in `build-manifest.json` |

## 2. What this package contains

Exactly the paths in `SOURCE-FILES.txt`, plus the unmodified upstream sdist
in the corresponding-source archive. `build/build.py` refuses to pack any path
that is not listed.

| Path | What it is |
|---|---|
| `LICENSE` | GNU AGPL v3 text (upstream copy) |
| `NOTICE.md` | modification notice: what was changed, by whom and when. Also installed inside the program as `homr/BRIGHTCLEF-NOTICE.md` |
| `README.md`, `SOURCE-PACKAGE.md` | interface, build and compatibility notes; this page |
| `UPSTREAM.lock.json` | pinned upstream base, file hashes before and after patching, added files, build epoch, expected wheel hash |
| `patches/0001-split-mixed-clef-chords.patch` | the exporter change, derived from upstream commit `33baa326` |
| `patches/0002-local-version-and-static-build-backend.patch` | version string and build backend |
| `patches/0003-opt-in-symbol-capture.patch`, `native/symbol_capture.py` | the default-off `--capture-symbols` diagnostic |
| `SOURCE-FILES.txt`, `.dockerignore` | source and build-context allowlists |
| `Dockerfile` | standalone build and install recipe and CLI entrypoint. It installs no HOMR checkpoints |
| `build/build.py` | verified, reproducible build |
| `build/install.sh` | installation into a new virtual environment from hash-locked dependency closures |
| `build/qualify.sh` | build plus model-free qualification against the real 0.7.0 wheel |
| `requirements/*.txt`, `*.in` | hash-locked build, runtime and exporter-only closures, constrained by upstream's `poetry.lock` |
| `tests/` | exporter, diagnostic and packaging tests. The fixtures are six synthetic controls of C/D/E notes titled "control" |
| `tools/replay_symbol_capture.py` | re-export of saved `--capture-symbols` files with the installed exporter (code only) |

## 3. Rebuild and verify

```
python3 build/build.py --out DIST                          # downloads the pinned upstream sdist, or:
python3 build/build.py --out DIST --sdist homr-0.7.0.tar.gz
bash build/qualify.sh --python python3.11 --work WORK      # model-free tests, incl. a differential against stock 0.7.0
```

**What the build checks before it writes anything:**
- the upstream sdist hash;
- every patched file's hash before and after patching;
- that every other upstream file is unchanged;
- the declared added files.

**What it writes:** the wheel, the sdist and the corresponding-source archive. The same inputs produce the same bytes. Rebuilding from the corresponding-source archive alone, with its bundled upstream sdist, reproduces all three byte for byte.

## 4. Third-party dependencies

The program runs on these separately distributed packages, used unmodified
and pinned by hash in `requirements/`. Their licences are as each package's
metadata declares them.

| Package | Version | Declared licence |
|---|---|---|
| numpy | 2.4.2 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| musicxml | 1.4 | no licence metadata declared; ships MIT licence text |
| onnxruntime | 1.24.1 | MIT (bundles `ThirdPartyNotices.txt`) |
| opencv-python, opencv-python-headless | 4.13.0.92 | Apache-2.0 |
| rapidocr | 3.7.0 | Apache-2.0 (bundles the PP-OCR models used for title OCR) |
| pillow | 12.1.1 | MIT-CMU |
| requests 2.32.5, urllib3 2.6.3, idna 3.11, charset-normalizer 3.4.4, certifi 2026.1.4 | | Apache-2.0, MIT, BSD-3-Clause, MIT, MPL-2.0 |
| omegaconf 2.3.0, antlr4-python3-runtime 4.9.3, PyYAML 6.0.3 | | BSD-3-Clause, BSD, MIT |
| shapely 2.1.2, pyclipper 1.4.0 | | BSD-3-Clause, MIT |
| sympy 1.14.0, mpmath 1.3.0, flatbuffers 25.12.19, protobuf 6.33.5 | | BSD, BSD, Apache-2.0, BSD-3-Clause |
| colorlog 6.10.1, tqdm 4.67.3, six 1.17.0, packaging 26.0 | | MIT, MPL-2.0 AND MIT, MIT, Apache-2.0 OR BSD-2-Clause |
| typing_extensions 4.15.0, types-Pillow 10.2.0.20240822 | | PSF-2.0, Apache-2.0 |
| *(build only)* poetry-core 2.4.1, setuptools 80.9.0 | | MIT, MIT |

## 5. Model checkpoints (not included)

The checkpoints are not part of this package. The program downloads upstream's
unmodified checkpoints from upstream's release; `homr --init` does this ahead
of time. These are the checkpoints this version uses:

| File (inside the installed `homr/` package) | SHA-256 | Source |
|---|---|---|
| `segmentation/segnet_308-3296ccd40960f90ca6ab9c035cca945675d30a0f.onnx` | `6ed36640db4ef5d223098b6d5efe4eda97c66b24a2c72faab8a018c749003a8d` | `https://github.com/liebharc/homr/releases/tag/onnx_checkpoints` |
| `segmentation/segnet_308-3296ccd40960f90ca6ab9c035cca945675d30a0f_fp16.onnx` (Apple Silicon) | `60f495496cb41473c0521d0811d8f44b9d5cff892d287974a8aebb3eaee2fa83` | same |
| `transformer/encoder_pytorch_model_396-f6feedb42ff90087d898b0941a55d040fa6b2903.onnx` | `4c16df852b3789f2676b0d49f0545dab0740e4005f7b472c5252add642f5d5eb` | same |
| `transformer/decoder_pytorch_model_396-f6feedb42ff90087d898b0941a55d040fa6b2903.onnx` | `3e10fd5ae52d0b86792721922fcd954c283a7ed365de7446425bdabe38f3e57d` | same |

For the licence of the weights and their training data, see upstream's
[`LICENSE_FAQ.md`](https://github.com/liebharc/homr/blob/9f9bbec4e71d89938f87be3bf05a2f0022cd2cf8/LICENSE_FAQ.md).

## 6. Getting the source of a running version

Every build records its version, for example `0.7.0+brightclef.export3`. The
source of each version is published as the tag and release of the same name in
this repository, <https://github.com/kevinday/homr-brightclef>. The release carries the wheel, the sdist, the
corresponding-source archive, `build-manifest.json` and their SHA-256 sums.
