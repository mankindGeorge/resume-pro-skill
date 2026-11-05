# SPDX-License-Identifier: MIT
"""Career vault loading, validation, atomic saving, and merging."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator

from .errors import Issue, ValidationResult, VaultError
from .paths import schema_dir, vault_path

SCHEMA_VERSION = "1.0"
FACT_COLLECTIONS = (
    "education",
    "experience",
    "projects",
    "skills",
    "awards",
    "certificates",
    "languages",
    "publications",
)

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _schema() -> dict[str, Any]:
    if "vault" not in _SCHEMA_CACHE:
        path = schema_dir() / "vault.schema.json"
        try:
            _SCHEMA_CACHE["vault"] = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise VaultError(
                "schema.read_failed",
                f"Could not read {path}: {exc}",
                fix="Reinstall the package or set RESUME_PRO_SCHEMA_DIR.",
            ) from exc
    return _SCHEMA_CACHE["vault"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_vault() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "collecting",
        "updated_at": now_iso(),
        "identity": {},
        "education": [],
        "experience": [],
        "projects": [],
        "skills": [],
        "awards": [],
        "certificates": [],
        "languages": [],
        "publications": [],
        "evidence": {},
        "needs_confirmation": [],
    }


def _json_path(error_path: Any) -> str:
    out = ""
    for part in error_path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out


def _fix_for(error: Any) -> str:
    validator = error.validator
    if validator == "required":
        missing = str(error.message).split("'")[1] if "'" in str(error.message) else "the field"
        return f"Add the required field `{missing}`."
    if validator == "additionalProperties":
        return "Remove the unknown field, or add it to the schema first."
    if validator == "type":
        return f"Use the expected type: {error.validator_value}."
    if validator == "enum":
        return f"Use one of: {', '.join(map(str, error.validator_value))}."
    if validator in {"pattern", "format"}:
        return f"Use the expected format ({error.validator_value})."
    if validator == "minItems":
        return f"Provide at least {error.validator_value} item(s)."
    if validator == "minLength":
        return f"Provide at least {error.validator_value} character(s)."
    if validator == "const":
        return f"Use the fixed value {error.validator_value!r}."
    return "Fix the value to match schema/vault.schema.json."


def validate_vault(vault: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    validator = Draft202012Validator(_schema())
    for error in sorted(validator.iter_errors(vault), key=lambda e: list(e.path)):
        result.issues.append(
            Issue(
                code="vault.schema",
                path=_json_path(error.path),
                message=error.message,
                fix=_fix_for(error),
            )
        )

    # Referential integrity beyond JSON Schema.
    ids: dict[str, str] = {}
    for path, fact in iter_facts(vault):
        fact_id = fact.get("id")
        if not fact_id:
            continue
        if fact_id in ids:
            result.issues.append(
                Issue(
                    code="vault.duplicate_id",
                    path=f"{path}.id",
                    message=f"Duplicate id {fact_id!r}; already used at {ids[fact_id]}.",
                    fix="Assign a new stable id and update every reference to it.",
                )
            )
        else:
            ids[fact_id] = path
        for key in ("evidence",):
            for ref in fact.get(key, []) or []:
                if ref not in (vault.get("evidence") or {}):
                    result.issues.append(
                        Issue(
                            code="vault.missing_evidence",
                            path=f"{path}.{key}",
                            message=f"Evidence id {ref!r} is not in the evidence registry.",
                            fix="Add the evidence entry or remove the reference.",
                        )
                    )

    for path, bullet in iter_bullets(vault):
        bullet_id = bullet.get("id")
        if bullet_id in ids:
            result.issues.append(
                Issue(
                    code="vault.duplicate_id",
                    path=f"{path}.id",
                    message=f"Duplicate id {bullet_id!r}; already used at {ids[bullet_id]}.",
                    fix="Assign a new stable id.",
                )
            )
        elif bullet_id:
            ids[bullet_id] = f"{path}.id"
        refs = bullet.get("evidence") or []
        if not refs:
            result.issues.append(
                Issue(
                    code="vault.bullet_without_evidence",
                    path=f"{path}.evidence",
                    message="Every bullet must reference at least one evidence id.",
                    fix="Link an evidence entry; use status user_asserted when proof is unavailable.",
                )
            )
        for ref in refs:
            if ref not in (vault.get("evidence") or {}):
                result.issues.append(
                    Issue(
                        code="vault.missing_evidence",
                        path=f"{path}.evidence",
                        message=f"Evidence id {ref!r} is not in the evidence registry.",
                        fix="Add the evidence entry or remove the reference.",
                    )
                )

    summary_refs = (vault.get("identity") or {}).get("summary_evidence") or []
    for ref in summary_refs:
        if ref not in (vault.get("evidence") or {}):
            result.issues.append(
                Issue(
                    code="vault.missing_evidence",
                    path="identity.summary_evidence",
                    message=f"Evidence id {ref!r} is not in the evidence registry.",
                    fix="Add the evidence entry or remove the reference.",
                )
            )

    evidence = vault.get("evidence") or {}
    for key, entry in evidence.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("id") != key:
            result.issues.append(
                Issue(
                    code="vault.evidence_id_mismatch",
                    path=f"evidence.{key}.id",
                    message=f"Evidence key {key!r} does not match its id {entry.get('id')!r}.",
                    fix="Make the key and the id identical.",
                )
            )
    return result


def iter_facts(vault: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for collection in FACT_COLLECTIONS:
        for index, fact in enumerate(vault.get(collection) or []):
            if isinstance(fact, dict):
                yield f"{collection}[{index}]", fact


def iter_bullets(vault: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for collection in ("experience", "projects"):
        for index, fact in enumerate(vault.get(collection) or []):
            for b_index, bullet in enumerate(fact.get("bullets") or []):
                if isinstance(bullet, dict):
                    yield f"{collection}[{index}].bullets[{b_index}]", bullet


def load_vault(
    path: Path | str | None = None,
    *,
    root: Path | None = None,
    validate: bool | None = None,
) -> dict[str, Any]:
    if path is None:
        if root is None:
            raise ValueError("load_vault needs a path or a root")
        path = vault_path(root)
    path = Path(path)
    if not path.is_file():
        raise VaultError(
            "vault.not_found",
            f"No vault at {path}.",
            fix="Run `resume init` to create one.",
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise VaultError(
            "vault.invalid_yaml",
            f"Could not parse {path}: {exc}",
            path=str(path),
            fix="Fix the YAML syntax or restore the previous version.",
        ) from exc
    if raw is None:
        raw = empty_vault()
    if not isinstance(raw, dict):
        raise VaultError(
            "vault.invalid_root",
            "The vault root must be a mapping.",
            path=str(path),
            fix="Start from `resume init` and keep the top level as key: value pairs.",
        )
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise VaultError(
            "vault.unsupported_version",
            f"Unsupported vault schema_version {version!r}; this build reads {SCHEMA_VERSION!r}.",
            path=str(path),
            fix="Run a migration, or restore the vault from a version that matches this build.",
        )

    should_validate = validate
    if should_validate is None:
        should_validate = raw.get("status") != "collecting"
    if should_validate:
        result = validate_vault(raw)
        if not result.ok:
            first = result.errors[0]
            raise VaultError(
                "vault.invalid",
                f"{len(result.errors)} validation error(s); first: {first.message}",
                path=first.path,
                fix=first.fix,
                details=result.to_dict(),
            )
    return raw


def save_vault(
    vault: dict[str, Any],
    path: Path | str | None = None,
    *,
    root: Path | None = None,
    validate: bool = True,
) -> Path:
    if path is None:
        if root is None:
            raise ValueError("save_vault needs a path or a root")
        path = vault_path(root)
    path = Path(path)
    data = copy.deepcopy(vault)
    data["updated_at"] = now_iso()
    if validate and data.get("status") != "collecting":
        result = validate_vault(data)
        if not result.ok:
            first = result.errors[0]
            raise VaultError(
                "vault.invalid",
                f"Cannot save invalid vault; first: {first.message}",
                path=first.path,
                fix=first.fix,
                details=result.to_dict(),
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    fd, tmp_name = tempfile.mkstemp(prefix=".vault-", suffix=".yaml.tmp", dir=str(path.parent))
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
    vault.clear()
    vault.update(data)
    return path


def vault_fingerprint(vault: dict[str, Any]) -> str:
    canonical = json.dumps(vault, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_ids(vault: dict[str, Any]) -> None:
    """Assign stable ids to entries created incrementally by intake or import."""
    prefixes = {
        "education": "edu",
        "experience": "exp",
        "projects": "proj",
        "skills": "skl",
        "awards": "awd",
        "certificates": "cert",
        "languages": "lang",
        "publications": "pub",
    }
    for collection, prefix in prefixes.items():
        for item in vault.get(collection) or []:
            if isinstance(item, dict) and not item.get("id"):
                item["id"] = next_id(vault, prefix)
    for collection in ("experience", "projects"):
        for item in vault.get(collection) or []:
            if not isinstance(item, dict):
                continue
            parent_id = item.get("id")
            for index, bullet in enumerate(item.get("bullets") or []):
                if isinstance(bullet, dict) and not bullet.get("id"):
                    bullet["id"] = f"bul_{parent_id}_{index + 1}"


def next_id(vault: dict[str, Any], prefix: str) -> str:
    used: set[str] = set()
    for _, fact in iter_facts(vault):
        if fact.get("id"):
            used.add(fact["id"])
    for _, bullet in iter_bullets(vault):
        if bullet.get("id"):
            used.add(bullet["id"])
    used.update((vault.get("evidence") or {}).keys())
    number = 1
    while f"{prefix}_{number:03d}" in used:
        number += 1
    return f"{prefix}_{number:03d}"


def _norm(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("en") or value.get("zh") or ""
    return " ".join(str(value or "").lower().split())


def _entity_key(collection: str, item: dict[str, Any], lang: str = "en") -> tuple:
    if collection == "education":
        return (_norm(item.get("school")), _norm(item.get("degree")), item.get("start"))
    if collection == "experience":
        return (_norm(item.get("company")), _norm(item.get("title")), item.get("start"))
    if collection == "projects":
        return (_norm(item.get("name")), item.get("start"))
    if collection == "awards":
        return (_norm(item.get("title")), _norm(item.get("issuer")))
    if collection == "certificates":
        return (_norm(item.get("name")), _norm(item.get("issuer")))
    if collection == "languages":
        return (_norm(item.get("name")),)
    if collection == "publications":
        return (_norm(item.get("title")), _norm(item.get("venue")))
    if collection == "skills":
        return (_norm(item.get("name")), item.get("kind"))
    return (json.dumps(item, sort_keys=True, ensure_ascii=False),)


def _merge_missing(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key not in target or target[key] in (None, "", [], {}):
            target[key] = copy.deepcopy(value)
        elif isinstance(target[key], dict) and isinstance(value, dict):
            _merge_missing(target[key], value)
        elif isinstance(target[key], list) and isinstance(value, list):
            if key == "bullets":
                _merge_bullets(target, value)
            else:
                for entry in value:
                    if entry not in target[key]:
                        target[key].append(copy.deepcopy(entry))


def _merge_bullets(target: dict[str, Any], incoming: list[dict[str, Any]]) -> None:
    existing = target.setdefault("bullets", [])
    by_id = {b.get("id"): b for b in existing if b.get("id")}
    by_text = {_norm(b.get("text")): b for b in existing}
    for bullet in incoming:
        if not isinstance(bullet, dict):
            continue
        found = by_id.get(bullet.get("id")) or by_text.get(_norm(bullet.get("text")))
        if found:
            _merge_missing(found, bullet)
        else:
            existing.append(copy.deepcopy(bullet))


def _all_ids(vault: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for _, fact in iter_facts(vault):
        if fact.get("id"):
            ids.add(fact["id"])
    for _, bullet in iter_bullets(vault):
        if bullet.get("id"):
            ids.add(bullet["id"])
    ids.update((vault.get("evidence") or {}).keys())
    return ids


def _allocate(prefix: str, used: set[str]) -> str:
    number = 1
    while f"{prefix}_{number:03d}" in used:
        number += 1
    value = f"{prefix}_{number:03d}"
    used.add(value)
    return value


def _remap_refs(value: Any, evidence_map: dict[str, str], skill_map: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"evidence", "summary_evidence"} and isinstance(item, list):
                value[key] = [evidence_map.get(ref, ref) for ref in item]
            elif key == "skill_ids" and isinstance(item, list):
                value[key] = [skill_map.get(ref, ref) for ref in item]
            else:
                _remap_refs(item, evidence_map, skill_map)
    elif isinstance(value, list):
        for item in value:
            _remap_refs(item, evidence_map, skill_map)


_COLLECTION_PREFIX = {
    "education": "edu",
    "experience": "exp",
    "projects": "proj",
    "skills": "skl",
    "awards": "awd",
    "certificates": "cert",
    "languages": "lang",
    "publications": "pub",
}


def _merge_evidence(
    merged: dict[str, Any], incoming: dict[str, Any]
) -> dict[str, str]:
    evidence = merged.setdefault("evidence", {})
    mapping: dict[str, str] = {}
    for key, entry in incoming.items():
        if not isinstance(entry, dict):
            continue
        if key not in evidence:
            evidence[key] = copy.deepcopy(entry)
            mapping[key] = key
        elif _norm(evidence[key].get("claim")) == _norm(entry.get("claim")):
            _merge_missing(evidence[key], entry)
            mapping[key] = key
        else:
            new_key = next_id(merged, "ev")
            new_entry = copy.deepcopy(entry)
            new_entry["id"] = new_key
            evidence[new_key] = new_entry
            mapping[key] = new_key
    return mapping


def _plan_skill_ids(merged: dict[str, Any], incoming: list[dict[str, Any]]) -> dict[str, str]:
    used = _all_ids(merged)
    existing = {item.get("id"): _entity_key("skills", item) for item in merged.get("skills") or []}
    mapping: dict[str, str] = {}
    for item in incoming:
        old_id = item.get("id")
        if not old_id:
            continue
        key = _entity_key("skills", item)
        if old_id in existing and existing[old_id] != key:
            mapping[old_id] = _allocate("skl", used)
    return mapping


def merge_vaults(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge two vaults without inventing facts or losing conflicting entries.

    Matching entries merge. Conflicting ids are reassigned and all references
    (bullets, evidence, skill ids) are remapped so two resumes can coexist.
    """
    merged = copy.deepcopy(base)
    merged.setdefault("identity", {})

    evidence_map = _merge_evidence(merged, incoming.get("evidence") or {})
    skill_map = _plan_skill_ids(merged, incoming.get("skills") or [])

    incoming_identity = copy.deepcopy(incoming.get("identity") or {})
    _remap_refs(incoming_identity, evidence_map, skill_map)
    _merge_missing(merged["identity"], incoming_identity)

    if incoming.get("preferences"):
        merged.setdefault("preferences", {})
        _merge_missing(merged["preferences"], incoming["preferences"])

    for collection in FACT_COLLECTIONS:
        target_items = merged.setdefault(collection, [])
        index = {_entity_key(collection, item): item for item in target_items}
        for item in incoming.get(collection) or []:
            if not isinstance(item, dict):
                continue
            key = _entity_key(collection, item)
            found = index.get(key)
            incoming_item = copy.deepcopy(item)
            old_id = incoming_item.get("id")
            if collection == "skills" and old_id in skill_map:
                incoming_item["id"] = skill_map[old_id]
            _remap_refs(incoming_item, evidence_map, skill_map)
            if found:
                _merge_missing(found, incoming_item)
                continue

            new_id = incoming_item.get("id") or _allocate(_COLLECTION_PREFIX[collection], _all_ids(merged))
            if any(existing.get("id") == new_id for existing in target_items):
                new_id = _allocate(_COLLECTION_PREFIX[collection], _all_ids(merged))
            incoming_item["id"] = new_id
            if collection in {"experience", "projects"} and new_id != old_id:
                for bullet_index, bullet in enumerate(incoming_item.get("bullets") or []):
                    bullet["id"] = f"bul_{new_id}_{bullet_index + 1}"
            target_items.append(incoming_item)
            index[key] = incoming_item

    confirmations = merged.setdefault("needs_confirmation", [])
    seen = {(c.get("path"), c.get("question")) for c in confirmations}
    for item in incoming.get("needs_confirmation") or []:
        marker = (item.get("path"), item.get("question"))
        if marker not in seen:
            confirmations.append(copy.deepcopy(item))
            seen.add(marker)

    if merged.get("status") != "collecting" and incoming.get("status") == "collecting":
        merged["status"] = "collecting"
    merged["updated_at"] = now_iso()
    return merged
