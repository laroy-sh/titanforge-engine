from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from titanforge.masks.analyzer import MaskAnalysis, analyze_png_mask
from titanforge.masks.png import PngImage


LAYOUT_SCHEMA = "titanforge.mask-layout"
LAYOUT_VERSION = 1


@dataclass(frozen=True)
class MaskLayoutResult:
    input_path: Path
    output_path: Path
    width: int
    height: int
    zone_count: int
    unknown_color_count: int


def build_mask_layout(
    input_path: Path,
    *,
    image: PngImage | None = None,
    layout_dir: Path | None = None,
) -> dict[str, Any]:
    """Build a layout dict for a PNG mask.

    When ``layout_dir`` is given, ``source.path`` is stored relative to that folder
    (POSIX separators) so the layout keeps working when the folder is moved or read
    from another working directory. Without it, the path is stored as given.
    """
    analysis = analyze_png_mask(input_path, image=image)
    return _layout_from_analysis(analysis, layout_dir=layout_dir)


def write_mask_layout(input_path: Path, output_path: Path, *, image: PngImage | None = None) -> MaskLayoutResult:
    layout = build_mask_layout(input_path, image=image, layout_dir=output_path.parent)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(layout, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    world = layout["world"]
    return MaskLayoutResult(
        input_path=input_path,
        output_path=output_path,
        width=int(world["width"]),
        height=int(world["length"]),
        zone_count=len(layout["zones"]),
        unknown_color_count=len(layout["unknownColors"]),
    )


def format_mask_layout_result(result: MaskLayoutResult) -> str:
    return "\n".join(
        [
            f"Mask layout: {result.output_path}",
            f"Input: {result.input_path}",
            f"Size: {result.width} x {result.height}",
            f"Zones: {result.zone_count}",
            f"Unknown colors: {result.unknown_color_count}",
        ]
    )


def _source_path_for_layout(mask_path: Path, layout_dir: Path | None) -> str:
    import os  # local import keeps this module's import block untouched

    if layout_dir is None:
        return str(mask_path)
    absolute_mask = mask_path.resolve()
    try:
        relative = os.path.relpath(absolute_mask, layout_dir.resolve())
    except ValueError:
        # Different drives on Windows: no relative path exists.
        return absolute_mask.as_posix()
    return Path(relative).as_posix()


def _layout_from_analysis(analysis: MaskAnalysis, *, layout_dir: Path | None = None) -> dict[str, Any]:
    return {
        "schema": LAYOUT_SCHEMA,
        "version": LAYOUT_VERSION,
        "source": {
            "type": "png-mask",
            "path": _source_path_for_layout(analysis.path, layout_dir),
        },
        "world": {
            "width": analysis.width,
            "length": analysis.height,
        },
        "coverage": {
            "totalPixels": analysis.total_pixels,
            "knownPixels": analysis.known_pixels,
            "unknownPixels": analysis.unknown_pixels,
        },
        "zones": [
            {
                "id": stat.zone.zone_id,
                "label": stat.zone.label,
                "color": stat.zone.color.hex_rgb,
                "pixels": stat.pixels,
                "percent": round(stat.percent, 4),
            }
            for stat in analysis.zone_stats
        ],
        "unknownColors": [
            {
                "color": stat.color.hex_rgb,
                "alpha": stat.color.alpha,
                "pixels": stat.pixels,
                "percent": round(stat.percent, 4),
            }
            for stat in analysis.unknown_color_stats
        ],
    }
