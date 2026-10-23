from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib

from titanforge import __version__
from titanforge.core.project import ProjectConfig, load_project_config
from titanforge.inventory.scanner import format_inventory_report, scan_inventory
from titanforge.layouts.mask_layout import format_mask_layout_result, write_mask_layout
from titanforge.locations.builder import build_location_pack, format_location_build_result
from titanforge.masks.analyzer import analyze_png_mask, format_mask_analysis
from titanforge.masks.cleanup import format_mask_cleanup_result, render_mask_cleanup_preview
from titanforge.masks.png import PngError
from titanforge.masks.demo import DEMO_MASK_MIN_SIZE, format_demo_mask_result, generate_demo_mask
from titanforge.operations.night_run import format_night_run_result, run_night_run
from titanforge.preview.mask_preview import format_mask_preview_result, render_mask_preview
from titanforge.terrain.heightmap_preview import format_heightmap_preview_result, render_heightmap_preview
from titanforge.validation.layout_report import format_layout_validation_report, validate_layout_file, write_layout_validation_report
from titanforge.versions.targets import ACTIVE_TARGETS, PARKING_LOT_TARGETS, PRIMARY_TARGET


class CliUsageError(Exception):
    """A bad command-line value; reported as a one-line error with exit code 2."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="titanforge",
        description="TitanForge Engine command-line tools.",
    )
    parser.add_argument("--version", action="store_true", help="Show TitanForge Engine version.")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("info", help="Show current engine strategy and version targets.")

    plan_parser = subparsers.add_parser("plan", help="Read and summarize a TitanForge project config.")
    plan_parser.add_argument("config", type=Path, help="Path to titanforge.toml.")

    inventory_parser = subparsers.add_parser(
        "inventory",
        help="Scan a source or donor folder before importing it.",
    )
    inventory_parser.add_argument("path", type=Path, help="Folder to scan.")

    mask_parser = subparsers.add_parser(
        "mask-info",
        help="Inspect a PNG mask and report known TitanForge zone colors.",
    )
    mask_parser.add_argument("path", type=Path, help="PNG mask to inspect.")

    demo_mask_parser = subparsers.add_parser(
        "demo-mask",
        help="Create a small deterministic demo PNG mask for pipeline testing.",
    )
    demo_mask_parser.add_argument("output", type=Path, help="Demo mask PNG output path.")
    demo_mask_parser.add_argument("--width", type=int, default=128, help="Demo mask width.")
    demo_mask_parser.add_argument("--height", type=int, default=128, help="Demo mask height.")

    mask_preview_parser = subparsers.add_parser(
        "mask-preview",
        help="Render a normalized preview PNG from a TitanForge mask.",
    )
    mask_preview_parser.add_argument("input", type=Path, help="PNG mask to preview.")
    mask_preview_parser.add_argument("output", type=Path, help="Preview PNG output path.")

    mask_cleanup_parser = subparsers.add_parser(
        "mask-cleanup-preview",
        help="Render a cleanup preview that removes tiny water/land mask noise.",
    )
    mask_cleanup_parser.add_argument("input", type=Path, help="PNG mask to clean up.")
    mask_cleanup_parser.add_argument("output", type=Path, help="Cleanup preview PNG output path.")
    mask_cleanup_parser.add_argument("--threshold", type=int, default=5, help="Neighbor threshold from 1 to 8.")

    mask_layout_parser = subparsers.add_parser(
        "mask-layout",
        help="Write a neutral layout JSON artifact from a TitanForge PNG mask.",
    )
    mask_layout_parser.add_argument("input", type=Path, help="PNG mask to convert.")
    mask_layout_parser.add_argument("output", type=Path, help="Layout JSON output path.")

    heightmap_preview_parser = subparsers.add_parser(
        "heightmap-preview",
        help="Render a first grayscale heightmap preview from a mask layout JSON.",
    )
    heightmap_preview_parser.add_argument("layout", type=Path, help="Mask layout JSON input path.")
    heightmap_preview_parser.add_argument("output", type=Path, help="Heightmap preview PNG output path.")
    heightmap_preview_parser.add_argument(
        "--mask",
        type=Path,
        help="Optional mask PNG override, useful for cleaned terrain inputs.",
    )

    validate_layout_parser = subparsers.add_parser(
        "validate-layout",
        help="Validate a mask layout JSON and optionally write a human-readable report.",
    )
    validate_layout_parser.add_argument("layout", type=Path, help="Mask layout JSON input path.")
    validate_layout_parser.add_argument("--report", type=Path, help="Optional report TXT output path.")

    build_location_parser = subparsers.add_parser(
        "build-location",
        help="Build a first TitanForge location pack folder from a mask or deterministic demo input.",
    )
    build_location_parser.add_argument("output_dir", type=Path, help="Location pack output folder.")
    source_group = build_location_parser.add_mutually_exclusive_group()
    source_group.add_argument("--input", type=Path, help="PNG mask to use as the location source.")
    source_group.add_argument("--demo", action="store_true", help="Generate a deterministic demo mask.")
    build_location_parser.add_argument("--width", type=int, default=128, help="Demo mask width.")
    build_location_parser.add_argument("--height", type=int, default=128, help="Demo mask height.")
    build_location_parser.add_argument(
        "--use-cleanup-for-heightmap",
        action="store_true",
        help="Render heightmap-preview.png from mask-cleanup-preview.png instead of mask.png.",
    )

    night_run_parser = subparsers.add_parser(
        "night-run",
        help="Run a resilient overnight batch of demo location-pack generations.",
    )
    night_run_parser.add_argument("output_dir", type=Path, help="Night run output folder.")
    night_run_parser.add_argument("--count", type=int, default=24, help="How many cases to attempt.")
    night_run_parser.add_argument("--width", type=int, default=128, help="Base demo mask width.")
    night_run_parser.add_argument("--height", type=int, default=128, help="Base demo mask height.")
    night_run_parser.add_argument("--size-step", type=int, default=32, help="Size increase for variant cases.")
    night_run_parser.add_argument("--max-minutes", type=float, help="Stop after this many minutes.")
    night_run_parser.add_argument(
        "--use-cleanup-for-heightmap",
        action="store_true",
        help="Use cleanup previews as heightmap source for every case.",
    )
    night_run_parser.add_argument(
        "--no-alternate-cleanup",
        action="store_true",
        help="Do not alternate cleanup/raw heightmap cases.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    try:
        return _dispatch(args, parser)
    except (
        CliUsageError,
        PngError,
        FileNotFoundError,
        NotADirectoryError,
        IsADirectoryError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.command == "info":
        print_info()
        return 0

    if args.command == "plan":
        config = load_project_config(args.config)
        print_project_plan(config)
        return 0

    if args.command == "inventory":
        report = scan_inventory(args.path)
        print(format_inventory_report(report))
        return 0

    if args.command == "mask-info":
        analysis = analyze_png_mask(args.path)
        print(format_mask_analysis(analysis))
        return 0

    if args.command == "demo-mask":
        _require_demo_size(args.width, args.height)
        result = generate_demo_mask(args.output, width=args.width, height=args.height)
        print(format_demo_mask_result(result))
        return 0

    if args.command == "mask-preview":
        result = render_mask_preview(args.input, args.output)
        print(format_mask_preview_result(result))
        return 0

    if args.command == "mask-cleanup-preview":
        if not 1 <= args.threshold <= 8:
            print(f"error: --threshold must be between 1 and 8, got {args.threshold}", file=sys.stderr)
            return 2
        result = render_mask_cleanup_preview(args.input, args.output, threshold=args.threshold)
        print(format_mask_cleanup_result(result))
        return 0

    if args.command == "mask-layout":
        result = write_mask_layout(args.input, args.output)
        print(format_mask_layout_result(result))
        return 0

    if args.command == "heightmap-preview":
        result = render_heightmap_preview(args.layout, args.output, mask_override_path=args.mask)
        print(format_heightmap_preview_result(result))
        return 0

    if args.command == "validate-layout":
        if args.report:
            result = write_layout_validation_report(args.layout, args.report)
        else:
            result = validate_layout_file(args.layout)
        print(format_layout_validation_report(result))
        return 1 if result.has_errors else 0

    if args.command == "build-location":
        if args.input is None:
            _require_demo_size(args.width, args.height)
        result = build_location_pack(
            args.output_dir,
            input_mask=args.input,
            demo=args.demo,
            width=args.width,
            height=args.height,
            use_cleanup_for_heightmap=args.use_cleanup_for_heightmap,
        )
        print(format_location_build_result(result))
        return 1 if result.errors else 0

    if args.command == "night-run":
        _require(args.count >= 1, f"--count must be at least 1, got {args.count}")
        _require_demo_size(args.width, args.height)
        _require(args.size_step >= 0, f"--size-step must be zero or positive, got {args.size_step}")
        _require(
            args.max_minutes is None or args.max_minutes > 0,
            f"--max-minutes must be positive, got {args.max_minutes}",
        )
        result = run_night_run(
            args.output_dir,
            count=args.count,
            width=args.width,
            height=args.height,
            size_step=args.size_step,
            max_minutes=args.max_minutes,
            use_cleanup_for_heightmap=args.use_cleanup_for_heightmap,
            alternate_cleanup=not args.no_alternate_cleanup,
        )
        print(format_night_run_result(result))
        return 1 if result.failed_cases else 0

    parser.print_help()
    return 0


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CliUsageError(message)


def _require_demo_size(width: int, height: int) -> None:
    _require(
        width >= DEMO_MASK_MIN_SIZE and height >= DEMO_MASK_MIN_SIZE,
        f"--width and --height must be at least {DEMO_MASK_MIN_SIZE}, got {width} x {height}",
    )


def print_info() -> None:
    print("TitanForge Engine")
    print(f"Primary target: {PRIMARY_TARGET.minecraft_version}")
    print("Active targets:")
    for target in ACTIVE_TARGETS:
        print(f"- {target.minecraft_version}: {target.role}")
    print("Parking lot:")
    for target in PARKING_LOT_TARGETS:
        print(f"- {target.minecraft_version}: {target.role}")


def print_project_plan(config: ProjectConfig) -> None:
    print(f"Project: {config.name}")
    print(f"Target: {config.target_version}")
    print(f"World size: {config.width} x {config.length}")
    print("Pipeline:")
    for stage in config.pipeline:
        print(f"- {stage}")
