"""Export every control stream with whichever homr is installed in this interpreter.

    <engine python> tests/export_streams.py OUT.json

Writes {"version": ..., "exports": {stream name: MusicXML or "error: ..."}}.
Run it under the unmodified homr 0.7.0 and under this build to compare the two
programs on identical inputs (test_mixed_clef_export.StockReleaseDifferentialTests
does this when HOMR_STOCK_PYTHON names a stock interpreter).
"""
from __future__ import annotations

import contextlib
import importlib.metadata
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from controls import all_streams  # noqa: E402
from homr import music_xml_generator as g  # noqa: E402


def export(tokens) -> str:
    # The exporter prints warnings for invalid groups; keep stdout clean.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return g.generate_xml(g.XmlGeneratorArguments(), [tokens], "control").to_string()
        except Exception as error:  # noqa: BLE001 - the failure itself is the observation
            return f"error: {type(error).__name__}: {error}"


def main() -> int:
    out = Path(sys.argv[1])
    payload = {"version": importlib.metadata.version("homr"),
               "exports": {name: export(tokens) for name, tokens in all_streams().items()}}
    out.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
