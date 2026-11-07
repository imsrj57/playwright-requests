"""
Pixel-level visual regression for Playwright pages using Pillow.

    await check_visual_regression(base.page, name="home_page", threshold=100)

First run stores a baseline in `UIeye/baselines/<name>.png`; later runs diff
against it and fail if more than `threshold` pixels differ. Current, baseline
and diff images are attached to Allure.
"""

import io
from pathlib import Path

import allure
from PIL import Image, ImageChops

DEFAULT_BASELINE_DIR = "UIeye/baselines"


def _attach(img: Image.Image, name: str) -> None:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    allure.attach(buf.getvalue(), name=name, attachment_type=allure.attachment_type.PNG)


def count_diff_pixels(img1: Image.Image, img2: Image.Image) -> int:
    diff = ImageChops.difference(img1.convert("RGB"), img2.convert("RGB")).convert("L")
    return sum(diff.histogram()[1:])


async def check_visual_regression(page, name: str = "default", baseline_dir: str = DEFAULT_BASELINE_DIR,
                                  threshold: int = 100, full_page: bool = True, update_baseline: bool = False):
    baseline_dir_path = Path(baseline_dir)
    baseline_dir_path.mkdir(parents=True, exist_ok=True)
    baseline_path = baseline_dir_path / f"{name}.png"

    current = Image.open(io.BytesIO(await page.screenshot(full_page=full_page)))
    _attach(current, f"{name} - Current")

    if update_baseline or not baseline_path.exists():
        current.save(baseline_path)
        print(f"[visual] baseline saved: {baseline_path}")
        return

    baseline = Image.open(baseline_path)
    _attach(baseline, f"{name} - Baseline")

    if baseline.size != current.size:
        raise AssertionError(f"Visual regression '{name}': size changed {baseline.size} -> {current.size}")

    diff_pixels = count_diff_pixels(current, baseline)
    if diff_pixels > threshold:
        diff = ImageChops.difference(current.convert("RGB"), baseline.convert("RGB"))
        diff.save(baseline_dir_path / f"{name}_diff.png")
        _attach(diff, f"{name} - Diff")
        raise AssertionError(f"Visual regression '{name}': {diff_pixels} pixels differ (threshold {threshold})")
