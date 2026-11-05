# SPDX-License-Identifier: MIT
"""Template learning tests: manifests, privacy, previews, and original-file safety."""

from __future__ import annotations

import hashlib
import json

import pytest
from jsonschema import Draft202012Validator

from resume_pro.ingest import ingest_file
from resume_pro.paths import schema_dir
from resume_pro.template_audit import audit_template
from resume_pro.template_learn import LearnError, learn_template, load_learned_template
from tests.ingest_fixtures import BAD_HTML, TWO_COLUMN_HTML, write_html


def _manifest_schema():
    return json.loads((schema_dir() / "template.schema.json").read_text(encoding="utf-8"))


def test_learn_html_creates_valid_private_template(tmp_path):
    path = write_html(tmp_path / "resume.html")
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learned = learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")

    assert learned.directory.is_dir()
    assert (learned.directory / "template.html").is_file()
    assert (learned.directory / "styles.css").is_file()
    assert (learned.directory / "preview.html").is_file()
    manifest = json.loads(learned.manifest_path.read_text(encoding="utf-8"))
    Draft202012Validator(_manifest_schema()).validate(manifest)
    assert manifest["status"] == "private"
    assert manifest["provenance"]["kind"] == "user_learned"
    assert manifest["markets"] == ["intl_en"]
    assert len(manifest["fingerprint"]) == 64
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash


def test_preview_compares_original_and_learned(tmp_path):
    path = write_html(tmp_path / "resume.html")
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learned = learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    preview = learned.preview_path.read_text(encoding="utf-8")
    assert "Original text" in preview
    assert "Learned layout" in preview
    assert "Li Ming" in preview
    assert "The original file is unchanged" in preview


def test_learn_refuses_failed_audit(tmp_path):
    path = write_html(tmp_path / "bad.html", BAD_HTML)
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    with pytest.raises(LearnError) as error:
        learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    assert error.value.code == "template.audit_failed"


def test_learn_with_explicit_override(tmp_path):
    path = write_html(tmp_path / "bad.html", BAD_HTML)
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learned = learn_template(
        result,
        audit,
        project_root=tmp_path,
        market="intl_en",
        persona="experienced",
        allow_failed=True,
    )
    assert learned.directory.is_dir()
    assert any("override" in warning for warning in learned.warnings)


def test_two_column_is_rebuilt_single_column(tmp_path):
    path = write_html(tmp_path / "two.html", TWO_COLUMN_HTML)
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learned = learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    manifest = json.loads(learned.manifest_path.read_text(encoding="utf-8"))
    assert manifest["page"]["columns"] == "single"
    assert any("single-column" in warning for warning in learned.warnings)


def test_existing_template_requires_force(tmp_path):
    path = write_html(tmp_path / "resume.html")
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    with pytest.raises(LearnError) as error:
        learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    assert error.value.code == "template.exists"
    rebuilt = learn_template(
        result, audit, project_root=tmp_path, market="intl_en", persona="experienced", force=True
    )
    assert rebuilt.directory.is_dir()


def test_load_learned_template(tmp_path):
    path = write_html(tmp_path / "resume.html")
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    learned = learn_template(result, audit, project_root=tmp_path, market="intl_en", persona="experienced")
    loaded = load_learned_template(learned.directory)
    assert loaded["manifest"]["id"] == learned.template_id
    assert "data-slot" in loaded["html"]
    assert "--accent" in loaded["css"]
