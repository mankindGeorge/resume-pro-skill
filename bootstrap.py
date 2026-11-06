# SPDX-License-Identifier: MIT
"""Check or install the runtime required by an imported resume skill.

Run from the skill folder after unzipping the package:

    python bootstrap.py              # verify Python, dependencies, templates
    python bootstrap.py --install    # editable install: adds the `resume` command
    python bootstrap.py --deps-only  # dependencies only; keep using `python resume.py`
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
LAUNCHER = ROOT / "resume.py"
LIBRARY_IDS = (
    "ats-classic",
    "campus",
    "modern-sidebar",
    "editorial",
    "executive",
    "zh-professional",
)
DEPENDENCIES = (
    ("click", "click>=8.1"),
    ("yaml", "PyYAML>=6.0"),
    ("jsonschema", "jsonschema>=4.20"),
    ("docx", "python-docx>=1.1"),
    ("pdfplumber", "pdfplumber>=0.11"),
    ("bs4", "beautifulsoup4>=4.12"),
)


def missing_dependencies() -> list[str]:
    return [spec for module, spec in DEPENDENCIES if importlib.util.find_spec(module) is None]


def run_launcher(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(LAUNCHER), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def inspect_templates() -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "count": 0, "variants": [], "error": None}
    if not LAUNCHER.is_file():
        result["error"] = "resume.py is missing from the skill folder."
        return result
    process = run_launcher("templates", "--json")
    if process.returncode != 0:
        result["error"] = (process.stderr or process.stdout).strip() or "resume templates failed."
        return result
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        result["error"] = "resume templates did not return JSON."
        return result
    variants = [
        (item["id"], item["language"])
        for item in payload.get("templates", [])
        if item.get("folder") in {"cn", "en"} and "error" not in item
    ]
    result["variants"] = [f"{template_id}:{language}" for template_id, language in variants]
    result["count"] = len(variants)
    expected = {(template_id, language) for template_id in LIBRARY_IDS for language in ("zh", "en")}
    if set(variants) != expected:
        missing = sorted(expected - set(variants))
        extra = sorted(set(variants) - expected)
        result["error"] = f"Library variants mismatch. Missing={missing} Unexpected={extra}"
        return result
    result["ok"] = True
    return result


def check() -> dict[str, Any]:
    python_ok = python_supported()
    missing = missing_dependencies()
    templates = {"ok": False, "count": 0, "variants": [], "error": None}
    errors: list[str] = []
    if not python_ok:
        errors.append(f"Python 3.10+ is required; found {sys.version.split()[0]}.")
    if missing:
        errors.append("Missing dependencies: " + ", ".join(missing))
    if python_ok and not missing:
        templates = inspect_templates()
        if not templates["ok"]:
            errors.append(templates["error"] or "Template check failed.")
    return {
        "ok": python_ok and not missing and templates["ok"],
        "python": sys.version.split()[0],
        "python_ok": python_ok,
        "missing_dependencies": missing,
        "library_templates": templates["count"],
        "template_variants": templates["variants"],
        "launcher": f"{Path(sys.executable).name} resume.py",
        "console": "resume",
        "errors": errors,
    }


def python_supported() -> bool:
    return sys.version_info >= (3, 10)


def install(*, editable: bool) -> tuple[bool, str]:
    if not python_supported():
        return False, "Python 3.10+ is required."
    if editable:
        command = [sys.executable, "-m", "pip", "install", "-e", str(ROOT)]
    else:
        command = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=900)
    if process.returncode == 0:
        return True, process.stdout.strip()
    return False, (process.stderr or process.stdout).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the runtime (default).")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Editable install; adds the `resume` command and installs dependencies.",
    )
    parser.add_argument(
        "--deps-only",
        action="store_true",
        help="Install requirements.txt only; keep calling `python resume.py`.",
    )
    parser.add_argument("--json", dest="json_flag", action="store_true", help="Emit one JSON object.")
    args = parser.parse_args()
    if args.install and args.deps_only:
        parser.error("choose either --install or --deps-only")

    install_message = ""
    installed = True
    mode = "check"
    if args.install or args.deps_only:
        mode = "install" if args.install else "deps-only"
        installed, install_message = install(editable=args.install)
        if not installed:
            report = check()
            report.update({"ok": False, "mode": mode, "install_error": install_message})
            if args.json_flag:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print("Installation failed.")
                print(install_message)
                print("See docs/install.md for manual setup.")
            return 1

    report = check()
    report["mode"] = mode
    if args.json_flag:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Resume Pro Skill runtime check")
        print(f"  Python {report['python']}: {'OK' if report['python_ok'] else 'FAIL'}")
        deps = "OK" if not report["missing_dependencies"] else "missing " + ", ".join(report["missing_dependencies"])
        print(f"  Dependencies: {deps}")
        print(f"  Library templates: {report['library_templates']} variants")
        if report["errors"]:
            for error in report["errors"]:
                print(f"  error: {error}")
        if report["ok"]:
            print("  Run: python resume.py --help")
            if mode == "install":
                print("  Console command: resume")
            else:
                print("  Optional console command: python bootstrap.py --install")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
