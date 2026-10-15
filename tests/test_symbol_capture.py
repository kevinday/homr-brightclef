"""Model-free capture contract, exercising the installed native CLI functions.

Perception is replaced with authored symbol streams; the real exporter writes
both outputs. This proves wiring/noninterference, not recognition acceptance.
"""
import ast
import contextlib
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import controls
from homr import music_xml_generator as g
from homr import symbol_capture as capture


def identity():
    return {"engineVersion": importlib.metadata.version("homr"), "fixture": "model-free"}


def native_namespace(tokens):
    """Compile installed native function bodies; no alternate capture/export path."""
    import argparse
    source = (Path(capture.__file__).parent / "main.py").read_text()
    tree = ast.parse(source)
    names = {"GpuSupport", "ProcessingConfig", "process_image", "main"}
    selected = ast.Module(body=[n for n in tree.body if getattr(n, 'name', '') in names], type_ignores=[])
    debug = SimpleNamespace(write_teaser=lambda *a: None,
                            clean_debug_files_from_previous_runs=lambda: None)
    namespace = dict(argparse=argparse, os=os, sys=sys, dataclass=dataclass, Enum=Enum,
                     Debug=object, SymbolCapture=capture.SymbolCapture,
                     XmlGeneratorArguments=g.XmlGeneratorArguments, generate_xml=g.generate_xml,
                     replace_extension=lambda p, ext: os.path.splitext(p)[0] + ext,
                     eprint=lambda *a: None, Config=lambda: SimpleNamespace(),
                     detect_staffs_in_image=lambda *a: ([], None, debug, SimpleNamespace(result=lambda _: 'private OCR title')),
                     parse_staffs=lambda *a, **kw: deepcopy(tokens),
                     cuda_available=lambda: False, coreml_available=lambda: False,
                     download_weights=lambda *a: None,
                     ort=SimpleNamespace(set_default_logger_severity=lambda _: None),
                     InvalidProgramArgumentException=ValueError)
    exec(compile(selected, str(Path(capture.__file__).parent / "main.py"), 'exec'), namespace)
    return namespace


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'page.png'
        self.image.write_bytes(b'synthetic input bytes; no recognition')
        self.config = SimpleNamespace(segnet_use_gpu=False, transformer_use_gpu=False, coreml_encoder=False)

    def test_capture_rejects_batch_missing_input_and_init_before_model_provisioning(self):
        ns = native_namespace([])
        provisioned = []
        ns['download_weights'] = lambda *args: provisioned.append(args)
        cases = ([str(self.root)], [], [str(self.root / 'missing.png')],
                 ['--init', str(self.image)])
        for args in cases:
            with self.subTest(args=args), patch.object(sys, 'argv', ['homr', '--capture-symbols', *args]), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    ns['main']()
                self.assertEqual(2, raised.exception.code)
        self.assertEqual([], provisioned)

    def test_real_cli_flag_captures_before_export_without_changing_six_control_outputs(self):
        for name, tokens in controls.DECODER_SPELLED.items():
            with self.subTest(name):
                ns = native_namespace([tokens])
                target = self.image.with_suffix('.model-symbols.json')
                with patch.object(capture, 'build_identity', side_effect=lambda _: identity()), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with patch.object(sys, 'argv', ['homr', str(self.image)]):
                        ns['main']()
                    self.assertFalse(target.exists())
                    plain = self.image.with_suffix('.musicxml').read_bytes()
                    # generate_xml sees a completed sidecar before it receives
                    # the very same authored predictions; the real exporter runs.
                    real_export = ns['generate_xml']
                    def export(*args):
                        self.assertTrue(target.is_file())
                        return real_export(*args)
                    ns['generate_xml'] = export
                    old_umask = os.umask(0)
                    try:
                        with patch.object(sys, 'argv', ['homr', '--capture-symbols', str(self.image)]):
                            ns['main']()
                    finally:
                        os.umask(old_umask)
                self.assertEqual(plain, self.image.with_suffix('.musicxml').read_bytes())
                self.assertEqual(0o600, target.stat().st_mode & 0o777)
                payload = json.loads(target.read_bytes())
                self.assertEqual(hashlib.sha256(self.image.read_bytes()).hexdigest(), payload['sourceSha256'])
                self.assertEqual([{f: getattr(s, f) for f in capture.FIELDS} for s in tokens], payload['staffs'][0])
                self.assertNotIn('private OCR title', target.read_text())
                self.assertEqual('homr-decoded-symbols-before-xml', payload['producer'])
                # The existing engine-side loader accepts old and extended v1.
                import importlib.util
                spec = importlib.util.spec_from_file_location('replay', Path(__file__).resolve().parents[1] / 'tools/replay_symbol_capture.py')
                replay = importlib.util.module_from_spec(spec); spec.loader.exec_module(replay)
                _, restored = replay.load(target)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(real_export(g.XmlGeneratorArguments(), [tokens], 'control').to_string(),
                                     real_export(g.XmlGeneratorArguments(), restored, 'control').to_string())
                del payload['engineIdentity']; target.write_text(json.dumps(payload))
                self.assertEqual(len(tokens), len(replay.load(target)[1][0]))
                target.unlink()

    def test_private_no_clobber_including_symlink_and_race(self):
        target = self.image.with_suffix('.model-symbols.json')
        with patch.object(capture, 'build_identity', side_effect=lambda _: identity()):
            observer = capture.SymbolCapture(str(self.image), self.config)
            target.write_bytes(b'prior evidence')
            with self.assertRaises(FileExistsError): observer.write([])
            self.assertEqual(b'prior evidence', target.read_bytes())
            with self.assertRaises(ValueError): capture.SymbolCapture(str(self.image), self.config)
            target.unlink(); target.symlink_to(self.root / 'absent')
            with self.assertRaises(ValueError): capture.SymbolCapture(str(self.image), self.config)
            self.assertFalse((self.root / 'absent').exists())

    def test_changed_input_or_identity_is_refused_before_writing(self):
        with patch.object(capture, 'build_identity', side_effect=lambda _: identity()):
            observer = capture.SymbolCapture(str(self.image), self.config)
            self.image.write_bytes(b'changed input')
            with self.assertRaises(ValueError): observer.write([])
        with patch.object(capture, 'build_identity', side_effect=[identity(), {"changed": True}]):
            observer = capture.SymbolCapture(str(self.image), self.config)
            with self.assertRaises(ValueError): observer.write([])
        self.assertFalse(self.image.with_suffix('.model-symbols.json').exists())

    def test_staff_symbol_field_and_file_limits_fail_without_partial_capture(self):
        row = SimpleNamespace(**{f: '_' for f in capture.FIELDS})
        bad = SimpleNamespace(**{f: '_' for f in capture.FIELDS}); bad.pitch = 'x' * 129
        for staffs in ([[]] * 65, [[row] * 100001], [[bad]], [[SimpleNamespace(**{f: 0 for f in capture.FIELDS})]]):
            with self.subTest(size=len(staffs)), patch.object(capture, 'build_identity', side_effect=lambda _: identity()):
                observer = capture.SymbolCapture(str(self.image), self.config)
                with self.assertRaises(ValueError): observer.write(staffs)
        with patch.object(capture, 'build_identity', side_effect=lambda _: identity()), patch.object(capture, 'MAX_CAPTURE_BYTES', 1):
            observer = capture.SymbolCapture(str(self.image), self.config)
            with self.assertRaises(ValueError): observer.write([])
        self.assertFalse(self.image.with_suffix('.model-symbols.json').exists())

    def test_identity_hashes_actual_code_and_selected_files_without_absolute_paths(self):
        names = ('main.py', 'music_xml_generator.py', 'symbol_capture.py', 'BRIGHTCLEF-NOTICE.md')
        for name in names: (self.root / name).write_bytes(('source ' + name).encode())
        models = {}
        for role in ('segmentation', 'encoder', 'decoder'):
            path = self.root / (role + '.onnx'); path.write_bytes(('synthetic ' + role).encode()); models[role] = path
        with patch.object(capture, '__file__', str(self.root / 'symbol_capture.py')), patch.object(capture, 'selected_model_paths', return_value=models):
            actual = capture.build_identity(self.config)
        self.assertEqual({n: hashlib.sha256(('source ' + n).encode()).hexdigest() for n in names}, actual['codeFiles'])
        for role, item in actual['models'].items():
            self.assertEqual(role + '.onnx', item['path'])
            self.assertEqual(hashlib.sha256(('synthetic ' + role).encode()).hexdigest(), item['sha256'])
        self.assertNotIn(str(self.root), json.dumps(actual))
        digest = actual.pop('manifestSha256')
        self.assertEqual(hashlib.sha256(json.dumps(actual, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), digest)

    def test_cpu_cuda_and_coreml_select_the_same_paths_as_native_download_configuration(self):
        for seg, gpu, coreml in ((False,False,False),(True,False,False),(True,True,False),(True,False,True)):
            config = SimpleNamespace(segnet_use_gpu=seg, transformer_use_gpu=gpu, coreml_encoder=coreml)
            paths = capture.selected_model_paths(config)
            self.assertEqual(seg, paths['segmentation'].name.endswith('_fp16.onnx'))
            self.assertEqual(gpu or coreml, paths['encoder'].name.endswith('_fp16.onnx'))
            self.assertEqual(gpu, paths['decoder'].name.endswith('_fp16.onnx'))

    def test_identity_refuses_symlinks_and_non_regular_files(self):
        link = self.root / 'link'; link.symlink_to(self.image)
        with self.assertRaises(OSError): capture.file_sha256(link)
        with self.assertRaises((ValueError, OSError)): capture.file_sha256(self.root)
