# SPDX-License-Identifier: MIT
"""Run the CLI from an unzipped skill folder without installing the package."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from resume_pro.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
