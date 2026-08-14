"""Screenshot engines for the html backend.

An engine takes an HTML string and gives back PNG bytes plus the on-page
geometry of every annotated element -- that geometry is what turns a web
page into OCR ground truth.  ``playwright`` is the reference engine; add
another by subclassing :class:`ScreenshotEngine` and registering it in
``ENGINES``.
"""

from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Boxes are keyed by the element's data-* id, values are CSS-pixel rects.
Boxes = dict[str, dict[str, float]]

CHROMIUM_ENV_VAR = "VLM_OCR_CHROMIUM_PATH"

# Pre-provisioned browsers found on common CI images.
CHROMIUM_CANDIDATES = (
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
)


def resolve_chromium_path(explicit: Optional[str] = None) -> Optional[str]:
    """Locate a chromium binary, or ``None`` to use playwright's own."""
    for candidate in (explicit, os.environ.get(CHROMIUM_ENV_VAR)):
        if candidate:
            if not Path(candidate).exists():
                raise FileNotFoundError(f"chromium not found: {candidate}")
            return candidate

    for candidate in CHROMIUM_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    for name in ("chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


class ScreenshotEngine(ABC):
    name: str = "base"

    @classmethod
    @abstractmethod
    def check_available(cls) -> Optional[str]:
        """``None`` when usable, else why not."""

    @abstractmethod
    def capture(
        self,
        html: str,
        page_width: int,
        page_height: int,
        scale: float,
        selectors: dict[str, str],
    ) -> tuple[bytes, dict[str, Boxes]]:
        """Return ``(png_bytes, {group: {element_id: rect}})``.

        ``selectors`` maps a group name (e.g. ``"blocks"``) to the
        ``data-*`` attribute whose values identify the elements to measure.
        """


class PlaywrightEngine(ScreenshotEngine):
    name = "playwright"

    def __init__(self, executable_path: Optional[str] = None, timeout_ms: int = 30_000):
        self.executable_path = executable_path
        self.timeout_ms = timeout_ms

    @classmethod
    def check_available(cls) -> Optional[str]:
        return _playwright_status()

    def capture(
        self,
        html: str,
        page_width: int,
        page_height: int,
        scale: float,
        selectors: dict[str, str],
    ) -> tuple[bytes, dict[str, Boxes]]:
        from playwright.sync_api import sync_playwright

        executable_path = resolve_chromium_path(self.executable_path)
        launch_kwargs = {"args": ["--font-render-hinting=none"]}
        if executable_path:
            launch_kwargs["executable_path"] = executable_path

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            try:
                page = browser.new_page(
                    viewport={"width": int(page_width), "height": int(page_height)},
                    device_scale_factor=scale,
                )
                page.set_default_timeout(self.timeout_ms)
                page.set_content(html, wait_until="load")
                page.wait_for_function("document.fonts.ready.then(() => true)")

                boxes = {
                    group: page.evaluate(_BOX_SCRIPT, attribute)
                    for group, attribute in selectors.items()
                }
                png = page.screenshot(type="png")
            finally:
                browser.close()

        return png, boxes


# Runs in the page: collect getBoundingClientRect() for every annotated node.
_BOX_SCRIPT = """
(attribute) => {
  const result = {};
  for (const node of document.querySelectorAll(`[${attribute}]`)) {
    const rect = node.getBoundingClientRect();
    result[node.getAttribute(attribute)] = {
      x1: rect.left + window.scrollX,
      y1: rect.top + window.scrollY,
      x2: rect.right + window.scrollX,
      y2: rect.bottom + window.scrollY,
    };
  }
  return result;
}
"""


@lru_cache(maxsize=1)
def _playwright_status() -> Optional[str]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "playwright is not installed (pip install '.[html]')"

    try:
        if resolve_chromium_path() is not None:
            return None
    except FileNotFoundError as exc:
        return str(exc)

    try:
        with sync_playwright() as playwright:
            bundled = playwright.chromium.executable_path
    except Exception as exc:  # driver missing / cannot start
        return f"playwright driver unusable: {exc}"

    if not Path(bundled).exists():
        return (
            "no chromium available; run 'playwright install chromium' "
            f"or set {CHROMIUM_ENV_VAR}"
        )
    return None


ENGINES: dict[str, type[ScreenshotEngine]] = {
    PlaywrightEngine.name: PlaywrightEngine,
}


def get_engine_class(name: str) -> type[ScreenshotEngine]:
    try:
        return ENGINES[name]
    except KeyError:
        raise KeyError(
            f"unknown screenshot engine '{name}'; available: {', '.join(sorted(ENGINES))}"
        ) from None
