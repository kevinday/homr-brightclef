"""Opt-in private pre-export evidence owned by the standalone HOMR engine.

AGPL-3.0, Fourdot Tech LLC, 14 October 2026. No application imports.
This module records predictions; it never modifies them or runs recognition.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat

FIELDS = ("rhythm", "pitch", "lift", "articulation", "slur", "position")
MAX_STAFFS = 64
MAX_SYMBOLS = 100000
MAX_FIELD_CHARS = 128
MAX_CAPTURE_BYTES = 64 * 1024 * 1024


def file_sha256(path: Path) -> str:
    # Refuse links and non-files, and detect replacement during a read. No
    # paths or model content enter the diagnostic JSON, only relative names.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("capture identity requires a regular file")
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (
        after.st_size, after.st_mtime_ns, after.st_ino
    ) or path.stat().st_ino != after.st_ino:
        raise ValueError("capture identity changed during read")
    return digest.hexdigest()


def selected_model_paths(config) -> dict[str, Path]:
    from homr.segmentation.config import segnet_path_onnx, segnet_path_onnx_fp16
    from homr.transformer.configs import default_config

    paths = default_config.filepaths
    return {
        "segmentation": Path(segnet_path_onnx_fp16 if config.segnet_use_gpu else segnet_path_onnx),
        "encoder": Path(paths.encoder_path_fp16 if (
            config.transformer_use_gpu or config.coreml_encoder
        ) else paths.encoder_path),
        "decoder": Path(paths.decoder_path_fp16 if config.transformer_use_gpu else paths.decoder_path),
    }


def build_identity(config) -> dict:
    package = Path(__file__).resolve().parent
    models = {role: path.parent.resolve() / path.name
              for role, path in selected_model_paths(config).items()}
    # These are the actual selected checkpoint files, not an expected manifest
    # supplied by the caller. Hash again before capture to refuse changed inputs.
    model_files = {
        role: {"path": str(path.relative_to(package)), "sha256": file_sha256(path)}
        for role, path in models.items()
    }
    code_files = {
        name: file_sha256(package / name)
        for name in ("main.py", "music_xml_generator.py", "symbol_capture.py", "BRIGHTCLEF-NOTICE.md")
    }
    identity = {
        "engineVersion": importlib.metadata.version("homr"),
        "codeFiles": code_files,
        "models": model_files,
        "execution": {"segnetGpu": config.segnet_use_gpu,
                      "transformerGpu": config.transformer_use_gpu,
                      "coremlEncoder": config.coreml_encoder},
    }
    identity["manifestSha256"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return identity


class SymbolCapture:
    def __init__(self, image_path: str, config):
        self.image = Path(image_path)
        self.target = self.image.with_suffix(".model-symbols.json")
        # lexists also catches dangling links. The exclusive open below remains
        # authoritative if another process creates a file after this check.
        if os.path.lexists(self.target):
            raise ValueError("symbol capture destination already exists")
        self.config = config
        self.source_sha256 = file_sha256(self.image)
        self.identity = build_identity(config)

    def write(self, staffs) -> None:
        if len(staffs) > MAX_STAFFS or sum(len(staff) for staff in staffs) > MAX_SYMBOLS:
            raise ValueError("symbol capture exceeds bounds")
        rows = []
        for staff in staffs:
            values = []
            for symbol in staff:
                row = {field: getattr(symbol, field) for field in FIELDS}
                if any(not isinstance(value, str) or len(value) > MAX_FIELD_CHARS
                       for value in row.values()):
                    raise ValueError("invalid musical symbol capture")
                values.append(row)
            rows.append(values)
        if file_sha256(self.image) != self.source_sha256 or build_identity(self.config) != self.identity:
            raise ValueError("symbol capture inputs changed during recognition")
        payload = {"schemaVersion": 1, "producer": "homr-decoded-symbols-before-xml",
                   "engineVersion": self.identity["engineVersion"],
                   "sourceSha256": self.source_sha256,
                   "exportPreservation": "mixed-clef-chords-v1",
                   "engineIdentity": self.identity, "staffs": rows}
        data = (json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n").encode()
        if len(data) > MAX_CAPTURE_BYTES:
            raise ValueError("symbol capture exceeds file budget")
        fd = os.open(self.target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        # Creation permissions are private even under umask 0. A partial write
        # remains evidence of failure; it is never overwritten or reused.
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
