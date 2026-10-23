from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from pathlib import Path

from titanforge.masks.palette import DEFAULT_ZONE_PALETTE, MaskColor
from titanforge.masks.png import write_rgba_png

DEMO_MASK_MIN_SIZE = 32


@dataclass(frozen=True)
class DemoMaskResult:
    output_path: Path
    width: int
    height: int


def generate_demo_mask(output_path: Path, width: int = 128, height: int = 128) -> DemoMaskResult:
    if width < DEMO_MASK_MIN_SIZE or height < DEMO_MASK_MIN_SIZE:
        raise ValueError(f"Demo mask size must be at least {DEMO_MASK_MIN_SIZE} x {DEMO_MASK_MIN_SIZE}.")

    colors = {zone.zone_id: zone.color.rgba for zone in DEFAULT_ZONE_PALETTE}
    pixels: list[tuple[tuple[int, int, int, int], ...]] = []

    center_x = (width - 1) / 2
    center_y = (height - 1) / 2
    radius_x = width * 0.38
    radius_y = height * 0.34
    beach_radius_x = width * 0.42
    beach_radius_y = height * 0.38
    mountain_center = (width * 0.64, height * 0.37)
    mountain_radius = min(width, height) * 0.11

    for y in range(height):
        row: list[tuple[int, int, int, int]] = []
        for x in range(width):
            normalized_island = ((x - center_x) / radius_x) ** 2 + ((y - center_y) / radius_y) ** 2
            normalized_beach = ((x - center_x) / beach_radius_x) ** 2 + ((y - center_y) / beach_radius_y) ** 2

            if normalized_beach > 1.0:
                zone = "water"
            elif normalized_island > 1.0:
                zone = "beach"
            else:
                zone = "land"

            if zone in {"land", "beach"} and _is_road(x, y, width, height):
                zone = "road"

            if zone == "land" and _is_city_block(x, y, width, height):
                zone = "city"

            if zone == "land" and _is_forest(x, y, width, height):
                zone = "forest"

            if zone == "land" and hypot(x - mountain_center[0], y - mountain_center[1]) <= mountain_radius:
                zone = "mountain"

            if zone in {"water", "beach", "land"} and _is_port(x, y, width, height):
                zone = "port"

            row.append(colors[zone])
        pixels.append(tuple(row))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_rgba_png(output_path, width, height, tuple(pixels))
    return DemoMaskResult(output_path=output_path, width=width, height=height)


def format_demo_mask_result(result: DemoMaskResult) -> str:
    return "\n".join(
        [
            f"Demo mask: {result.output_path}",
            f"Size: {result.width} x {result.height}",
        ]
    )


def _is_road(x: int, y: int, width: int, height: int) -> bool:
    diagonal = abs(y - (height * 0.72 - x * 0.24))
    horizontal = abs(y - height * 0.53)
    return diagonal <= max(1.5, height * 0.012) or (
        horizontal <= max(1.5, height * 0.01) and width * 0.30 <= x <= width * 0.70
    )


def _is_city_block(x: int, y: int, width: int, height: int) -> bool:
    return width * 0.38 <= x <= width * 0.58 and height * 0.43 <= y <= height * 0.62


def _is_forest(x: int, y: int, width: int, height: int) -> bool:
    return x < width * 0.38 and y < height * 0.50


def _is_port(x: int, y: int, width: int, height: int) -> bool:
    return width * 0.42 <= x <= width * 0.62 and height * 0.78 <= y <= height * 0.90
