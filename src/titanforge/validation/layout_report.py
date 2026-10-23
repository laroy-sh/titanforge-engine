from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LayoutIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class LayoutValidationResult:
    layout_path: Path
    schema: str
    version: int
    width: int
    length: int
    zones: tuple[str, ...]
    total_pixels: int
    known_pixels: int
    unknown_pixels: int
    issues: tuple[LayoutIssue, ...]

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")


def validate_layout_file(layout_path: Path) -> LayoutValidationResult:
    try:
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        issue = LayoutIssue("error", "layout.parse", f"Layout file is not valid JSON: {exc}")
        return _empty_result(layout_path, (issue,))
    return validate_layout(layout_path, layout)


def validate_layout(layout_path: Path, layout: Any) -> LayoutValidationResult:
    if not isinstance(layout, dict):
        issue = LayoutIssue("error", "layout.shape", "Layout must be a JSON object.")
        return _empty_result(layout_path, (issue,))

    issues: list[LayoutIssue] = []
    world = _section(layout, "world", issues)
    coverage = _section(layout, "coverage", issues)
    zones_data = _zone_entries(layout, issues)

    schema = str(layout.get("schema", ""))
    version = _int_field(layout, "version", "layout.version", issues)
    width = _int_field(world, "width", "world.width", issues)
    length = _int_field(world, "length", "world.length", issues)
    total_pixels = _int_field(coverage, "totalPixels", "coverage.totalPixels", issues)
    known_pixels = _int_field(coverage, "knownPixels", "coverage.knownPixels", issues)
    unknown_pixels = _int_field(coverage, "unknownPixels", "coverage.unknownPixels", issues)
    zones = tuple(str(zone.get("id", "")) for zone in zones_data if zone.get("id"))

    if schema != "titanforge.mask-layout":
        issues.append(LayoutIssue("error", "layout.schema", "Unsupported or missing layout schema."))
    if version != 1:
        issues.append(LayoutIssue("error", "layout.version", "Unsupported or missing layout version."))
    if width <= 0 or length <= 0:
        issues.append(LayoutIssue("error", "world.size", "World width and length must be positive."))
    if total_pixels != width * length:
        issues.append(LayoutIssue("error", "coverage.total", "Coverage total does not match world size."))
    if known_pixels + unknown_pixels != total_pixels:
        issues.append(LayoutIssue("error", "coverage.sum", "Known and unknown pixel counts do not match total."))
    if not zones:
        issues.append(LayoutIssue("error", "zones.empty", "Layout contains no known zones."))
    if unknown_pixels > 0:
        issues.append(LayoutIssue("warning", "mask.unknown-colors", f"Mask has {unknown_pixels} unknown pixels."))
    if "water" not in zones:
        issues.append(LayoutIssue("warning", "zones.no-water", "Layout has no water zone."))
    if "land" not in zones:
        issues.append(LayoutIssue("warning", "zones.no-land", "Layout has no land zone."))
    if _coverage_percent(zones_data, "water", issues) > 95.0:
        issues.append(LayoutIssue("warning", "zones.too-much-water", "Water covers more than 95% of the mask."))
    if _coverage_percent(zones_data, "land", issues) > 95.0:
        issues.append(LayoutIssue("warning", "zones.too-much-land", "Land covers more than 95% of the mask."))

    return LayoutValidationResult(
        layout_path=layout_path,
        schema=schema,
        version=version,
        width=width,
        length=length,
        zones=zones,
        total_pixels=total_pixels,
        known_pixels=known_pixels,
        unknown_pixels=unknown_pixels,
        issues=tuple(issues),
    )


def write_layout_validation_report(layout_path: Path, report_path: Path) -> LayoutValidationResult:
    result = validate_layout_file(layout_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(format_layout_validation_report(result) + "\n", encoding="utf-8")
    return result


def format_layout_validation_report(result: LayoutValidationResult) -> str:
    lines = [
        "TitanForge Layout Report",
        f"Layout: {result.layout_path}",
        f"Schema: {result.schema}",
        f"Version: {result.version}",
        f"World: {result.width} x {result.length}",
        f"Coverage: {result.known_pixels}/{result.total_pixels} known, {result.unknown_pixels} unknown",
        f"Zones: {', '.join(result.zones) if result.zones else '<none>'}",
        f"Status: {'ERROR' if result.has_errors else 'OK'}",
        f"Errors: {result.error_count}",
        f"Warnings: {result.warning_count}",
    ]

    if result.issues:
        lines.append("")
        lines.append("Issues:")
        for issue in result.issues:
            lines.append(f"- [{issue.severity.upper()}] {issue.code}: {issue.message}")

    return "\n".join(lines)


def _empty_result(layout_path: Path, issues: tuple[LayoutIssue, ...]) -> LayoutValidationResult:
    return LayoutValidationResult(
        layout_path=layout_path,
        schema="",
        version=0,
        width=0,
        length=0,
        zones=(),
        total_pixels=0,
        known_pixels=0,
        unknown_pixels=0,
        issues=issues,
    )


def _section(layout: dict[str, Any], key: str, issues: list[LayoutIssue]) -> dict[str, Any]:
    value = layout.get(key, {})
    if isinstance(value, dict):
        return value
    issues.append(LayoutIssue("error", f"{key}.shape", f"'{key}' must be a JSON object."))
    return {}


def _zone_entries(layout: dict[str, Any], issues: list[LayoutIssue]) -> tuple[dict[str, Any], ...]:
    value = layout.get("zones", [])
    if not isinstance(value, list):
        issues.append(LayoutIssue("error", "zones.shape", "'zones' must be a JSON list."))
        return ()
    entries = tuple(zone for zone in value if isinstance(zone, dict))
    if len(entries) != len(value):
        issues.append(LayoutIssue("error", "zones.shape", "Every entry in 'zones' must be a JSON object."))
    return entries


def _int_field(section: dict[str, Any], key: str, code: str, issues: list[LayoutIssue]) -> int:
    value = section.get(key, 0)
    try:
        if isinstance(value, bool):
            raise TypeError("booleans are not numbers")
        return int(value)
    except (TypeError, ValueError, OverflowError):
        issues.append(LayoutIssue("error", f"{code}.type", f"'{code}' must be a whole number, got {value!r}."))
        return 0


def _coverage_percent(zones_data: tuple[dict[str, Any], ...], zone_id: str, issues: list[LayoutIssue]) -> float:
    for zone in zones_data:
        if zone.get("id") == zone_id:
            value = zone.get("percent", 0.0)
            try:
                return float(value)
            except (TypeError, ValueError):
                issues.append(
                    LayoutIssue("error", "zones.percent.type", f"Zone '{zone_id}' percent must be a number, got {value!r}.")
                )
                return 0.0
    return 0.0
