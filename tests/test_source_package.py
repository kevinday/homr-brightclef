"""Source-offer privacy and reconstruction input contract (no models)."""
import importlib.util
import re
import shlex
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("engine_build", Path(__file__).resolve().parents[1] / "build/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class SourcePackageTests(unittest.TestCase):
    def test_unlisted_private_material_is_not_packed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SOURCE-FILES.txt").write_text("SOURCE-FILES.txt\nsource.py\n")
            (root / "source.py").write_text("print('source')\n")
            (root / "private-capture.json").write_text("private sentinel")
            (root / "weights.onnx").write_bytes(b"weight sentinel")
            with patch.object(build, "COMPONENT", root):
                self.assertEqual([p.name for p in build.component_files()], ["SOURCE-FILES.txt", "source.py"])

    def test_missing_traversal_duplicate_and_symlink_entries_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "link").symlink_to(root / "SOURCE-FILES.txt")
            with patch.object(build, "COMPONENT", root):
                for content in ("SOURCE-FILES.txt\nmissing\n", "../secret\nSOURCE-FILES.txt\n", "SOURCE-FILES.txt\nSOURCE-FILES.txt\n", "SOURCE-FILES.txt\nlink\n"):
                    with self.subTest(content=content):
                        (root / "SOURCE-FILES.txt").write_text(content)
                        with self.assertRaises(SystemExit):
                            build.component_files()

    def test_package_contains_build_install_and_covered_interface_sources(self):
        names = {str(p.relative_to(build.COMPONENT)) for p in build.component_files()}
        self.assertTrue({"Dockerfile", "build/build.py", "build/install.sh", "build/qualify.sh", "UPSTREAM.lock.json", "NOTICE.md", "LICENSE", "tools/replay_symbol_capture.py"} <= names)
        self.assertFalse(any(p.startswith(("server/", "src/", ".transcribe-work/")) for p in names))

    def test_runtime_install_recipes_use_the_locked_wheel_version_and_hash(self):
        # Source archives contain only the standalone recipe. In a checkout,
        # cover the worker recipe too without packaging proprietary worker code.
        recipes = [build.COMPONENT / "Dockerfile"]
        repository = build.COMPONENT.parent.parent
        if (repository / "AGENTS.md").is_file():
            recipes.append(repository / "server/import_worker/Dockerfile")
        for recipe in recipes:
            with self.subTest(recipe=str(recipe)):
                source = recipe.read_text().replace("\\\n", " ")
                variables = dict(re.findall(r"^ARG ([A-Za-z_][A-Za-z_0-9]*)=(\S+)$", source, re.M))
                installs = [line for line in source.splitlines()
                            if line.startswith("RUN ") and "build/install.sh" in line]
                self.assertEqual(len(installs), 1, "each runtime has one reviewed installer")
                args = shlex.split(installs[0][4:])
                self.assertEqual(args[0], "bash")
                self.assertTrue(args[1].endswith("/build/install.sh"))
                def option(name):
                    self.assertEqual(args.count(name), 1)
                    value = args[args.index(name) + 1]
                    if value.startswith("$"):
                        value = variables[value[1:].strip("{}")]
                    return value
                self.assertEqual(option("--closure"), "runtime")
                self.assertEqual(Path(option("--wheel")).name,
                                 f"homr-{build.LOCK['buildVersion']}-py3-none-any.whl")
                self.assertEqual(option("--wheel-sha256"), build.LOCK["expectedWheelSha256"])
