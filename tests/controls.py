"""Decoder symbol streams used by the exporter qualification.

Every stream here is a controlled input to the real exporter
(`homr.music_xml_generator.generate_xml`): no image, model or recognition is
involved. The module imports only `homr.transformer.vocabulary`, which is
identical in the unmodified 0.7.0 release and in this build, so the same
streams can be exported under either program (see export_streams.py).

Three families:
  SIX_CONTROLS      the six controls of the original exporter patch (labelled
                    "799"), built as it built them (including its `timeSignature_4/4` spelling,
                    which the 0.7.0 decoder never emits; see DECODER_SPELLED).
  ORDINARY          streams without a clef+note/rest group: the modification
                    must leave their bytes unchanged.
  REFUSED           other mixtures joined to notes (key/time signature,
                    barline, repeat, volta) and clef-only groups: the narrowed
                    backport must leave them exactly as 0.7.0 writes them.
  POSITIVE          nearby clef+note/rest groups beyond the six controls.
"""
from __future__ import annotations

from homr.transformer.vocabulary import EncodedSymbol as S
from homr.transformer.vocabulary import Vocabulary

_VOCABULARY = Vocabulary()


def note(pitch: str, position: str, rhythm: str = "note_4") -> S:
    return S(rhythm, pitch, "_", "_", "_", position)


def clef(sign: str, position: str) -> S:
    return S("clef_" + sign, "_", "_", "_", "_", position)


def framed(group: list[S], time: str = "timeSignature_4/4") -> list[S]:
    """The opening the original patch's controls used, around one group."""
    return [clef("G2", "upper"), S("chord"), clef("F4", "lower"), S(time), *group, S("barline")]


def token_lines(text: str, remap: dict[str, str] | None = None) -> list[S]:
    """Parse homr `.tokens` lines: one time position per line, '&' joins a chord."""
    out: list[S] = []
    for line in text.strip().splitlines():
        for index, entry in enumerate(line.split("&")):
            fields = entry.strip().split()
            if remap:
                fields[5] = remap.get(fields[5], fields[5])
            if index:
                out.append(S("chord"))
            out.append(S(*fields))
    return out


def outside_070_vocabulary(tokens: list[S]) -> list[str]:
    """Fields of these symbols that homr 0.7.0's decoder cannot emit."""
    bad = []
    for symbol in tokens:
        for field in ("rhythm", "pitch", "lift", "articulation", "slur", "position"):
            value = getattr(symbol, field)
            if value not in getattr(_VOCABULARY, field):
                bad.append(f"{field}={value}")
    return bad


GRAND = """clef_G2 _ _ _ _ upper&clef_F4 _ _ _ _ lower
keySignature_0 . . . . .
timeSignature/4 . . . . ."""

# ------------------------------------- the original patch's six controls

SIX_CONTROLS = {
    "lower-clef-mid-chord": [note("C5", "upper"), S("chord"), clef("G2", "lower"), S("chord"), note("C4", "lower")],
    "lower-clef-real-rest": [note("C5", "upper"), S("chord"), clef("G2", "lower"), S("chord"),
                             S("rest_4", "_", "_", "_", "_", "lower")],
    "lower-clef-half-note": [note("C5", "upper"), S("chord"), clef("G2", "lower"), S("chord"),
                             note("C4", "lower", "note_2")],
    "tuplet-with-clef": [note("C5", "upper", "note_12"), S("chord"), clef("G2", "lower"),
                         note("D5", "upper", "note_12"), note("E5", "upper", "note_12")],
    "upper-clef-lower-note": [note("C3", "lower"), S("chord"), clef("F4", "upper")],
    "ordinary-no-clef": [note("C5", "upper"), note("D5", "upper")],
}

# The same six groups with the time token the 0.7.0 decoder actually emits.
DECODER_SPELLED = {name: framed(group, "timeSignature/4") for name, group in SIX_CONTROLS.items()}

# ----------------------------------------------------------------- ordinary

ORDINARY = {
    "799-ordinary": framed(SIX_CONTROLS["ordinary-no-clef"]),
    "grand-staff-chords": token_lines(GRAND.replace("keySignature_0", "keySignature_-3") + """
note_4 E4 b _ _ upper&note_4 G4 _ _ _ upper&note_2 C3 _ _ _ lower
note_8 F4 _ _ slurStart upper&rest_4 _ _ _ _ lower
note_8 G4 _ _ slurStop upper
note_4. A4 b _ _ upper&note_4 E3 b _ _ lower
note_8 B4 b _ _ upper
barline . . . . ."""),
    "triplets-and-slurred-repeat-notes": token_lines(GRAND.replace("keySignature_0", "keySignature_1") + """
note_12 G4 _ _ _ upper&note_4 G2 _ _ _ lower
note_12 A4 _ _ _ upper
note_12 B4 _ _ _ upper
note_2 D5 _ _ slurStart upper&note_2 D3 _ _ _ lower
barline . . . . .
note_4 D5 _ _ slurStop upper&note_4 B2 _ _ _ lower
rest_4 _ _ _ _ upper&rest_4 _ _ _ _ lower
note_2 G4 _ staccato _ upper&note_2 G2 _ _ _ lower
barline . . . . ."""),
    "clef-change-on-its-own-and-repeats": token_lines(GRAND + """
repeatStart . . . . .
note_2 C5 _ _ _ upper&note_2 C3 _ _ _ lower
clef_G2 _ _ _ _ lower
note_2 E5 _ _ _ upper&note_2 E4 _ _ _ lower
repeatEnd . . . . .
voltaStart . . . . .
note_1 G4 _ _ _ upper&note_1 G4 _ _ _ lower
voltaStop . . . . .
clef_F4 _ _ _ _ lower
note_1 C5 _ _ _ upper&note_1 C3 _ _ _ lower
bolddoublebarline . . . . ."""),
    "single-staff-melody": token_lines("""
clef_G2 _ _ _ _ upper
keySignature_2 . . . . .
timeSignature/4 . . . . .
note_4 D5 # _ _ upper
note_8 E5 _ _ _ upper
note_8 F5 # _ _ upper
note_2 A5 _ fermata _ upper
barline . . . . ."""),
}

# --------------------------------------------- refusals (left exactly as 0.7.0)

REFUSED_LINES = {
    "key-signature-in-chord": "note_2 D5 _ _ _ upper&note_2 D3 _ _ _ lower&keySignature_2 . . . . .",
    "time-signature-in-chord": "note_4 C5 _ _ _ upper&note_4 C3 _ _ _ lower&timeSignature/4 . . . . .",
    "repeat-in-chord": "note_2 C5 _ _ _ upper&note_2 C3 _ _ _ lower&repeatEnd . . . . .",
    "clef-and-key-in-chord": "note_2 D5 _ _ _ upper&clef_G2 _ _ _ _ lower&keySignature_2 . . . . .",
    "clef-and-repeat-in-chord": "note_2 D5 _ _ _ upper&clef_G2 _ _ _ _ lower&repeatEnd . . . . .",
    "clef-and-volta-in-chord": "note_2 D5 _ _ _ upper&clef_G2 _ _ _ _ lower&voltaStart . . . . .",
    "clef-and-barline-in-chord": "note_2 D5 _ _ _ upper&clef_G2 _ _ _ _ lower&barline . . . . .",
    "clefs-without-notes": "clef_G2 _ _ _ _ lower&clef_F4 _ _ _ _ upper",
}


def refused(line: str) -> list[S]:
    return token_lines(GRAND + f"""
note_2 C5 _ _ _ upper&note_2 C3 _ _ _ lower
{line}
note_2 E5 _ _ _ upper&note_2 E4 _ _ _ lower
barline . . . . .""")


REFUSED = {name: refused(line) for name, line in REFUSED_LINES.items()}

# ------------------------------------------------------------ nearby positives

POSITIVE = {
    # Adapted from upstream 33baa326 test_clef_joined_to_a_chord_of_rests.
    "clef-joined-to-rests": token_lines(GRAND + """
rest_4 _ _ _ _ upper&rest_4 _ _ _ _ lower&clef_G2 _ _ _ _ lower
note_4 C5 _ _ _ upper&note_4 E4 _ _ _ lower
barline . . . . ."""),
    # Adapted from upstream test_clef_change_joined_to_a_chord_of_notes.
    "clef-joined-before-lower-run": token_lines(GRAND + """
note_4 C5 _ _ _ upper&note_4 C3 _ _ _ lower
note_4 A4 _ _ _ upper&clef_G2 _ _ _ _ lower
note_4 F4 _ _ _ lower
note_2 G4 _ _ _ upper&note_2 E4 _ _ _ lower
barline . . . . ."""),
    # Adapted from upstream test_clef_joined_to_the_middle_of_a_triplet.
    "clef-in-middle-of-triplet": token_lines(GRAND + """
note_12 C5 _ _ _ upper&note_4 C3 _ _ _ lower
note_12 D5 _ _ _ upper&clef_G2 _ _ _ _ lower
note_12 E5 _ _ _ upper
note_4 F5 _ _ _ upper&note_4 F4 _ _ _ lower
barline . . . . ."""),
    "two-clefs-and-a-note": token_lines("""
clef_G2 _ _ _ _ upper&clef_F4 _ _ _ _ lower
timeSignature/4 . . . . .
note_4 C4 _ _ _ upper&clef_G2 _ _ _ _ lower&clef_F4 _ _ _ _ upper
note_4 D3 _ _ _ upper&note_4 E4 _ _ _ lower
barline . . . . ."""),
    # Adapted from upstream test_clef_with_a_pitch_is_not_written_as_a_note.
    "clef-token-with-stray-pitch": token_lines("""
clef_G2 _ _ _ _ upper&clef_G2 _ _ _ _ lower
keySignature_0 . . . . .
timeSignature/4 . . . . .
note_2 F4 _ _ _ upper&clef_F4 F5 _ _ _ lower
note_2 G4 _ _ _ upper&note_2 C3 _ _ _ lower
barline . . . . ."""),
    "clef-change-in-second-measure": token_lines(GRAND + """
note_1 C5 _ _ _ upper&note_1 C3 _ _ _ lower
barline . . . . .
note_2 D5 _ _ _ upper&clef_G2 _ _ _ _ lower&note_2 B3 _ _ _ lower
note_2 E5 _ _ _ upper&note_2 C4 _ _ _ lower
barline . . . . ."""),
    "upper-clef-with-slurred-lower-note": token_lines(GRAND + """
note_2 C3 _ _ slurStart lower&clef_F4 _ _ _ _ upper
note_2 D3 _ _ slurStop lower&note_2 A3 _ _ _ upper
barline . . . . ."""),
}

# Upstream test_real_page_clef_change_in_a_chord (Clair de lune, Mutopia
# edition, page 4, first measure of a system), tokens verbatim from upstream
# commit 33baa326. They were decoded by a NEWER upstream model whose positions
# include `upper2`/`lower2`; 0.7.0's vocabulary has only `upper`/`lower`, so
# the stream is replayed with those two positions mapped down. This is
# real-origin exporter evidence, not a 0.7.0 recognition of any image.
CLAIR_DE_LUNE_UPSTREAM = """clef_G2 _ _ _ _ upper&clef_F4 _ _ _ _ lower
keySignature_-5 . . . . .
rest_8 _ _ _ _ upper&note_8 D2 b _ _ lower&note_8 A2 b _ _ lower
note_4 F3 _ _ _ upper2&note_4 A3 b _ _ upper&clef_G2 _ _ _ _ lower
note_8 F4 _ _ _ lower&note_8 A4 b _ slurStart lower
note_4. F5 _ _ _ upper&note_4. A5 b _ _ upper&note_2. F4 _ _ _ lower&note_2. C4 b _ _ lower2&note_2. A4 b _ slurStop lower
note_4. F5 _ _ slurStart_slurStop upper&note_4. D5 b _ _ upper
barline . . . . ."""
CLAIR_DE_LUNE = token_lines(CLAIR_DE_LUNE_UPSTREAM, remap={"upper2": "upper", "lower2": "lower"})


def all_streams() -> dict[str, list[S]]:
    streams: dict[str, list[S]] = {}
    for prefix, family in (("six", {n: framed(g) for n, g in SIX_CONTROLS.items()}),
                           ("decoder-spelled", DECODER_SPELLED), ("ordinary", ORDINARY),
                           ("refused", REFUSED), ("positive", POSITIVE)):
        for name, tokens in family.items():
            streams[f"{prefix}/{name}"] = tokens
    streams["real-origin/clair-de-lune-upstream"] = CLAIR_DE_LUNE
    return streams
