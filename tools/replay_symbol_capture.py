"""Re-export retained decoder symbol captures with the installed exporter.

    <engine python> tools/replay_symbol_capture.py --capture DIR [--capture DIR ...]
        --title TITLE --out REPORT.json [--write-xml DIR]

Engine-side diagnostic tooling. It runs inside an engine environment (stock
0.7.0 or this build), reads `native-*/model-symbols.json` files that an
earlier, separately authorised capture retained, and exports each one with the
installed `generate_xml`. No image, model or recognition is used, and the
captures are never modified. When a `raw.musicxml` was retained next to a
capture it is compared too, after removing only the title, which the capture
deliberately omits (homr reads it by OCR), and the XML declaration homr's
file writer adds.

For each capture the report gives the clef+note/rest groups found, whether the
installed export differs from the unmodified 0.7.0 code path (only meaningful
under this build), and hashes of every input and output. Captures are private
musical data: write reports and XML only into private storage.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import re
from pathlib import Path

from homr import music_xml_generator as g
from homr.transformer.vocabulary import EncodedSymbol

FIELDS = ("rhythm", "pitch", "lift", "articulation", "slur", "position")
TITLE = re.compile(r"<work-title\s*/>|<work-title>.*?</work-title>", re.S)
DECLARATION = re.compile(r"\A<\?xml[^>]*\?>\s*")


def without_file_wrapper(xml: str) -> str:
    """Drop what homr's file writer adds and the capture lacks: the XML
    declaration and the OCR title. Nothing musical is removed."""
    return TITLE.sub("<work-title/>", DECLARATION.sub("", xml))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> tuple[dict, list[list[EncodedSymbol]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    staffs = []
    for staff in payload["staffs"]:
        symbols = []
        for row in staff:
            if set(row) != set(FIELDS) or not all(isinstance(row[f], str) for f in FIELDS):
                raise ValueError(f"unexpected symbol row in {path}")
            symbols.append(EncodedSymbol(*(row[f] for f in FIELDS)))
        staffs.append(symbols)
    return payload, staffs


def export(staffs, title: str, *, stock: bool) -> str:
    original = getattr(g, "split_mixed_clef_chords", None)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            if stock and original is not None:
                g.split_mixed_clef_chords = lambda groups: groups
            return g.generate_xml(g.XmlGeneratorArguments(), staffs, title).to_string()
        finally:
            if original is not None:
                g.split_mixed_clef_chords = original


def mixed(staffs) -> list[dict]:
    out = []
    for index, staff in enumerate(staffs):
        for position, group in enumerate(g.add_tuplet_start_stop(g.group_into_chords(staff))):
            clefs = [s for s in group.symbols if s.rhythm.startswith("clef")]
            timed = [s for s in group.symbols if s.rhythm.startswith(("note", "rest"))]
            if clefs and timed:
                out.append({"staffSequence": index, "group": position,
                            "splitByThisBuild": len(clefs) + len(timed) == len(group.symbols),
                            "rhythms": [s.rhythm for s in group.symbols]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="append", required=True, type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--write-xml", type=Path)
    args = parser.parse_args()
    version = importlib.metadata.version("homr")
    modified = hasattr(g, "split_mixed_clef_chords")
    rows = []
    for root in args.capture:
        for folder in sorted(root.glob("native-*")):
            symbols_path = folder / "model-symbols.json"
            payload, staffs = load(symbols_path)
            installed = export(staffs, args.title, stock=False)
            stock_path = export(staffs, args.title, stock=True) if modified else installed
            row = {
                "capture": f"{root.name}/{folder.name}",
                "modelSymbolsSha256": sha(symbols_path.read_bytes()),
                "capturedSourceSha256": payload.get("sourceSha256"),
                "capturedEngineVersion": payload.get("engineVersion"),
                "symbols": sum(len(s) for s in staffs),
                "mixedClefGroups": mixed(staffs),
                "installedExportSha256": sha(installed.encode()),
                "installedEqualsStockPath": installed == stock_path,
            }
            raw = folder / "raw.musicxml"
            if raw.is_file():
                retained = raw.read_text(encoding="utf-8")
                row["retainedRawSha256"] = sha(raw.read_bytes())
                row["equalsRetainedRawExceptTitle"] = without_file_wrapper(retained) == without_file_wrapper(installed)
            if args.write_xml:
                target = args.write_xml / root.name
                target.mkdir(parents=True, exist_ok=True)
                (target / f"{folder.name}.musicxml").write_text(installed, encoding="utf-8")
            rows.append(row)
    report = {"schemaVersion": 1, "engineVersion": version, "modifiedExporter": modified,
              "inferenceExecuted": False, "referenceSupplied": False, "rows": rows}
    args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"captures": len(rows),
                      "withMixedClefGroups": sum(bool(r["mixedClefGroups"]) for r in rows),
                      "allInstalledEqualStockPath": all(r["installedEqualsStockPath"] for r in rows),
                      "allEqualRetainedRawExceptTitle": all(r.get("equalsRetainedRawExceptTitle", False) for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
