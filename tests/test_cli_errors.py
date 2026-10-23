import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from titanforge.cli import main
from titanforge.validation.layout_report import validate_layout, validate_layout_file


def _run(argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = main(argv)
    return exit_code, stdout.getvalue(), stderr.getvalue()


BAD_LAYOUTS = {
    "list": "[]",
    "world-string": '{"world": "x"}',
    "zone-strings": '{"zones": ["water"]}',
    "width-text": '{"world": {"width": "abc"}}',
    "coverage-list": '{"coverage": [1, 2]}',
    "zones-object": '{"zones": {"id": "water"}}',
    "percent-text": '{"zones": [{"id": "water", "percent": "lots"}]}',
    "width-bool": '{"world": {"width": true}}',
    "malformed": "{not json",
}


class LayoutValidationShapeTests(unittest.TestCase):
    def test_bad_layout_shapes_are_reported_as_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in BAD_LAYOUTS.items():
                with self.subTest(layout=name):
                    layout_path = root / f"{name}.json"
                    layout_path.write_text(text, encoding="utf-8")
                    result = validate_layout_file(layout_path)
                    self.assertTrue(result.has_errors)

    def test_validate_layout_accepts_non_dict_input(self) -> None:
        result = validate_layout(Path("layout.json"), ["water"])
        self.assertEqual([issue.code for issue in result.issues], ["layout.shape"])

    def test_validate_layout_cli_reports_bad_layouts_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in BAD_LAYOUTS.items():
                with self.subTest(layout=name):
                    layout_path = root / f"{name}.json"
                    report_path = root / f"{name}-report.txt"
                    layout_path.write_text(text, encoding="utf-8")
                    exit_code, stdout, _ = _run(["validate-layout", str(layout_path), "--report", str(report_path)])
                    self.assertEqual(exit_code, 1)
                    self.assertIn("Status: ERROR", stdout)
                    self.assertTrue(report_path.exists())

    def test_malformed_json_reports_parse_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout_path = Path(directory) / "layout.json"
            layout_path.write_text("{not json", encoding="utf-8")
            result = validate_layout_file(layout_path)
        self.assertEqual([issue.code for issue in result.issues], ["layout.parse"])

    def test_heightmap_preview_on_malformed_json_gives_clean_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout_path = root / "layout.json"
            layout_path.write_text("{not json", encoding="utf-8")
            exit_code, _, stderr = _run(["heightmap-preview", str(layout_path), str(root / "out.png")])
        self.assertEqual(exit_code, 2)
        self.assertTrue(stderr.startswith("error:"))


class NumericArgumentTests(unittest.TestCase):
    def assert_clean_error(self, argv: list[str], fragment: str) -> None:
        exit_code, _, stderr = _run(argv)
        self.assertEqual(exit_code, 2)
        self.assertTrue(stderr.startswith("error:"), stderr)
        self.assertIn(fragment, stderr)
        self.assertEqual(len(stderr.strip().splitlines()), 1)

    def test_bad_numeric_arguments_give_one_line_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = [
                (["demo-mask", str(root / "m.png"), "--width", "10"], "--width"),
                (["build-location", str(root / "p"), "--width", "10"], "--width"),
                (["build-location", str(root / "p"), "--height", "-5"], "--height"),
                (["night-run", str(root / "n"), "--count", "0"], "--count"),
                (["night-run", str(root / "n"), "--width", "10"], "--width"),
                (["night-run", str(root / "n"), "--size-step", "-1"], "--size-step"),
                (["night-run", str(root / "n"), "--max-minutes", "0"], "--max-minutes"),
            ]
            for argv, fragment in cases:
                with self.subTest(argv=argv):
                    self.assert_clean_error(argv, fragment)
            self.assertFalse((root / "n").exists())

    def test_build_location_with_input_ignores_demo_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mask_path = root / "mask.png"
            self.assertEqual(_run(["demo-mask", str(mask_path), "--width", "32", "--height", "32"])[0], 0)
            exit_code, _, _ = _run(["build-location", str(root / "p"), "--input", str(mask_path), "--width", "10"])
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
