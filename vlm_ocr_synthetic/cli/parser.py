"""Argument parsing: the shape of the CLI, and nothing else."""

from __future__ import annotations

import argparse

from ..dataset import DEFAULT_OUT_DIR as DATASET_OUT_DIR
from ..evaluation import DEFAULT_OUT_DIR
from ..renderers import renderer_names
from .commands import (
    _cmd_benchmark,
    _cmd_doctor,
    _cmd_generate,
    _cmd_list,
    _cmd_render,
)


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

    generate_parser = subparsers.add_parser(
        "generate",
        help="render a dataset by sampling the scenario space",
    )
    generate_parser.add_argument(
        "-c", "--config", default="configs/datasets/default.yaml", help="dataset config"
    )
    generate_parser.add_argument(
        "-o", "--out", default=str(DATASET_OUT_DIR), help="output directory"
    )
    generate_parser.add_argument("-n", "--pages", type=int, help="override pages")
    generate_parser.add_argument("--seed", type=int, help="override the master seed")
    generate_parser.add_argument("--scale", type=float, help="override scale")
    generate_parser.add_argument(
        "--mode", choices=["sample", "stratified"], help="override sampling mode"
    )
    generate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plan the run and print the realised distribution, render nothing",
    )
    generate_parser.add_argument("-q", "--quiet", action="store_true")
    generate_parser.set_defaults(func=_cmd_generate)

    return parser
