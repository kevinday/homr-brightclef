#!/usr/bin/env python3
"""Build homr 0.7.0+brightclef.export3 from the hash-pinned upstream release.

    python3 build/build.py --out DIR [--sdist homr-0.7.0.tar.gz]

Uses only the standard library of the Python that runs it (3.10 or newer) plus
the hash-pinned build backend in requirements/build.txt, installed into a
throwaway virtual environment. Nothing is installed anywhere else.

Writes to DIR, which must be empty or absent:

  homr-0.7.0+brightclef.export3-py3-none-any.whl
      the modified program
  homr-0.7.0+brightclef.export3.tar.gz
      a pip-installable sdist of the modified program
  homr-0.7.0+brightclef.export3-corresponding-source.tar.gz
      the complete source this component builds from: the unmodified upstream
      sdist plus this component directory (patches, notices, lock files,
      build/install/qualification scripts, tests and fixtures)
  build-manifest.json
      every input and output hash

The build stops on the first mismatch. It verifies:
  - the upstream sdist hash;
  - the base hash of each file a patch touches;
  - the patched hash of each such file;
  - that every other file in the upstream sdist is byte-identical after
    patching, and that only the declared notice and diagnostic module are added.

Running it twice with the same inputs gives byte-identical outputs.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

COMPONENT = Path(__file__).resolve().parent.parent
LOCK = json.loads((COMPONENT / "UPSTREAM.lock.json").read_text(encoding="utf-8"))
# Only explicitly reviewed source paths may enter a source-offer archive.
SOURCE_ALLOWLIST = "SOURCE-FILES.txt"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fail(message: str) -> None:
    sys.exit(f"build refused: {message}")


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def safe_extract(archive: Path, destination: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if not str(target).startswith(str(destination.resolve()) + os.sep):
                fail(f"unsafe path in upstream archive: {member.name}")
            if not (member.isfile() or member.isdir()):
                fail(f"unexpected member type in upstream archive: {member.name}")
        tar.extractall(destination)


def apply_patch(source: Path, patch: Path) -> None:
    if shutil.which("patch") is None:
        fail("the 'patch' program is required")
    with patch.open("rb") as stream:
        result = subprocess.run(
            ["patch", "--batch", "--forward", "--no-backup-if-mismatch", "-p1", "-d", str(source)],
            stdin=stream, capture_output=True,
        )
    if result.returncode != 0:
        fail(f"{patch.name} does not apply cleanly")
    leftovers = [p for p in source.rglob("*") if p.suffix in (".orig", ".rej")]
    if leftovers:
        fail(f"{patch.name} left {leftovers[0].name}")


def deterministic_tar_gz(target: Path, entries: list[tuple[str, Path]], epoch: int) -> None:
    """A tar.gz whose bytes depend only on the entries' names and contents."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name, path in sorted(entries):
            data = path.read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = epoch
            info.mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    with target.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as stream:
            stream.write(buffer.getvalue())


def component_files() -> list[Path]:
    names = (COMPONENT / SOURCE_ALLOWLIST).read_text(encoding="utf-8").splitlines()
    if names != sorted(set(names)) or SOURCE_ALLOWLIST not in names:
        fail("source allowlist must be sorted, unique and include itself")
    files = []
    for name in names:
        relative = Path(name)
        if not name or relative.is_absolute() or ".." in relative.parts or str(relative) != name:
            fail("unsafe source allowlist path")
        path = COMPONENT / relative
        if any((COMPONENT / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
            fail("source allowlist contains a symlink")
        if not path.is_file():
            fail(f"source allowlist file is missing: {name}")
        files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--sdist", type=Path, help="local copy of the upstream sdist (else downloaded)")
    args = parser.parse_args()

    out = args.out.absolute()
    if out.exists() and any(out.iterdir()):
        fail(f"output directory must be empty: {out}")
    out.mkdir(parents=True, exist_ok=True)
    upstream = LOCK["upstream"]
    version = LOCK["buildVersion"]
    epoch = int(LOCK["sourceDateEpoch"])

    with tempfile.TemporaryDirectory(prefix="homr-build-") as work_name:
        work = Path(work_name)
        sdist = args.sdist.absolute() if args.sdist else work / "homr-0.7.0.tar.gz"
        if not args.sdist:
            urllib.request.urlretrieve(upstream["sdist"]["url"], sdist)  # noqa: S310 - pinned URL, hash checked
        if sha256(sdist) != upstream["sdist"]["sha256"]:
            fail("upstream sdist hash mismatch")

        unpacked = work / "unpacked"
        unpacked.mkdir()
        safe_extract(sdist, unpacked)
        source = unpacked / "homr-0.7.0"
        before = tree_hashes(source)
        for name, digests in LOCK["files"].items():
            if before.get(name) != digests["baseSha256"]:
                fail(f"base hash mismatch for {name}")

        for patch in LOCK["patches"]:
            apply_patch(source, COMPONENT / patch)
        for name, spec in LOCK["addedFiles"].items():
            target = source / name
            if target.exists():
                fail(f"added file already exists upstream: {name}")
            shutil.copyfile(COMPONENT / spec["from"], target)

        after = tree_hashes(source)
        for name, digests in LOCK["files"].items():
            if after.get(name) != digests["patchedSha256"]:
                fail(f"patched hash mismatch for {name}")
        for name, spec in LOCK["addedFiles"].items():
            if after.get(name) != sha256(COMPONENT / spec["from"]):
                fail(f"added file differs from its source: {name}")
        changed = {n for n in before if after.get(n) != before[n]}
        added = set(after) - set(before)
        if changed != set(LOCK["files"]) or added != set(LOCK["addedFiles"]):
            fail(f"unexpected changes: changed={sorted(changed)} added={sorted(added)}")

        backend = work / "backend"
        subprocess.run([sys.executable, "-m", "venv", str(backend)], check=True)
        backend_python = backend / "bin" / "python"
        subprocess.run(
            [str(backend_python), "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
             "--no-cache-dir", "--require-hashes", "--no-deps", "--only-binary=:all:",
             "-r", str(COMPONENT / "requirements" / "build.txt")],
            check=True,
        )
        environment = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
        subprocess.run(
            [str(backend_python), "-c",
             "import sys\nfrom poetry.core.masonry.api import build_sdist, build_wheel\n"
             "build_wheel(sys.argv[1]); build_sdist(sys.argv[1])", str(out)],
            cwd=source, env=environment, check=True, stdout=subprocess.DEVNULL,
        )
        backend_version = subprocess.run(
            [str(backend_python), "-c", "import importlib.metadata as m; print(m.version('poetry-core'))"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        corresponding = out / f"homr-{version}-corresponding-source.tar.gz"
        entries = [(f"homr-{version}-corresponding-source/upstream/homr-0.7.0.tar.gz", sdist)]
        entries += [
            (f"homr-{version}-corresponding-source/component/{p.relative_to(COMPONENT)}", p)
            for p in component_files()
        ]
        deterministic_tar_gz(corresponding, entries, epoch)

    wheel = out / f"homr-{version}-py3-none-any.whl"
    pinned = LOCK.get("expectedWheelSha256")
    if pinned and wheel.is_file() and sha256(wheel) != pinned:
        fail(f"the wheel is not the reviewed build: {sha256(wheel)} != {pinned}")
    expected = {wheel.name, f"homr-{version}.tar.gz", corresponding.name}
    produced = {p.name for p in out.iterdir()}
    if produced != expected:
        fail(f"unexpected build outputs: {sorted(produced)}")
    manifest = {
        "schemaVersion": 2,
        "buildVersion": version,
        "inputs": {
            "upstreamSdist": {"name": sdist.name, "sha256": upstream["sdist"]["sha256"]},
            "component": {str(p.relative_to(COMPONENT)): sha256(p) for p in component_files()},
        },
        "verified": {
            "changedFiles": sorted(LOCK["files"]),
            "addedFiles": sorted(LOCK["addedFiles"]),
            "unchangedUpstreamFiles": len(before) - len(LOCK["files"]),
        },
        "builder": {"python": platform.python_version(), "poetryCore": backend_version,
                    "sourceDateEpoch": epoch},
        "outputs": {name: sha256(out / name) for name in sorted(expected)},
    }
    (out / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["outputs"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
