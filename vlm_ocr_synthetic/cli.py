"""Command line entry point.

    python -m vlm_ocr_synthetic doctor                     # is this environment usable?
    python -m vlm_ocr_synthetic benchmark --pages 3        # compare the backends
    python -m vlm_ocr_synthetic list                       # backend status
    python -m vlm_ocr_synthetic render --renderer all      # side-by-side check
    python -m vlm_ocr_synthetic render -r html --config configs/html_flow.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .benchmark import DEFAULT_OUT_DIR, format_markdown, run_benchmark, save_report
from .compat import environment_report, problems
from .renderers import (
    RendererUnavailable,
    available_renderers,
    get_renderer,
    load_config,
    renderer_names,
)
from .samples import get_sample, sample_names
from .schemas.document import Document


def _load_document(path: Optional[str], sample: str) -> Document:
    if path:
        return Document.model_validate_json(Path(path).read_text(encoding="utf-8"))
    return get_sample(sample)


def _cmd_list(args: argparse.Namespace) -> int:
    status = available_renderers()
    if args.json:
        print(json.dumps(status, indent=2))
        return 0

    print("renderers:")
    for name, reason in status.items():
        mark = "ok" if reason is None else "unavailable"
        print(f"  {name:<10} {mark}{'' if reason is None else f' -- {reason}'}")
    print(f"samples: {', '.join(sample_names())}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    report = environment_report()

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if not problems() else 1

    python = report["python"]
    print(f"python      {python['version']} ({python['implementation']})")
    print(f"            {python['executable']}")

    imaging = report["imaging"]
    if imaging["available"]:
        print(
            f"imaging     Pillow {imaging['pillow']} "
            f"(freetype {imaging['freetype']}, raqm {imaging['raqm'] or 'missing'})"
        )
    else:
        print(f"imaging     unavailable -- {imaging['reason']}")

    print("renderers")
    for name, reason in report["renderers"].items():
        print(f"  {name:<10} {'ok' if reason is None else f'unavailable -- {reason}'}")

    print("dependencies")
    for entry in report["dependencies"]:
        installed = entry["installed"] or "-"
        required = f">= {entry['required']}" if entry["required"] else "any"
        print(
            f"  {entry['distribution']:<12} {installed:<10} {required:<12}"
            f" {entry['status']}"
        )

    issues = problems()
    if issues:
        print("\nproblems:")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print("\nno problems found")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    document = _load_document(args.document, args.sample)

    if args.config:
        config_name, options = load_config(args.config)
        targets = [config_name] if args.renderer is None else _expand(args.renderer)
    else:
        options = {}
        targets = _expand(args.renderer or "all")

    if args.scale is not None:
        options = {**options, "scale": args.scale}
    if args.no_paper:
        # Stage one only: the structure on a clean sheet.
        options = {**options, "paper": {"enabled": False}}

    out_root = Path(args.out)
    failures = 0

    for name in targets:
        try:
            renderer = get_renderer(name, options)
            result = renderer.render(document)
        except RendererUnavailable as exc:
            print(f"[skip] {name}: {exc}", file=sys.stderr)
            failures += 1
            continue

        image_path, annotation_path = result.save(out_root / name, args.stem)
        print(f"[ok] {name}: {image_path} ({result.image.size[0]}x{result.image.size[1]})")
        print(f"     {annotation_path}")

    return 1 if failures and args.strict else 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    options: dict[str, object] = {"scale": args.scale}
    if args.no_paper:
        options["paper"] = {"enabled": False}

    report = run_benchmark(
        pages=args.pages,
        sample=args.sample,
        options=options,
        backends=_expand(args.renderer or "all"),
        out_dir=args.out,
        save_images=not args.no_images,
    )

    json_path, markdown_path = save_report(report, args.out)
    print(format_markdown(report))
    print(f"report: {markdown_path}")
    print(f"        {json_path}")
    if not args.no_images:
        print(f"images: {Path(args.out)}/<renderer>/page_*.png")

    return 1 if not report["backends"] else 0


def _expand(renderer: str) -> list[str]:
    return renderer_names() if renderer == "all" else [renderer]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vlm-ocr-synthetic",
        description="Render synthetic document pages with pluggable backends.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="show backends and samples")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=_cmd_list)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="check the interpreter, dependencies and backends; non-zero on problems",
    )
    doctor_parser.add_argument("--json", action="store_true")
    doctor_parser.set_defaults(func=_cmd_doctor)

    render_parser = subparsers.add_parser("render", help="render one document")
    render_parser.add_argument(
        "-r",
        "--renderer",
        help=f"backend name or 'all' (default: all). One of: {', '.join(renderer_names())}",
    )
    render_parser.add_argument("-c", "--config", help="YAML/JSON renderer config")
    render_parser.add_argument("-d", "--document", help="path to a Document JSON file")
    render_parser.add_argument(
        "-s", "--sample", default="invoice", help="built-in sample document"
    )
    render_parser.add_argument(
        "-o", "--out", default="data", help="output directory (default: data)"
    )
    render_parser.add_argument("--stem", default="page", help="output file stem")
    render_parser.add_argument(
        "--no-paper",
        action="store_true",
        help="render the structure only, without the paper layer",
    )
    render_parser.add_argument("--scale", type=float, help="override config scale")
    render_parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when a backend is unavailable",
    )
    render_parser.set_defaults(func=_cmd_render)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="render the same pages through every backend and compare them",
    )
    benchmark_parser.add_argument("-n", "--pages", type=int, default=3)
    benchmark_parser.add_argument("-s", "--sample", default="invoice")
    benchmark_parser.add_argument(
        "-r", "--renderer", help="backend name or 'all' (default: all)"
    )
    benchmark_parser.add_argument(
        "-o", "--out", default=str(DEFAULT_OUT_DIR), help="output directory"
    )
    benchmark_parser.add_argument("--scale", type=float, default=1.0)
    benchmark_parser.add_argument(
        "--no-paper", action="store_true", help="measure without the paper layer"
    )
    benchmark_parser.add_argument(
        "--no-images", action="store_true", help="report only, write no pages"
    )
    benchmark_parser.set_defaults(func=_cmd_benchmark)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
