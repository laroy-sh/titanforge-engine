from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from titanforge.masks.classifier import MaskColorClassifier
from titanforge.masks.palette import DEFAULT_ZONE_PALETTE, ZoneDefinition
from titanforge.masks.png import PngImage, read_png, write_rgba_png


UNKNOWN_HEIGHT_COLOR = (255, 0, 255, 255)

ZONE_HEIGHTS = {
    "void": None,
    "water": 38,
    "beach": 92,
    "port": 104,
    "road": 112,
    "city": 122,
    "forest": 132,
    "land": 140,
    "mountain": 220,
}


@dataclass(frozen=True)
class HeightmapPreviewResult:
    layout_path: Path
    mask_path: Path
    output_path: Path
    width: int
    height: int
    known_pixels: int
    unknown_pixels: int


def render_heightmap_preview(
    layout_path: Path,
    output_path: Path,
    mask_override_path: Path | None = None,
    palette: tuple[ZoneDefinition, ...] = DEFAULT_ZONE_PALETTE,
    *,
    mask_image: PngImage | None = None,
) -> HeightmapPreviewResult:
    layout = _load_layout(layout_path)
    mask_path = mask_override_path or _resolve_mask_path(layout_path, layout)
    image = mask_image if mask_image is not None else read_png(mask_path)
    classifier = MaskColorClassifier(palette)

    known_pixels = 0
    unknown_pixels = 0
    output_rows: list[tuple[tuple[int, int, int, int], ...]] = []

    for row in image.pixels:
        output_row: list[tuple[int, int, int, int]] = []
        for rgba in row:
            zone = classifier.classify(rgba)
            if zone is None:
                unknown_pixels += 1
                output_row.append(UNKNOWN_HEIGHT_COLOR)
                continue

            height_value = ZONE_HEIGHTS.get(zone.zone_id)
            known_pixels += 1
            if height_value is None:
                output_row.append((0, 0, 0, 0))
            else:
                output_row.append((height_value, height_value, height_value, 255))

        output_rows.append(tuple(output_row))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_rgba_png(output_path, image.width, image.height, tuple(output_rows))

    return HeightmapPreviewResult(
        layout_path=layout_path,
        mask_path=mask_path,
        output_path=output_path,
        width=image.width,
        height=image.height,
        known_pixels=known_pixels,
        unknown_pixels=unknown_pixels,
    )


def format_heightmap_preview_result(result: HeightmapPreviewResult) -> str:
    return "\n".join(
        [
            f"Heightmap preview: {result.output_path}",
            f"Layout: {result.layout_path}",
            f"Mask: {result.mask_path}",
            f"Size: {result.width} x {result.height}",
            f"Known pixels: {result.known_pixels}",
            f"Unknown pixels: {result.unknown_pixels}",
        ]
    )


def _load_layout(layout_path: Path) -> dict[str, Any]:
    return json.loads(layout_path.read_text(encoding="utf-8"))


def _resolve_mask_path(layout_path: Path, layout: dict[str, Any]) -> Path:
    source = layout.get("source") if isinstance(layout, dict) else None
    raw_path = source.get("path") if isinstance(source, dict) else None
    if not isinstance(raw_path, str) or not raw_path:
        raise FileNotFoundError(f"Layout {layout_path} does not name a source mask (source.path); use --mask to provide one.")

    # New layouts store the mask path relative to the layout folder. Older layouts
    # stored it relative to the working directory, so that is kept as a fallback.
    source_path = Path(raw_path)
    if source_path.is_absolute():
        return source_path

    layout_relative = layout_path.parent / source_path
    if layout_relative.exists():
        return layout_relative

    cwd_relative = Path.cwd() / source_path
    if cwd_relative.exists():
        return cwd_relative

    return layout_relative
