"""One function per subcommand: read args, do the work, print, return a code.

Kept apart from the parser so a command can be called directly from Python
or from a test without going through argparse.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..compat import environment_report, problems
from ..dataset import (
    dry_run,
    format_distribution,
    generate,
    load_dataset_config,
)
from ..evaluation import format_markdown, run_benchmark, save_report
from ..renderers import (
    RendererUnavailable,
    available_renderers,
    get_renderer,
    load_config,
    renderer_names,
)
from ..samples import get_sample, sample_names
from ..schemas.document import Document


def expand(renderer: str) -> list[str]:
    return renderer_names() if renderer == "all" else [renderer]


def _load_document(path: str | None, sample: str) -> Document:
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
        targets = [config_name] if args.renderer is None else expand(args.renderer)
    else:
        options = {}
        targets = expand(args.renderer or "all")

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
        print(
            f"[ok] {name}: {image_path} ({result.image.size[0]}x{result.image.size[1]})"
        )
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
        backends=expand(args.renderer or "all"),
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


def _cmd_generate(args: argparse.Namespace) -> int:
    config = load_dataset_config(args.config)
    if args.pages is not None:
        config = config.model_copy(update={"pages": args.pages})
    if args.seed is not None:
        config = config.model_copy(update={"seed": args.seed})
    if args.scale is not None:
        config = config.model_copy(update={"scale": args.scale})
    if args.mode is not None:
        config = config.model_copy(update={"mode": args.mode})

    if args.dry_run:
        print(format_distribution(dry_run(config)))
        print("\n(dry run: nothing was rendered)")
        return 0

    written = 0

    def progress(count: int, scenario) -> None:
        nonlocal written
        written = count
        if args.quiet or count % 25:
            return
        print(f"  {count} images", file=sys.stderr)

    report = generate(config, out_dir=args.out, progress=progress)
    print(format_distribution(report))
    print(f"\nmanifest: {report['manifest']}")
    print(f"summary:  {Path(args.out) / 'summary.json'}")
    return 1 if report["images"] == 0 else 0
