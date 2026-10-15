"""Native exporter qualification for homr 0.7.0+brightclef.export1.

Every case hands a controlled decoder symbol stream (tests/controls.py) to the
real installed exporter, `homr.music_xml_generator.generate_xml`. No image,
model or recognition is involved, so the tests need only the exporter-only
closure (requirements/exporter-only.txt).

"Stock path" below means this installed exporter with the one added call,
`split_mixed_clef_chords`, replaced by the identity. That is the unmodified
0.7.0 code path, and StockReleaseDifferentialTests proves it: when
HOMR_STOCK_PYTHON names an interpreter with the unmodified homr 0.7.0 wheel,
every stream is exported there too and must match the stock path byte for byte.
build/qualify.sh sets that up.

Run inside the engine environment, from the component directory:
    <engine venv>/bin/python -m unittest discover -s tests -v
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import controls as c  # noqa: E402
from musicxml_facts import onsets, summary, timeline, tuplets, zero_length_rests  # noqa: E402

from homr import music_xml_generator as g  # noqa: E402

COMPONENT = HERE.parent
GOLDEN = HERE / "fixtures" / "golden-078183ab"
LOCK = json.loads((COMPONENT / "UPSTREAM.lock.json").read_text(encoding="utf-8"))


def export(tokens, *, stock: bool = False) -> str:
    patch = (mock.patch.object(g, "split_mixed_clef_chords", lambda groups: groups)
             if stock else contextlib.nullcontext())
    with patch, contextlib.redirect_stdout(io.StringIO()):
        return g.generate_xml(g.XmlGeneratorArguments(), [tokens], "control").to_string()


def groups_of(tokens):
    return g.add_tuplet_start_stop(g.group_into_chords(tokens))


def mixed_groups(tokens) -> int:
    """Groups the backport splits: clefs plus notes/rests and nothing else."""
    count = 0
    for x in groups_of(tokens):
        clefs = sum(s.rhythm.startswith("clef") for s in x.symbols)
        timed = sum(s.rhythm.startswith(("note", "rest")) for s in x.symbols)
        count += bool(clefs and timed and clefs + timed == len(x.symbols))
    return count


# ------------------------------------------------------------------ identity

class BuildIdentityTests(unittest.TestCase):
    def test_installed_program_is_the_modified_build(self):
        self.assertEqual(importlib.metadata.version("homr"), LOCK["buildVersion"])
        digest = hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest()
        self.assertEqual(digest, LOCK["files"]["homr/music_xml_generator.py"]["patchedSha256"])

    def test_installed_program_carries_its_modification_notice(self):
        package = Path(importlib.util.find_spec("homr").origin).parent
        notice = package / "BRIGHTCLEF-NOTICE.md"
        self.assertEqual(notice.read_bytes(), (COMPONENT / "NOTICE.md").read_bytes())


class VocabularyTests(unittest.TestCase):
    """Say which inputs the 0.7.0 decoder could actually have produced."""

    def test_every_stream_except_799s_time_token_is_decoder_emittable(self):
        for name, tokens in c.all_streams().items():
            with self.subTest(name):
                bad = c.outside_070_vocabulary(tokens)
                if name.startswith("six/") or name == "ordinary/799-ordinary":
                    self.assertEqual(bad, ["rhythm=timeSignature_4/4"])
                else:
                    self.assertEqual(bad, [])

    def test_clair_de_lune_needed_its_newer_positions_mapped_down(self):
        verbatim = c.token_lines(c.CLAIR_DE_LUNE_UPSTREAM)
        self.assertEqual(sorted(set(c.outside_070_vocabulary(verbatim))),
                         ["position=lower2", "position=upper2"])


# ---------------------------------- the six controls of the original patch

class SixControlTests(unittest.TestCase):
    golden = json.loads((GOLDEN / "golden.json").read_text(encoding="utf-8"))

    def test_modified_export_reproduces_799_preserved_bytes_and_structure(self):
        for name, group in c.SIX_CONTROLS.items():
            with self.subTest(name):
                xml = export(c.framed(group))
                self.assertEqual(xml, (GOLDEN / f"{name}.preserved.musicxml").read_text(encoding="utf-8"))
                self.assertEqual(summary(xml), self.golden[name]["preserved"])
                self.assertEqual(zero_length_rests(xml), 0)

    def test_stock_path_reproduces_the_unmodified_release_fixtures(self):
        for name, group in c.SIX_CONTROLS.items():
            with self.subTest(name):
                xml = export(c.framed(group), stock=True)
                self.assertEqual(xml, (GOLDEN / f"{name}.stock.musicxml").read_text(encoding="utf-8"))
                self.assertEqual(summary(xml), self.golden[name]["stock"])

    def test_decoder_spelled_time_token_gives_the_same_bytes(self):
        # The original patch spelled the time token `timeSignature_4/4`, which 0.7.0's decoder
        # never emits. The exporter reads both spellings alike, so the controls
        # with the decoder's own `timeSignature/4` give its preserved bytes.
        for name, tokens in c.DECODER_SPELLED.items():
            with self.subTest(name):
                xml = export(tokens)
                self.assertEqual(xml, (GOLDEN / f"{name}.preserved.musicxml").read_text(encoding="utf-8"))
                self.assertEqual(summary(xml), self.golden[name]["preserved"])
                self.assertEqual(zero_length_rests(xml), 0)

    def test_named_obligations(self):
        upper = summary(export(c.framed(c.SIX_CONTROLS["upper-clef-lower-note"])))
        # No phantom quarter rest; C3 sounds at beat 0; the upper staff gets F4.
        self.assertEqual(upper["rests"], [])
        self.assertEqual(upper["pitched"], [[1, "2", "0", "1", "C", "3", "5", "quarter"]])
        self.assertEqual(upper["clefs"][-1], ["1", "F", "4"])
        tuplet = export(c.framed(c.SIX_CONTROLS["tuplet-with-clef"]))
        self.assertIn([1, "1", "1/3", "1/3", "D", "5", "1", "eighth"], summary(tuplet)["pitched"])
        self.assertEqual(tuplets(tuplet), [("C5", "3", "2", ("start",)), ("D5", "3", "2", ()),
                                           ("E5", "3", "2", ("stop",))])
        rest = summary(export(c.framed(c.SIX_CONTROLS["lower-clef-real-rest"])))
        self.assertEqual(rest["rests"], [["2", "1"]])  # the printed rest survives, once
        half = summary(export(c.framed(c.SIX_CONTROLS["lower-clef-half-note"])))
        self.assertIn([1, "2", "0", "2", "C", "4", "5", "half"], half["pitched"])
        mid = summary(export(c.framed(c.SIX_CONTROLS["lower-clef-mid-chord"])))
        self.assertEqual(mid["clefs"][-1], ["2", "G", "2"])


# --------------------------------------------------- ordinary-output identity

class OrdinaryOutputIdentityTests(unittest.TestCase):
    def test_streams_without_a_mixed_clef_group_are_untouched(self):
        for name, tokens in c.ORDINARY.items():
            with self.subTest(name):
                self.assertEqual(mixed_groups(tokens), 0)
                groups = groups_of(tokens)
                split = g.split_mixed_clef_chords(groups)
                self.assertEqual(len(split), len(groups))
                for before, after in zip(groups, split):
                    self.assertIs(before, after)
                self.assertEqual(export(tokens), export(tokens, stock=True))


# ---------------------------------------------------- refusals (left as stock)

class RefusalTests(unittest.TestCase):
    def test_other_mixtures_keep_the_unmodified_export(self):
        # 0.7.0 mishandles some of these too; the narrowed backport leaves every
        # one exactly as the release writes it (upstream 33baa326 is broader).
        for name, tokens in c.REFUSED.items():
            with self.subTest(name):
                groups = groups_of(tokens)
                split = g.split_mixed_clef_chords(groups)
                self.assertEqual(len(split), len(groups))
                for before, after in zip(groups, split):
                    self.assertIs(before, after)
                self.assertEqual(export(tokens), export(tokens, stock=True))


# --------------------------------------------------------- nearby positives

class NearbyPositiveTests(unittest.TestCase):
    def assert_fixed(self, tokens):
        stock, fixed = export(tokens, stock=True), export(tokens)
        self.assertEqual(mixed_groups(tokens), 1)
        self.assertNotEqual(stock, fixed)
        self.assertEqual(zero_length_rests(fixed), 0)
        return stock, fixed

    def test_split_keeps_symbol_objects_and_puts_the_tuplet_mark_on_the_notes(self):
        n, k = c.note("C5", "upper", "note_12"), c.clef("G2", "lower")
        mixed = g.SymbolChord([n, k], "start")
        clefs_only, notes_only = g.SymbolChord([k]), g.SymbolChord([n], "stop")
        out = g.split_mixed_clef_chords([mixed, clefs_only, notes_only])
        self.assertEqual([x.symbols for x in out], [[k], [n], [k], [n]])
        self.assertEqual([x.tuplet_mark for x in out], ["", "start", "", "stop"])
        self.assertIs(out[0].symbols[0], k)
        self.assertIs(out[1].symbols[0], n)
        self.assertIs(out[2], clefs_only)
        self.assertIs(out[3], notes_only)
        self.assertEqual(mixed.symbols, [n, k])  # input not mutated

    def test_clef_joined_to_rests(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["clef-joined-to-rests"])
        self.assertEqual(zero_length_rests(stock), 1)
        self.assertEqual(sorted(summary(fixed)["rests"]), [["1", "1"], ["2", "1"]])
        self.assertEqual(summary(fixed)["clefs"][-1], ["2", "G", "2"])
        self.assertEqual(onsets(fixed), {"C5": [(1, 1)], "E4": [(1, 1)]})

    def test_clef_before_a_lower_run_keeps_later_notes_on_their_own_beats(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["clef-joined-before-lower-run"])
        self.assertEqual(onsets(stock)["F4"], [(1, 1)])  # stock: collides with A4
        self.assertEqual(onsets(fixed), {"C5": [(1, 0)], "C3": [(1, 0)], "A4": [(1, 1)],
                                         "F4": [(1, 2)], "G4": [(1, 3)], "E4": [(1, 3)]})
        lower = [(e[3], e[4]) for e in timeline(ET.fromstring(fixed)) if e[1] == "clef" and e[2] == "2"]
        self.assertEqual(lower, [(0, "F4"), (1, "G2")])

    def test_clef_in_the_middle_of_a_triplet(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["clef-in-middle-of-triplet"])
        self.assertEqual([(p, t) for p, a, n, t in tuplets(fixed) if a == "3"],
                         [("C5", ("start",)), ("D5", ()), ("E5", ("stop",))])
        self.assertEqual(onsets(fixed)["E5"], [(1, Fraction(2, 3))])
        self.assertEqual(onsets(fixed)["F5"], [(1, 1)])
        self.assertEqual(onsets(stock)["F5"], [(1, Fraction(2, 3))])  # stock shortens the bar

    def test_two_clefs_and_a_note(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["two-clefs-and-a-note"])
        self.assertEqual(summary(fixed)["clefs"],
                         [["1", "G", "2"], ["2", "F", "4"], ["2", "G", "2"], ["1", "F", "4"]])
        self.assertEqual(summary(fixed)["rests"], [])
        self.assertEqual(onsets(fixed), {"C4": [(1, 0)], "D3": [(1, 1)], "E4": [(1, 1)]})
        self.assertEqual(sorted(summary(stock)["rests"]), [["1", "2"], ["2", None]])

    def test_clef_token_carrying_a_stray_pitch_is_not_written_as_a_note(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["clef-token-with-stray-pitch"])
        self.assertIn("F5", onsets(stock))  # stock invents a note from the clef
        self.assertEqual(sorted(onsets(fixed)), ["C3", "F4", "G4"])
        self.assertEqual(summary(fixed)["clefs"][-1], ["2", "F", "4"])

    def test_clef_change_in_a_later_measure(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["clef-change-in-second-measure"])
        clefs = [(e[0], e[2], e[3], e[4]) for e in timeline(ET.fromstring(fixed)) if e[1] == "clef"]
        self.assertEqual(clefs[-1], (2, "2", 0, "G2"))
        self.assertEqual(onsets(fixed)["B3"], [(2, 0)])
        self.assertEqual(onsets(fixed)["C4"], [(2, 2)])

    def test_upper_clef_joined_to_a_slurred_lower_note(self):
        stock, fixed = self.assert_fixed(c.POSITIVE["upper-clef-with-slurred-lower-note"])
        self.assertEqual(summary(stock)["rests"], [["1", "4"]])  # stock: a whole-bar phantom rest
        self.assertEqual(summary(fixed)["rests"], [])
        self.assertEqual(onsets(fixed), {"C3": [(1, 0)], "A3": [(1, 2)], "D3": [(1, 2)]})
        root = ET.fromstring(fixed)
        self.assertEqual([s.get("type") for s in root.iter("slur")], ["start", "stop"])


# ------------------------------------------------------ real-origin evidence

class RealOriginClairDeLuneTests(unittest.TestCase):
    """Upstream test_real_page_clef_change_in_a_chord, replayed on 0.7.0.

    What this shows: the retained real-origin tokens contain exactly one
    clef+note group, and the modification turns stock's dropped clef and
    zero-length rest into the lower G clef, without changing any pitch.

    What it does not show: correct timing. 0.7.0 writes every token line on one
    shared clock; these tokens came from a newer model with second-voice
    positions. Stock writes this 9/8 measure as 4 beats and the modified build
    as 5; neither is 4.5. Upstream fixed timing separately (df36447,
    independent staff clocks), which this backport does not take. Nor is it a
    recognition of our own source image: the page itself was not examined.
    """

    def test_the_case_genuinely_exercises_the_defect(self):
        self.assertEqual(mixed_groups(c.CLAIR_DE_LUNE), 1)
        stock, fixed = export(c.CLAIR_DE_LUNE, stock=True), export(c.CLAIR_DE_LUNE)
        self.assertEqual(zero_length_rests(stock), 1)
        self.assertEqual(zero_length_rests(fixed), 0)
        self.assertEqual([k[1] for k in summary(stock)["clefs"] if k[0] == "2"], ["F"])
        self.assertEqual([k[1] for k in summary(fixed)["clefs"] if k[0] == "2"], ["F", "G"])
        pitches = lambda xml: sorted(e[4] + e[5] for e in summary(xml)["pitched"])
        self.assertEqual(pitches(fixed), pitches(stock))
        self.assertEqual(len(pitches(fixed)), 13)

    def test_timing_is_0_7_0_single_clock_placement_not_musical_truth(self):
        def length(xml):
            last = max(e[3] + e[4] for e in timeline(ET.fromstring(xml)) if e[1] != "clef")
            return last
        self.assertEqual(length(export(c.CLAIR_DE_LUNE, stock=True)), 4)
        self.assertEqual(length(export(c.CLAIR_DE_LUNE)), 5)


# ------------------------------------------- against the real unmodified wheel

STOCK_PYTHON = os.environ.get("HOMR_STOCK_PYTHON", "")


@unittest.skipUnless(STOCK_PYTHON, "HOMR_STOCK_PYTHON (an unmodified homr 0.7.0 interpreter) is not set")
class StockReleaseDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "stock.json"
            subprocess.run([STOCK_PYTHON, str(HERE / "export_streams.py"), str(out)], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cls.stock = json.loads(out.read_text(encoding="utf-8"))

    def test_the_comparison_ran_against_the_unmodified_release(self):
        self.assertEqual(self.stock["version"], LOCK["upstream"]["tag"].lstrip("v"))

    def test_stock_path_equals_the_unmodified_release_on_every_stream(self):
        for name, tokens in c.all_streams().items():
            with self.subTest(name):
                self.assertEqual(export(tokens, stock=True), self.stock["exports"][name])

    def test_the_two_programs_differ_only_where_a_clef_is_joined_to_notes(self):
        for name, tokens in c.all_streams().items():
            with self.subTest(name):
                same = export(tokens) == self.stock["exports"][name]
                self.assertEqual(same, mixed_groups(tokens) == 0)


if __name__ == "__main__":
    unittest.main()
