# SPDX-License-Identifier: MIT
"""Per-application model: create, load, save, and validate application.yaml."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from . import profile
from .errors import ResumeProError, ValidationResult, Issue
from .paths import resume_dir, schema_dir
from .vault import vault_fingerprint

LIBRARY_TEMPLATES = (
    "ats-classic",
    "campus",
    "compact",
    "modern-sidebar",
    "editorial",
    "executive",
)

_SCHEMA_CACHE: dict[str, Any] = {}


class ApplicationError(ResumeProError):
    pass


def _schema() -> dict[str, Any]:
    if "application" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["application"] = json.loads(
            (schema_dir() / "application.schema.json").read_text(encoding="utf-8")
        )
    return _SCHEMA_CACHE["application"]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = "application"
    if any(ord(ch) > 127 for ch in value) or slug in {"application", "target"}:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug}-{digest}" if slug not in {"application"} else f"application-{digest}"
    return slug[:60]


def filename_role(role: str) -> str:
    value = re.sub(r"[^\w一-鿿-]+", "-", str(role or "").strip().lower(), flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:48]


def default_template(market: str, persona: str) -> str:
    if market.startswith("cn_"):
        return "campus" if profile.is_student(persona) else "modern-sidebar"
    if persona == "senior_manager":
        return "executive"
    return "ats-classic"


def page_budget(market: str, persona: str) -> dict[str, Any]:
    market_profile = profile.load_market(market)
    page = market_profile.get("page") or {}
    size = page.get("size", "a4" if market == "cn_internet" else "letter")
    if persona == "senior_manager":
        maximum = int(page.get("senior_max_pages", 2))
        target = min(2, maximum)
    elif profile.is_student(persona):
        maximum = int(page.get("student_max_pages", page.get("early_career_max_pages", 2)))
        target = 1
    else:
        maximum = int(page.get("experienced_max_pages", page.get("default_max_pages", 2)))
        target = min(2, maximum)
    return {"size": size, "target": max(1, target), "max": max(1, maximum)}


def validate_application(application: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    validator = Draft202012Validator(_schema())
    for error in sorted(validator.iter_errors(application), key=lambda e: list(e.path)):
        path = ".".join(str(part) for part in error.path)
        result.issues.append(
            Issue(
                code="application.schema",
                path=path,
                message=error.message,
                fix="Fix the value to match schema/application.schema.json.",
            )
        )
    if not result.ok:
        return result
    if application["page_budget"]["target"] > application["page_budget"]["max"]:
        result.issues.append(
            Issue(
                code="application.page_budget",
                path="page_budget.target",
                message="The target page count is greater than the maximum.",
                fix="Lower the target or raise the maximum.",
            )
        )
    if not application["writing"].get("consent"):
        result.issues.append(
            Issue(
                code="application.consent",
                path="writing.consent",
                message="Writing framework consent is required.",
                fix="Ask the user to choose a framework; never apply one silently.",
            )
        )
    return result


def create_application(
    *,
    vault: dict[str, Any],
    selection: dict[str, Any],
    role: str,
    market: str,
    persona: str,
    framework: str,
    company: str | None = None,
    template_id: str | None = None,
    slug: str | None = None,
    target_url: str | None = None,
    jd_path: str | None = None,
    role_in_filename: bool | None = None,
    allow_unknown_template: bool = False,
) -> dict[str, Any]:
    template_id = template_id or default_template(market, persona)
    if not allow_unknown_template and template_id not in LIBRARY_TEMPLATES and not template_id.startswith("user-"):
        raise ApplicationError(
            "application.template_unknown",
            f"Unknown template id {template_id!r}.",
            fix="Use one of: " + ", ".join(LIBRARY_TEMPLATES) + ", or a learned user-* template.",
        )
    slug = slug or slugify(f"{company or 'target'}-{role}")
    budget = page_budget(market, persona)
    mode = (vault.get("preferences") or {}).get("application_mode") or "unknown"
    if role_in_filename is None:
        role_in_filename = mode != "mass"
    role_slug = filename_role(role) if role_in_filename else ""
    html_name = f"resume-{role_slug}.html" if role_slug else "resume.html"
    editable_name = f"resume-{role_slug}-editable.html" if role_slug else "resume-editable.html"
    application = {
        "schema_version": "1.0",
        "slug": slug,
        "created_at": _now(),
        "vault_fingerprint": vault_fingerprint(vault),
        "target": {
            "role": role,
            **({"company": company} if company else {}),
            **({"url": target_url} if target_url else {}),
            **({"jd_path": jd_path} if jd_path else {}),
        },
        "market": market,
        "persona": persona,
        "template": {
            "id": template_id,
            "variant": "locked",
            "source": "user_learned" if template_id.startswith("user-") else "library",
        },
        "page_budget": budget,
        "selection": selection,
        "writing": {
            "framework": framework,
            "consent": True,
            "consent_at": _now(),
            "voice": "first_person_implied",
            "locale": "zh" if market.startswith("cn_") else "en",
        },
        "output": {
            "dir": f".resume/applications/{slug}",
            "html": html_name,
            "editable_html": editable_name,
            "draft": False,
        },
        "qa": {"status": "not_run"},
    }
    result = validate_application(application)
    if not result.ok:
        first = result.errors[0]
        raise ApplicationError(
            "application.invalid",
            f"Application is invalid: {first.message}",
            path=first.path,
            fix=first.fix,
            details=result.to_dict(),
        )
    return application


def application_dir(root: Path, slug: str) -> Path:
    return resume_dir(root) / "applications" / slug


def application_path(root: Path, slug: str) -> Path:
    return application_dir(root, slug) / "application.yaml"


def save_application(root: Path, application: dict[str, Any]) -> Path:
    result = validate_application(application)
    if not result.ok:
        first = result.errors[0]
        raise ApplicationError(
            "application.invalid",
            f"Cannot save invalid application: {first.message}",
            path=first.path,
            fix=first.fix,
            details=result.to_dict(),
        )
    directory = application_dir(root, application["slug"])
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "application.yaml"
    payload = yaml.safe_dump(application, allow_unicode=True, sort_keys=False, default_flow_style=False)
    fd, tmp_name = tempfile.mkstemp(prefix=".application-", suffix=".yaml.tmp", dir=str(directory))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def load_application(root: Path, slug: str) -> dict[str, Any]:
    path = application_path(root, slug)
    if not path.is_file():
        raise ApplicationError(
            "application.not_found",
            f"No application named {slug!r}.",
            path=str(path),
            fix="Run `resume new` or `resume tailor` first.",
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ApplicationError(
            "application.invalid_yaml",
            f"Could not parse {path}: {exc}",
            fix="Fix the YAML or recreate the application.",
        ) from exc
    result = validate_application(data)
    if not result.ok:
        first = result.errors[0]
        raise ApplicationError(
            "application.invalid",
            f"Application is invalid: {first.message}",
            path=first.path,
            fix=first.fix,
            details=result.to_dict(),
        )
    return data


def list_applications(root: Path) -> list[dict[str, Any]]:
    directory = resume_dir(root) / "applications"
    if not directory.is_dir():
        return []
    items = []
    for path in sorted(directory.glob("*/application.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            items.append(
                {
                    "slug": data.get("slug"),
                    "role": (data.get("target") or {}).get("role"),
                    "company": (data.get("target") or {}).get("company"),
                    "market": data.get("market"),
                    "template": (data.get("template") or {}).get("id"),
                    "path": str(path),
                }
            )
    return items


def application_fingerprint(application: dict[str, Any]) -> str:
    canonical = json.dumps(application, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
