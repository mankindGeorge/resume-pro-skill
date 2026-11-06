# SPDX-License-Identifier: MIT
"""Build a private-safe, importable skill ZIP and verify the extracted copy.

The archive always contains a single top-level ``resume-pro-skill/`` folder.
Private review material, learned templates, local workspaces, VCS metadata,
caches, and secret-like files are excluded even when present on disk.

    python scripts/package_skill.py
    python scripts/package_skill.py --output dist/skill.zip --json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "resume-pro-skill"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
LIBRARY_IDS = (
    "ats-classic",
    "campus",
    "modern-sidebar",
    "editorial",
    "executive",
)
TEMPLATE_FILES = ("manifest.json", "template.html", "styles.css", "preview.html")

TOP_FILES = (
    "ATTRIBUTIONS.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "MANIFEST.in",
    "README.en.md",
    "README.md",
    "SKILL.md",
    "bootstrap.py",
    "pyproject.toml",
    "requirements.txt",
    "resume.py",
)

TREES = {
    "src": ("*.py",),
    "schema": ("*.json", "*.md", "*.yaml"),
    "profiles": ("*.yaml", "*.md"),
    "references": ("*.md",),
    "templates": ("*.html", "*.css", "*.json", "*.md"),
    "docs": ("*.md",),
    "scripts": ("*.py",),
}

TEST_TREE = ("tests", ("*.py", "*.sha256"))

PRIVATE_PARTS = {
    ".git",
    ".resume",
    "applications",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "dist",
    "build",
    "node_modules",
    ".idea",
    ".vscode",
    "designs",
}
PRIVATE_PREFIXES = ("docs/local/", "templates/user-", "tests/private/")
PRIVATE_NAMES = {".env", ".env.local", "credentials.json", "id_rsa", "id_ed25519"}
PRIVATE_SUFFIXES = (".local.json", ".local.html", ".pem", ".key")

REQUIRED = (
    "SKILL.md",
    "LICENSE",
    "ATTRIBUTIONS.md",
    "README.md",
    "README.en.md",
    "pyproject.toml",
    "requirements.txt",
    "bootstrap.py",
    "resume.py",
    "src/resume_pro/cli.py",
    "src/resume_pro/render.py",
    "schema/vault.schema.json",
    "schema/application.schema.json",
    "schema/template.schema.json",
    "profiles/markets/intl_en.yaml",
    "profiles/markets/cn_internet.yaml",
    "docs/install.md",
    "docs/quickstart.md",
    "docs/template-contracts.md",
    "docs/open-source-policy.md",
)


def version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else "0.0.0"


def is_private(relative: str) -> bool:
    path = Path(relative)
    if any(part.startswith(".") for part in path.parts):
        return True
    if any(part in PRIVATE_PARTS for part in path.parts):
        return True
    if any(relative.startswith(prefix) for prefix in PRIVATE_PREFIXES):
        return True
    if path.name in PRIVATE_NAMES:
        return True
    return any(path.name.endswith(suffix) for suffix in PRIVATE_SUFFIXES)


def collect(*, include_tests: bool) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []
    for name in TOP_FILES:
        path = ROOT / name
        if path.is_file() and not path.is_symlink():
            entries.append((path, name))
    trees = dict(TREES)
    if include_tests:
        trees[TEST_TREE[0]] = TEST_TREE[1]
    for top, patterns in trees.items():
        base = ROOT / top
        if not base.is_dir():
            continue
        for pattern in patterns:
            for path in sorted(base.rglob(pattern)):
                if not path.is_file() or path.is_symlink():
                    continue
                relative = path.relative_to(ROOT).as_posix()
                if is_private(relative):
                    continue
                entries.append((path, relative))
    unique: dict[str, Path] = {relative: path for path, relative in entries}
    return [(unique[name], name) for name in sorted(unique)]


def required_paths() -> list[str]:
    required = list(REQUIRED)
    for folder in ("cn", "en"):
        for template_id in LIBRARY_IDS:
            for filename in TEMPLATE_FILES:
                required.append(f"templates/{folder}/{template_id}/{filename}")
    return required


def validate(entries: list[tuple[Path, str]]) -> list[str]:
    failures: list[str] = []
    available = {relative for _, relative in entries}
    for required in required_paths():
        if required not in available:
            failures.append(f"missing required file: {required}")
    for _, relative in entries:
        if is_private(relative):
            failures.append(f"private path included: {relative}")
        if relative.startswith("/") or ".." in Path(relative).parts:
            failures.append(f"unsafe path: {relative}")
    return failures


def write_archive(entries: list[tuple[Path, str]], output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path, relative in entries:
            info = zipfile.ZipInfo(f"{SKILL_NAME}/{relative}", date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def inspect_archive(output: Path) -> list[str]:
    failures: list[str] = []
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if not names:
            return ["archive is empty"]
        if any(not name.startswith(f"{SKILL_NAME}/") for name in names):
            failures.append("archive must contain one top-level skill folder")
        relative_names = [name.split("/", 1)[1] for name in names if name.startswith(f"{SKILL_NAME}/")]
        for name in relative_names:
            if is_private(name):
                failures.append(f"private path in archive: {name}")
        for required in required_paths():
            if required not in relative_names:
                failures.append(f"archive missing: {required}")
        if archive.testzip() is not None:
            failures.append("archive integrity check failed")
    return failures


def runtime_check(output: Path) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="resume-pro-skill-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(output) as archive:
            archive.extractall(target)
        skill_root = target / SKILL_NAME
        process = subprocess.run(
            [sys.executable, str(skill_root / "bootstrap.py"), "--check", "--json"],
            cwd=skill_root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if process.returncode != 0:
            return {"ok": False, "error": (process.stderr or process.stdout).strip()}
        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError:
            return {"ok": False, "error": "bootstrap check did not return JSON"}
        return {
            "ok": bool(payload.get("ok")),
            "templates": payload.get("library_templates", 0),
            "errors": payload.get("errors", []),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Archive path (default: dist/resume-pro-skill-<version>.zip).",
    )
    parser.add_argument("--include-tests", action="store_true", help="Also include the public test suite.")
    parser.add_argument(
        "--skip-runtime-check",
        action="store_true",
        help="Skip extracting and bootstrapping the archive (not recommended).",
    )
    parser.add_argument("--json", dest="json_flag", action="store_true", help="Emit one JSON object.")
    args = parser.parse_args()

    output = args.output or (ROOT / "dist" / f"{SKILL_NAME}-{version()}.zip")
    entries = collect(include_tests=args.include_tests)
    failures = validate(entries)
    if failures:
        report = {"ok": False, "archive": str(output), "failures": failures}
        if args.json_flag:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("SKILL PACKAGE: FAIL")
            for failure in failures:
                print(" -", failure)
        return 1

    digest = write_archive(entries, output)
    failures = inspect_archive(output)
    checked: dict[str, object] = {"skipped": True}
    if not failures and not args.skip_runtime_check:
        checked = runtime_check(output)
        if not checked.get("ok"):
            failures.append("extracted package failed the bootstrap check")
    if failures:
        output.unlink(missing_ok=True)
        report = {
            "ok": False,
            "archive": str(output),
            "failures": failures,
            "runtime_check": checked,
        }
        if args.json_flag:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("SKILL PACKAGE: FAIL")
            for failure in failures:
                print(" -", failure)
        return 1

    report = {
        "ok": True,
        "archive": str(output),
        "sha256": digest,
        "files": len(entries),
        "bytes": output.stat().st_size,
        "runtime_check": checked,
    }
    if args.json_flag:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("SKILL PACKAGE: PASS")
        print(f"  archive: {output}")
        print(f"  files: {len(entries)}")
        print(f"  bytes: {report['bytes']}")
        print(f"  sha256: {digest}")
        if checked.get("skipped"):
            print("  runtime check: SKIPPED")
        else:
            print(f"  runtime check: {checked.get('templates', 0)} library variants")
        print(f"  import: unzip into a skill folder, then run `python bootstrap.py` there")
    return 0


if __name__ == "__main__":
    sys.exit(main())
