# Modified version of homr: notice

This is a **modified version** of homr, an optical music recognition program by
Christian Liebhardt and contributors (<https://github.com/liebharc/homr>). homr
is licensed under the GNU Affero General Public License, version 3; the text is
in `LICENSE` beside this component, and in the installed program's
distribution metadata. The modified version is licensed under the same licence.
Fourdot Tech LLC adds no further permissions or restrictions under section 7.

## Identity

- Modified program: `homr` **0.7.0+brightclef.export3**
- Based on homr 0.7.0:
  - tag `v0.7.0`, commit `8b5dcf7d7bdd1a47911dc0c661c573b957271eab`;
  - PyPI sdist `homr-0.7.0.tar.gz`, SHA-256
    `4078b9e70c16a1250288d92e065528bbd8712617339749407f057aebab9cfb7d`.
- Modified by Fourdot Tech LLC (<support@fourdottech.com>), for Brightclef:
  the exporter change on **13 October 2026**, the opt-in capture on
  **14 October 2026**, and on **15 October 2026** the version string
  (`export3`) and the maintainer identity in this notice, the patch headers
  and a source comment. The 15 October changes alter no program logic.
- Earlier builds of this modification, `export1` (13 October) and `export2`
  (14 October), were never published.

## What was changed (AGPL section 5(a))

1. **`homr/music_xml_generator.py`.** A new function, `split_mixed_clef_chords`,
   is called once in `build_measures`, after tuplet marks are assigned.
   - It applies to a decoded chord group made only of clefs plus notes or
     rests. That group is written as the clef(s) followed by the notes and
     rests, so the clef no longer becomes a zero-length rest, a phantom rest or
     a shifted onset.
   - Every other group is left exactly as homr 0.7.0 writes it. That includes
     key or time signatures, barlines, repeats or voltas joined to notes, and
     clef-only groups.
   - The change is derived from upstream commit
     `33baa326900faa12702df8c4bdcbea034a3d6a34` ("Split clefs and barlines out of
     chords of notes in the MusicXML writer", by slobaspid, committed by
     Christian Liebhardt on 5 October 2026), narrowed to clefs.
   - Patch: `patches/0001-split-mixed-clef-chords.patch`.
2. **`pyproject.toml`.** Patch: `patches/0002-local-version-and-static-build-backend.patch`.
   - The version is now `0.7.0+brightclef.export3`.
   - The build backend is poetry-core directly. The sdist already disabled
     dynamic versioning.
3. **Added `homr/BRIGHTCLEF-NOTICE.md`.** This notice, installed with the
   program.

4. **`homr/main.py` and added `homr/symbol_capture.py`.** Native opt-in
   `--capture-symbols` writes a bounded, private, no-overwrite JSON sidecar
   immediately before XML export. It binds the input and selected checkpoint
   hashes and the installed engine identity. Ordinary calls do not capture.
   Patch: `patches/0003-opt-in-symbol-capture.patch`; added source:
   `native/symbol_capture.py`.

No recognition, segmentation, decoder, OCR or model logic is changed, and no
model files are added. The build verifies all other upstream files unchanged.

## Source

The complete corresponding source of this version is
`homr-0.7.0+brightclef.export3-corresponding-source.tar.gz`, which
`build/build.py` writes beside the wheel. It contains:
- the unmodified upstream sdist;
- this component: patches, notices, lock files, build and install scripts,
  tests and fixtures.

Source location: <https://github.com/kevinday/homr-brightclef>, release
`0.7.0+brightclef.export3`, which carries this archive and the wheel and sdist
it reproduces. See `SOURCE-PACKAGE.md`.

## Third-party components and models

homr's own notices remain in its source. The program downloads ONNX
checkpoints when it runs (`homr --init` provisions them ahead of time). Its
title OCR uses RapidOCR models shipped in the RapidOCR wheel. Those weights
carry their own provenance, which this notice does not change; see
`SOURCE-PACKAGE.md`.
