"""What a dataset run is: how many pages, sampled how, written where.

Weights live here too, but only as data -- the variants they refer to are
declared in :mod:`vlm_ocr_synthetic.variations`."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from ..variations import ScenarioSpace, default_space

DEFAULT_OUT_DIR = Path("data/dataset")


class DatasetConfig(BaseModel):
    """A run: how many pages, sampled how, written where."""

    model_config = {"extra": "forbid"}

    pages: int = 100
    seed: int = 0
    scale: float = 1.0
    mode: str = "sample"  # "sample" | "stratified"

    # Each rendered page is aged this many ways. The structural render is
    # shared, so extra variants are nearly free.
    degradations_per_page: int = 1

    image_format: str = "png"  # "png" (lossless) | "jpeg" (small)
    jpeg_quality: int = 88

    # {axis: {variant: weight}} -- the only thing you normally edit.
    axes: dict[str, dict[str, float]] = {}


def load_dataset_config(path: str | Path) -> DatasetConfig:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: dataset config must be a mapping")
    return DatasetConfig(**data)


def build_space(config: DatasetConfig, space: ScenarioSpace | None = None):
    """Apply the config's weights to the space; unknown names raise."""
    return (space or default_space()).with_weights(config.axes)
