import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from titanforge.cli import main
from titanforge.layouts.mask_layout import write_mask_layout
from titanforge.masks.png import write_rgba_png
from titanforge.terrain.heightmap_preview import render_heightmap_preview


@contextlib.contextmanager
def _working_directory(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _run(argv: list[str]) -> int:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return main(argv)


class PortableLayoutTests(unittest.TestCase):
    def test_location_pack_layout_stores_mask_path_relative_to_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "work").mkdir()
            with _working_directory(root / "work"):
                exit_code = _run(["build-location", "../packs/p", "--width", "32", "--height", "32"])
            layout = json.loads((root / "packs" / "p" / "layout.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(layout["source"]["path"], "mask.png")

    def test_heightmap_preview_works_from_another_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "a").mkdir()
            (root / "b" / "c").mkdir(parents=True)
            with _working_directory(root / "a"):
                build_exit = _run(["build-location", "../x/p", "--width", "32", "--height", "32"])
            with _working_directory(root / "b" / "c"):
                preview_exit = _run(["heightmap-preview", "../../x/p/layout.json", "out.png"])
                output_exists = Path("out.png").exists()

        self.assertEqual(build_exit, 0)
        self.assertEqual(preview_exit, 0)
        self.assertTrue(output_exists)

    def test_mask_layout_uses_posix_relative_path_for_masks_in_other_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mask_path = root / "masks" / "island.png"
            mask_path.parent.mkdir()
            layout_path = root / "layouts" / "layout.json"
            write_rgba_png(mask_path, 1, 1, (((59, 170, 53, 255),),))
            write_mask_layout(mask_path, layout_path)
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            result = render_heightmap_preview(layout_path, root / "heightmap.png")

        self.assertEqual(layout["source"]["path"], "../masks/island.png")
        self.assertEqual(result.known_pixels, 1)

    def test_old_layout_with_working_directory_relative_path_still_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            pack = root / "out" / "pack"
            pack.mkdir(parents=True)
            write_rgba_png(pack / "mask.png", 1, 1, (((59, 170, 53, 255),),))
            write_mask_layout(pack / "mask.png", pack / "layout.json")
            layout = json.loads((pack / "layout.json").read_text(encoding="utf-8"))
            layout["source"]["path"] = "out/pack/mask.png"  # how older versions wrote it
            (pack / "layout.json").write_text(json.dumps(layout), encoding="utf-8")

            with _working_directory(root):
                result = render_heightmap_preview(Path("out/pack/layout.json"), Path("heightmap.png"))

        self.assertEqual(result.known_pixels, 1)

    def test_layout_without_source_path_gives_clean_cli_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout_path = root / "layout.json"
            layout_path.write_text("{}", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                exit_code = main(["heightmap-preview", str(layout_path), str(root / "out.png")])

        self.assertEqual(exit_code, 2)
        self.assertIn("does not name a source mask", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
