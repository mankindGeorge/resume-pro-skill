# SPDX-License-Identifier: MIT
"""Render README preview thumbnails from the template previews."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "compact", "modern-sidebar", "editorial", "executive")
OUTPUT = ROOT / "docs" / "images" / "templates"
WIDTH = 794
HEIGHT = 1215
SCALE = 2
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def find_browser(explicit: str | None) -> str:
    candidates = [explicit, os.environ.get("RESUME_PRO_BROWSER")]
    candidates.extend(
        [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    )
    candidates.extend([shutil.which("msedge"), shutil.which("google-chrome"), shutil.which("chromium")])
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise SystemExit("No Edge/Chrome/Chromium found. Set RESUME_PRO_BROWSER or pass --browser.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", default=None, help="Path to Edge, Chrome, or Chromium.")
    args = parser.parse_args()
    browser = find_browser(args.browser)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for template_id in TEMPLATES:
        preview = ROOT / "templates" / "en" / template_id / "preview.html"
        if not preview.is_file():
            raise SystemExit(f"Missing preview: {preview}")
        target = OUTPUT / f"en-{template_id}.png"
        process = subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--force-device-scale-factor={SCALE}",
                f"--window-size={WIDTH},{HEIGHT}",
                f"--screenshot={target.resolve()}",
                preview.resolve().as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if process.returncode != 0 or not target.is_file():
            raise SystemExit(f"Failed to render {template_id}: {process.stderr.strip()}")
        if target.read_bytes()[:8] != PNG_MAGIC:
            raise SystemExit(f"Renderer did not produce a PNG for {template_id}")
        print(f"readme preview en/{template_id}: {target.relative_to(ROOT)} ({target.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
