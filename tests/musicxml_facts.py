"""Musical facts read back from exported MusicXML (standard library only)."""
from __future__ import annotations

from fractions import Fraction
from xml.etree import ElementTree as ET


def _walk(root: ET.Element):
    """Yield (measure number, element, onset in beats) in document order."""
    divisions = 1
    for number, measure in enumerate(root.findall("part/measure"), 1):
        divisions = int(measure.findtext("attributes/divisions", str(divisions)))
        cursor = last = Fraction(0)
        for node in measure:
            if node.tag in ("backup", "forward"):
                sign = 1 if node.tag == "forward" else -1
                cursor += Fraction(node.findtext("duration")) / divisions * sign
                continue
            if node.tag == "note":
                onset = last if node.find("chord") is not None else cursor
                if node.find("chord") is None:
                    last = cursor
                    cursor += Fraction(node.findtext("duration") or "0") / divisions
                yield number, node, onset, divisions
            else:
                yield number, node, cursor, divisions


def pitched_events(root: ET.Element) -> list[list]:
    """The original patch's comparison key: (measure, staff, onset, duration, step, octave, voice, type)."""
    out = []
    for number, node, onset, divisions in _walk(root):
        if node.tag == "note" and node.find("pitch") is not None:
            duration = Fraction(node.findtext("duration") or "0") / divisions
            out.append([number, node.findtext("staff"), str(onset), str(duration),
                        node.findtext("pitch/step"), node.findtext("pitch/octave"),
                        node.findtext("voice"), node.findtext("type")])
    return sorted(out)


def timeline(root: ET.Element) -> list[tuple]:
    """(measure, kind, staff, onset, duration-or-sign) for clefs, rests and notes, in order."""
    out = []
    for number, node, onset, divisions in _walk(root):
        if node.tag == "attributes":
            for c in node.iter("clef"):
                out.append((number, "clef", c.get("number"), onset, c.findtext("sign") + c.findtext("line")))
        elif node.tag == "note":
            duration = Fraction(node.findtext("duration") or "0") / divisions
            name = ("rest" if node.find("rest") is not None
                    else node.findtext("pitch/step") + node.findtext("pitch/octave"))
            out.append((number, name, node.findtext("staff"), onset, duration))
    return out


def summary(xml: str) -> dict:
    root = ET.fromstring(xml)
    return {
        "pitched": pitched_events(root),
        "clefs": [[c.get("number"), c.findtext("sign"), c.findtext("line")] for c in root.iter("clef")],
        "rests": [[n.findtext("staff"), n.findtext("duration")] for n in root.iter("note")
                  if n.find("rest") is not None],
    }


def tuplets(xml: str) -> list[tuple]:
    root = ET.fromstring(xml)
    return [(n.findtext("pitch/step") + n.findtext("pitch/octave"),
             n.findtext("time-modification/actual-notes"),
             n.findtext("time-modification/normal-notes"),
             tuple(t.get("type") for t in n.iter("tuplet")))
            for n in root.iter("note") if n.find("pitch") is not None]


def zero_length_rests(xml: str) -> int:
    root = ET.fromstring(xml)
    return sum(1 for n in root.iter("note")
               if n.find("rest") is not None and int(n.findtext("duration") or 0) == 0)


def onsets(xml: str) -> dict[str, list]:
    """Pitch name -> sorted onsets (beats within its measure, with measure number)."""
    out: dict[str, list] = {}
    for number, kind, staff, onset, _ in timeline(ET.fromstring(xml)):
        if kind not in ("clef", "rest"):
            out.setdefault(kind, []).append((number, onset))
    return {k: sorted(v) for k, v in out.items()}
