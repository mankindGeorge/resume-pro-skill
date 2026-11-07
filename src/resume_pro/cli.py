# SPDX-License-Identifier: MIT
"""Command-line interface for Resume Pro."""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import yaml
from bs4 import BeautifulSoup

from . import __version__, profile
from .application import (
    application_dir,
    create_application,
    default_template,
    load_application,
    page_budget,
    save_application,
)
from .errors import ResumeProError
from .ingest import IngestError, detect_lang, ingest_file, to_vault
from .lint import lint as run_lint
from .localize import collect_gaps, localize_application
from .match import match_vault
from .qa import run_qa
from .recommend import recommend as recommend_roles
from .render import application_locale, load_template, render_application
from .select import select_facts
from .workspace import publish_workspace
from .writing import FRAMEWORK_IDS, require_consent
from .intake import (
    IntakeEngine,
    load_session,
    new_session,
    save_session,
    summary as intake_summary,
)
from .paths import (
    find_project_root,
    require_project_root,
    resume_dir,
    session_path,
    templates_dir,
    vault_path,
)
from .sufficiency import STATUS_BLOCKED, GateReport, evaluate
from .template_audit import VERDICT_REPLACE, VERDICT_UNMAINTAINABLE, TemplateAudit, audit_template
from .template_learn import build_preview, learn_template, load_learned_template
from .vault import empty_vault, load_vault, merge_vaults, save_vault

STATUS_LABELS = {
    "blocked": {"en": "BLOCKED", "zh": "被阻断"},
    "minimum": {"en": "MINIMUM", "zh": "最低可投"},
    "strong": {"en": "STRONG", "zh": "强匹配"},
}
DIM_STATUS = {
    "pass": {"en": "pass", "zh": "通过"},
    "warn": {"en": "warn", "zh": "提醒"},
    "fail": {"en": "fail", "zh": "未通过"},
}


def _lang(ctx: click.Context) -> str:
    return (ctx.obj or {}).get("lang", "en")


def _exit_code(error: ResumeProError) -> int:
    if error.code == "gate.blocked":
        return 2
    if error.code in {"ingest.unsupported_format", "ingest.conversion_failed", "ingest.scanned"}:
        return 5
    if error.code == "ingest.dependency_missing":
        return 6
    if error.code == "template.audit_failed":
        return 4
    return 3


def _handle(ctx: click.Context, error: ResumeProError) -> None:
    if (ctx.obj or {}).get("json"):
        click.echo(json.dumps({"ok": False, "error": error.to_dict()}, ensure_ascii=False, indent=2))
    else:
        click.echo(error.render(), err=True)
    ctx.exit(_exit_code(error))


def _json_enabled(ctx: click.Context, flag: bool = False) -> bool:
    enabled = bool(flag or (ctx.obj or {}).get("json"))
    ctx.ensure_object(dict)
    ctx.obj["json"] = enabled
    return enabled


def _question_payload(engine: IntakeEngine, question) -> dict[str, Any]:
    return {
        "id": question.id,
        "stage": question.stage,
        "kind": question.kind,
        "prompt": question.prompt,
        "why": question.why,
        "required": question.required,
        "example": question.example,
        "choices": list(question.choices),
    }


def _print_question(engine: IntakeEngine, question, lang: str) -> None:
    progress = engine.progress()
    click.echo("")
    click.echo(f"[{question.stage}] ({progress['answered']}/{progress['total']}) {question.text(lang)}")
    click.echo(f"  why: {question.why_text(lang)}")
    if question.example:
        click.echo(f"  e.g. {question.example}")
    if question.optional:
        click.echo("  optional: press Enter or type `skip` to leave a recorded gap")
    click.echo(f"  id: {question.id}")


def _print_summary(vault: dict[str, Any], session: dict[str, Any], lang: str) -> None:
    data = intake_summary(vault, session)
    if lang == "zh":
        click.echo(f"姓名: {data['identity']['name'] or '—'}")
        click.echo(f"目标: {data['target']['market'] or '—'} / {data['target']['persona'] or '—'} / {data['target']['role'] or '—'}")
        click.echo(f"教育: {data['counts']['education']} · 经历: {data['counts']['experience']} · 项目: {data['counts']['projects']} · 技能: {data['counts']['skills']}")
        click.echo(f"Bullet: {data['counts']['bullets']} · 证据: {data['counts']['evidence']}")
    else:
        click.echo(f"Name: {data['identity']['name'] or '—'}")
        click.echo(f"Target: {data['target']['market'] or '—'} / {data['target']['persona'] or '—'} / {data['target']['role'] or '—'}")
        click.echo(f"Education: {data['counts']['education']} · Experience: {data['counts']['experience']} · Projects: {data['counts']['projects']} · Skills: {data['counts']['skills']}")
        click.echo(f"Bullets: {data['counts']['bullets']} · Evidence: {data['counts']['evidence']}")
    if data.get("notes"):
        click.echo(f"Notes: {data['notes']}")
    for note in data["unresolved"]:
        click.echo(f"  unresolved [{note.get('severity')}]: {note.get('path')} — {note.get('reason')}")


def _print_report(report: GateReport, lang: str) -> None:
    label = STATUS_LABELS.get(report.status, {"en": report.status, "zh": report.status})[lang]
    click.echo(f"Gate: {label} ({report.market} / {report.persona})")
    for dimension in report.dimensions:
        info = dimension.to_dict()
        name = info["label_zh"] if lang == "zh" else info["label"]
        status_label = DIM_STATUS.get(info["status"], {"en": info["status"], "zh": info["status"]})[lang]
        click.echo(f"  {status_label:<4} {name}: {info['detail']}")
    if report.blockers:
        click.echo("Blockers:" if lang == "en" else "阻断项:")
        for item in report.blockers:
            click.echo(f"  - {item['code']} [{item['path']}]: {item['message']}")
            if item.get("fix"):
                click.echo(f"    fix: {item['fix']}")
    if report.warnings:
        click.echo("Warnings:" if lang == "en" else "警告:")
        for item in report.warnings:
            click.echo(f"  - {item['code']} [{item['path']}]: {item['message']}")
    if report.questions:
        click.echo("Next questions:" if lang == "en" else "建议追问:")
        for index, question in enumerate(report.questions, 1):
            click.echo(f"  {index}. {question['ask']}")
            click.echo(f"     why: {question['why']}")
    if report.draft:
        click.echo("DRAFT — NOT FOR SUBMISSION")
    click.echo(f"Can build: {report.can_build} · Deliverable: {report.deliverable}")


def _load_context(root: Path, lang: str = "en") -> tuple[dict[str, Any], dict[str, Any], IntakeEngine]:
    vault = load_vault(root=root)
    session = load_session(session_path(root), lang=lang)
    session["lang"] = lang
    engine = IntakeEngine(vault, session, lang=lang)
    return vault, session, engine


@click.group()
@click.version_option(__version__, prog_name="resume")
@click.option("--lang", type=click.Choice(["en", "zh"]), default="en", show_default=True, help="Message language; content is never translated.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.option("--cwd", type=click.Path(exists=True, file_okay=False, path_type=Path), default=None, help="Override the working directory used to locate .resume/.")
@click.pass_context
def cli(ctx: click.Context, lang: str, json_flag: bool, cwd: Path | None) -> None:
    ctx.ensure_object(dict)
    ctx.obj["lang"] = lang
    ctx.obj["json"] = json_flag
    if cwd is not None:
        os.chdir(cwd)


@cli.command()
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def init(ctx: click.Context, market: str | None, persona: str | None, json_flag: bool) -> None:
    """Create .resume/ and an empty vault."""
    as_json = _json_enabled(ctx, json_flag)
    root = find_project_root() or Path.cwd()
    try:
        directory = resume_dir(root)
        directory.mkdir(parents=True, exist_ok=True)
        vpath = vault_path(root)
        created = False
        if vpath.is_file():
            vault = load_vault(root=root)
        else:
            vault = empty_vault()
            created = True
        spath = session_path(root)
        session = load_session(spath)
        if market:
            profile.load_market(market)
            session["market"] = market
            if "target.market" not in session["answered"]:
                session["answered"].append("target.market")
            vault.setdefault("preferences", {})["target_markets"] = [market]
        if persona:
            profile.load_persona(persona)
            session["persona"] = persona
            if "target.persona" not in session["answered"]:
                session["answered"].append("target.persona")
        save_vault(vault, root=root, validate=False)
        save_session(session, spath)
        if as_json:
            click.echo(json.dumps({"ok": True, "root": str(root), "vault": str(vpath), "created": created, "session": str(spath)}, ensure_ascii=False, indent=2))
        else:
            click.echo(f"{'Created' if created else 'Found'} vault: {vpath}")
            click.echo(f"Session: {spath}")
            if created:
                click.echo("Next: `resume intake`")
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.option("--answer", "answer_text", default=None, help="Answer the current question and print the next one.")
@click.option("--id", "question_id", default=None, help="Answer a specific question id instead of the current one.")
@click.option("--skip", "skip_flag", is_flag=True, help="Skip the current (or --id) question and record the gap.")
@click.option("--summary", "summary_flag", is_flag=True, help="Show collected facts without asking a question.")
@click.option("--reset", "reset_flag", is_flag=True, help="Delete the intake session and start over.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def intake(ctx: click.Context, answer_text: str | None, question_id: str | None, skip_flag: bool, summary_flag: bool, reset_flag: bool, json_flag: bool) -> None:
    """Run the guided intake one question at a time."""
    as_json = _json_enabled(ctx, json_flag)
    lang = _lang(ctx)
    try:
        root = require_project_root()
        spath = session_path(root)
        if reset_flag:
            if spath.exists():
                spath.unlink()
            session = new_session(lang=lang)
            save_session(session, spath)
            if as_json:
                click.echo(json.dumps({"ok": True, "reset": True}, ensure_ascii=False, indent=2))
            else:
                click.echo("Intake session reset.")
            return

        vault, session, engine = _load_context(root, lang)
        if summary_flag:
            if not as_json:
                _print_summary(vault, session, lang)
            if session.get("market") and session.get("persona"):
                report = evaluate(vault, market=session["market"], persona=session["persona"], target_role=session.get("role"))
                if as_json:
                    click.echo(json.dumps({"ok": True, "summary": intake_summary(vault, session), "gate": report.to_dict()}, ensure_ascii=False, indent=2))
                else:
                    _print_report(report, lang)
            elif as_json:
                click.echo(json.dumps({"ok": True, "summary": intake_summary(vault, session)}, ensure_ascii=False, indent=2))
            return

        if question_id:
            question = engine.by_id(question_id)
            if question.when and not question.when(vault, session):
                raise ResumeProError(
                    "intake.not_applicable",
                    f"Question {question_id!r} is not applicable in the current state.",
                    fix="Run `resume intake --json` to see the current question.",
                )
        else:
            question = engine.current()

        if question is None:
            if as_json:
                click.echo(json.dumps({"ok": True, "complete": True, "summary": intake_summary(vault, session)}, ensure_ascii=False, indent=2))
            else:
                click.echo("Intake is complete.")
                _print_summary(vault, session, lang)
            return

        if skip_flag:
            engine.skip(question)
            save_vault(vault, root=root, validate=False)
            save_session(session, spath)
            next_question = engine.current()
            if as_json:
                click.echo(json.dumps({"ok": True, "skipped": question.id, "question": _question_payload(engine, next_question) if next_question else None, "complete": next_question is None}, ensure_ascii=False, indent=2))
            else:
                click.echo(f"Skipped {question.id}.")
                if next_question:
                    _print_question(engine, next_question, lang)
                else:
                    _print_summary(vault, session, lang)
            return

        if answer_text is not None:
            engine.answer(question, answer_text)
            save_vault(vault, root=root, validate=False)
            save_session(session, spath)
            next_question = engine.current()
            if as_json:
                click.echo(json.dumps({"ok": True, "answered": question.id, "question": _question_payload(engine, next_question) if next_question else None, "complete": next_question is None, "progress": engine.progress()}, ensure_ascii=False, indent=2))
            else:
                if next_question:
                    _print_question(engine, next_question, lang)
                else:
                    click.echo("Intake is complete.")
                    _print_summary(vault, session, lang)
            return

        if as_json:
            click.echo(json.dumps({"ok": True, "question": _question_payload(engine, question), "complete": False, "progress": engine.progress()}, ensure_ascii=False, indent=2))
            return

        # Interactive mode.
        while question is not None:
            _print_question(engine, question, lang)
            raw = click.prompt(">", prompt_suffix=" ", default="", show_default=False)
            lowered = raw.strip().lower()
            if lowered in {"quit", "exit"}:
                save_vault(vault, root=root, validate=False)
                save_session(session, spath)
                click.echo("Saved. Run `resume intake` to continue.")
                return
            if lowered in {"summary"}:
                _print_summary(vault, session, lang)
                continue
            try:
                engine.answer(question, raw)
            except ResumeProError as error:
                click.echo(error.render(), err=True)
                continue
            save_vault(vault, root=root, validate=False)
            save_session(session, spath)
            question = engine.current()
        click.echo("Intake is complete.")
        _print_summary(vault, session, lang)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.option("--draft", "draft_flag", is_flag=True, help="Mark the result as a non-deliverable draft.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def check(ctx: click.Context, draft_flag: bool, json_flag: bool) -> None:
    """Run the sufficiency gate; exit 2 when blocked."""
    as_json = _json_enabled(ctx, json_flag)
    lang = _lang(ctx)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        session = load_session(session_path(root))
        if not session.get("market") or not session.get("persona"):
            raise ResumeProError(
                "gate.context_missing",
                "The target market or persona is not set.",
                fix="Run `resume intake` and answer the first two questions.",
            )
        report = evaluate(vault, market=session["market"], persona=session["persona"], target_role=session.get("role"), draft=draft_flag)
        report_path = resume_dir(root) / "sufficiency.json"
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            click.echo(json.dumps({"ok": report.can_build, "report": str(report_path), "gate": report.to_dict()}, ensure_ascii=False, indent=2))
        else:
            _print_report(report, lang)
            click.echo(f"Report: {report_path}")
        ctx.exit(2 if report.status == STATUS_BLOCKED else 0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command("profile")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def profile_cmd(ctx: click.Context, json_flag: bool) -> None:
    """Show the current profile and missing dimensions."""
    as_json = _json_enabled(ctx, json_flag)
    lang = _lang(ctx)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        session = load_session(session_path(root))
        report = None
        if session.get("market") and session.get("persona"):
            report = evaluate(vault, market=session["market"], persona=session["persona"], target_role=session.get("role"))
        if as_json:
            click.echo(json.dumps({"ok": True, "summary": intake_summary(vault, session), "gate": report.to_dict() if report else None}, ensure_ascii=False, indent=2))
            return
        _print_summary(vault, session, lang)
        if report:
            _print_report(report, lang)
        else:
            click.echo("Gate not run: target market or persona is missing. Run `resume intake`.")
    except ResumeProError as error:
        _handle(ctx, error)


def _version_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _snapshot_version(root: Path, application: dict[str, Any]) -> str | None:
    directory = application_dir(root, application["slug"])
    html_path = directory / (application.get("output") or {}).get("html", "resume.html")
    if not html_path.is_file():
        return None
    version_dir = directory / "versions" / _version_timestamp()
    version_dir.mkdir(parents=True, exist_ok=True)
    output = application.get("output") or {}
    names = [
        "application.yaml",
        "render.json",
        "lint.json",
        "qa.json",
        output.get("html", "resume.html"),
        output.get("editable_html", "resume-editable.html"),
    ]
    for name in names:
        source = directory / name
        if source.is_file():
            shutil.copy2(source, version_dir / name)
    return version_dir.name


def _run_build(
    root: Path,
    vault: dict[str, Any],
    application: dict[str, Any],
    *,
    template_id: str | None = None,
    draft: bool = False,
    confirm: bool = False,
    snapshot: bool = True,
) -> tuple[int, dict[str, Any]]:
    slug = application["slug"]
    market = application["market"]
    persona = application["persona"]
    role = (application.get("target") or {}).get("role")
    gate = evaluate(vault, market=market, persona=persona, target_role=role)
    lint_report = run_lint(vault, market=market, persona=persona, application=application, target_role=role)
    lint_path = application_dir(root, slug) / "lint.json"
    lint_path.write_text(json.dumps(lint_report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload: dict[str, Any] = {
        "ok": False,
        "slug": slug,
        "gate": gate.to_dict(),
        "lint": lint_report.to_dict(),
        "lint_report": str(lint_path),
    }
    if gate.status == STATUS_BLOCKED:
        payload["next"] = "Resolve the gate blockers, then rebuild."
        return 2, payload
    if gate.requires_confirmation and not confirm:
        payload["next"] = "The gate is MINIMUM; rerun with --yes to confirm a truthful but modest version."
        return 2, payload
    if not draft and vault.get("status") != "ready":
        payload["error"] = {
            "code": "build.unconfirmed_facts",
            "message": "The facts have not been confirmed, so no deliverable resume can be built.",
            "fix": "Run `resume intake`, review the summary, and answer confirm.summary with yes; --yes only accepts a minimum gate, it is not fact consent.",
        }
        payload["next"] = "Confirm the collected facts before building. A draft (--draft) may still be rendered for inspection."
        return 2, payload
    locale = application_locale(application)
    source_locale = "en" if locale == "zh" else "zh"
    locale_gaps = collect_gaps(vault, application["selection"], locale=locale, source_locale=source_locale)
    if locale_gaps:
        payload["locale_gaps"] = [gap.to_dict() for gap in locale_gaps]
        payload["next"] = (
            f"{len(locale_gaps)} selected fact(s) have no {locale!r} text. "
            "Write the target-language facts in the vault, or use `resume localize --draft` to inspect the gaps."
        )
        return 3, payload
    if not lint_report.ok:
        payload["next"] = "Fix the lint errors, then rebuild."
        return 4, payload
    version = _snapshot_version(root, application) if snapshot else None
    result = render_application(root, vault, application, template_id=template_id, draft=draft)
    qa = run_qa(root, vault, application, template_id=result.template_id, draft=draft)
    qa_path = application_dir(root, slug) / "qa.json"
    qa_path.write_text(json.dumps(qa.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    application["qa"] = {
        "status": qa.status,
        "report": str(qa_path),
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    save_application(root, application)
    workspace = publish_workspace(
        root,
        slug,
        [result.html_path, result.editable_path],
    )
    payload.update(
        {
            "ok": qa.status != "fail",
            "render": result.to_dict(),
            "qa": qa.to_dict(),
            "qa_report": str(qa_path),
            "workspace": str(workspace),
            "version": version,
        }
    )
    return (0 if qa.status != "fail" else 4), payload


@cli.command()
@click.argument("application")
@click.option("--template", "template_id", default=None, help="Override the application template for this build.")
@click.option("--draft", "draft_flag", is_flag=True, help="Add a visible DRAFT banner; not deliverable.")
@click.option("--yes", "confirm_flag", is_flag=True, help="Confirm a `minimum` gate result.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def build(
    ctx: click.Context,
    application: str,
    template_id: str | None,
    draft_flag: bool,
    confirm_flag: bool,
    json_flag: bool,
) -> None:
    """Render the locked HTML and editable HTML. HTML only."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        app = load_application(root, application)
        exit_code, payload = _run_build(
            root,
            vault,
            app,
            template_id=template_id,
            draft=draft_flag,
            confirm=confirm_flag,
        )
        if as_json:
            _json_out(payload)
        else:
            _print_report(evaluate(vault, market=app["market"], persona=app["persona"], target_role=(app.get("target") or {}).get("role")), _lang(ctx))
            _print_lint(run_lint(vault, market=app["market"], persona=app["persona"], application=app, target_role=(app.get("target") or {}).get("role")))
            if payload.get("render"):
                render = payload["render"]
                click.echo(f"Template: {render['template_id']} · pages: {render['layout']['pages']}")
                click.echo(f"HTML: {render['html']}")
                click.echo(f"Editable preview: {render['editable_html']}")
                if payload.get("workspace"):
                    click.echo(f"Workspace: {payload['workspace']}")
                if payload.get("qa"):
                    _print_qa(payload["qa"])
            elif payload.get("next"):
                click.echo(payload["next"], err=True)
        ctx.exit(exit_code)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def templates(ctx: click.Context, json_flag: bool) -> None:
    """List available library and learned templates."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = find_project_root() or Path.cwd()
        directories = [templates_dir(), root / "templates"]
        seen: set[tuple[str, str | None]] = set()
        items = []
        manifest_paths = []
        for directory in directories:
            if directory.is_dir():
                for folder in ("cn", "en"):
                    manifest_paths.extend(sorted((directory / folder).glob("*/manifest.json")))
                manifest_paths.extend(sorted(directory.glob("user-*/manifest.json")))
        for manifest_path in manifest_paths:
            folder = manifest_path.parent.parent.name
            language = {"cn": "zh", "en": "en"}.get(folder)
            key = (manifest_path.parent.name, language)
            if key in seen:
                continue
            seen.add(key)
            try:
                template = load_template(manifest_path.parent.name, root=root, language=language)
                manifest = template["manifest"]
                preview_path = template["directory"] / (manifest.get("files") or {}).get("preview", "preview.html")
                items.append(
                    {
                        "id": manifest["id"],
                        "name": manifest["name"],
                        "language": manifest.get("language"),
                        "status": manifest["status"],
                        "markets": manifest["markets"],
                        "personas": manifest["personas"],
                        "pages": manifest["page"]["target_pages"],
                        "columns": manifest["page"]["columns"],
                        "fingerprint": manifest["fingerprint"],
                        "path": str(template["directory"]),
                        "preview": str(preview_path) if preview_path.is_file() else None,
                        "folder": folder if folder in {"cn", "en"} else "user",
                    }
                )
            except ResumeProError as error:
                items.append({
                    "id": manifest_path.parent.name,
                    "language": language,
                    "folder": folder if folder in {"cn", "en"} else "user",
                    "error": error.to_dict(),
                })
        if as_json:
            _json_out({"ok": True, "templates": items})
        else:
            groups = (
                ("cn", "Chinese templates (templates/cn)"),
                ("en", "English templates (templates/en)"),
                ("user", "Learned templates (templates/user-*)"),
            )
            for folder, label in groups:
                group = [item for item in items if item.get("folder", "user") == folder]
                if not group:
                    continue
                click.echo(label)
                for item in group:
                    if "error" in item:
                        click.echo(f"  {item['id']}: INVALID — {item['error']['message']}")
                    else:
                        click.echo(
                            f"  {item['id']}: {item['name']} · {', '.join(item['markets'])} · "
                            f"{', '.join(item['personas'])} · {item['pages']['min']}–{item['pages']['max']} pages"
                        )
                        if item.get("preview"):
                            click.echo(f"      preview: {item['preview']}")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:40] or "document"


def _validate_template_language(
    root: Path, market: str, template_id: str, *, language: str | None = None,
) -> None:
    language = language or profile.load_market(market)["language"]
    load_template(template_id, root=root, language=language)


def _report_dir(root: Path, kind: str, source: Path) -> Path:
    directory = resume_dir(root) / kind / f"{_timestamp()}-{_slug(source.stem)}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _resolve_target(
    root: Path,
    market: str | None,
    persona: str | None,
    *,
    save: bool = False,
) -> dict[str, Any]:
    session = load_session(session_path(root))
    if market:
        profile.load_market(market)
        session["market"] = market
        if "target.market" not in session["answered"]:
            session["answered"].append("target.market")
    if persona:
        profile.load_persona(persona)
        session["persona"] = persona
        if "target.persona" not in session["answered"]:
            session["answered"].append("target.persona")
    if not session.get("market") or not session.get("persona"):
        raise ResumeProError(
            "ingest.target_missing",
            "The target market and persona are required for a template audit.",
            fix="Pass --market and --persona, for example `--market cn_internet --persona student_with_internship`.",
        )
    if save:
        save_session(session, session_path(root))
    return session


def _ingest_readable(file: Path):
    """Ingest a resume file, refusing scanned/image-only input the CLI cannot read."""
    result = ingest_file(file)
    if result.scanned:
        raise IngestError(
            "ingest.scanned",
            f"{file.name} is scanned or image-only, so its text cannot be read.",
            fix="Export a text-based PDF or DOCX, or paste the content as Markdown/TXT.",
        )
    return result


def _print_ingest(result) -> None:
    fields = result.fields or {}
    click.echo(
        f"Extracted: {result.format} · {len(result.text)} chars · "
        f"education {len(fields.get('education') or [])} · "
        f"experience {len(fields.get('experience') or [])} · "
        f"projects {len(fields.get('projects') or [])} · "
        f"skills {len(fields.get('skills') or [])}"
    )
    if result.scanned:
        click.echo("Scanned/image-only: text could not be read.")
    for warning in result.warnings:
        click.echo(f"  warning: {warning}")
    if result.needs_confirmation:
        click.echo("  needs confirmation: " + ", ".join(result.needs_confirmation[:8]))


def _print_audit(audit: TemplateAudit) -> None:
    click.echo(f"Template verdict: {audit.verdict} (keep allowed: {audit.keep_allowed})")
    for dimension in audit.dimensions:
        info = dimension.to_dict()
        click.echo(f"  {info['status']:<4} {info['label']}: {info['detail']}")
        if info["fix"] and info["status"] != "pass":
            click.echo(f"       fix: {info['fix']}")
    if audit.recommendations:
        click.echo("  recommended templates: " + ", ".join(audit.recommendations))


def _json_out(data: dict[str, Any]) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def review(ctx: click.Context, file: Path, market: str | None, persona: str | None, json_flag: bool) -> None:
    """Diagnose an existing resume. Never rewrites it."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = find_project_root() or Path.cwd()
        resume_dir(root).mkdir(parents=True, exist_ok=True)
        session = _resolve_target(root, market, persona)
        result = _ingest_readable(file)
        audit = audit_template(result, market=session["market"], persona=session["persona"])
        directory = _report_dir(root, "reviews", file)
        report = {"extraction": result.to_dict(), "audit": audit.to_dict()}
        report_path = directory / "review.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        workspace = publish_workspace(root, directory.name, [report_path])
        ok = audit.verdict not in (VERDICT_REPLACE, VERDICT_UNMAINTAINABLE)
        if as_json:
            _json_out({"ok": ok, "report": str(report_path), "workspace": str(workspace), **report})
        else:
            _print_ingest(result)
            _print_audit(audit)
            click.echo(f"Report: {report_path}")
            click.echo(f"Workspace: {workspace}")
        ctx.exit(0 if ok else 4)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command("template-import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--force", is_flag=True, help="Rebuild an existing learned template.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def template_import(ctx: click.Context, file: Path, market: str | None, persona: str | None, force: bool, json_flag: bool) -> None:
    """Audit a user template and learn it only when it passes."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = find_project_root() or Path.cwd()
        resume_dir(root).mkdir(parents=True, exist_ok=True)
        session = _resolve_target(root, market, persona)
        result = _ingest_readable(file)
        audit = audit_template(result, market=session["market"], persona=session["persona"])
        directory = _report_dir(root, "template-imports", file)
        (directory / "audit.json").write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not audit.keep_allowed:
            if as_json:
                _json_out({"ok": False, "audit": audit.to_dict(), "report": str(directory / "audit.json")})
            else:
                _print_audit(audit)
                click.echo(f"Report: {directory / 'audit.json'}")
            ctx.exit(4)
        learned = learn_template(
            result,
            audit,
            project_root=root,
            market=session["market"],
            persona=session["persona"],
            force=force,
        )
        (directory / "learn.json").write_text(json.dumps(learned.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({"ok": True, "audit": audit.to_dict(), "learned": learned.to_dict()})
        else:
            _print_audit(audit)
            click.echo(f"Learned template: {learned.directory}")
            click.echo(f"Preview: {learned.preview_path}")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--keep-template", is_flag=True, help="Keep the original template if the audit allows it.")
@click.option("--template", "template_id", default=None, help="Use a library or learned template id.")
@click.option("--override", default=None, help="Record an explicit reason to keep a failing template.")
@click.option("--force", is_flag=True, help="Rebuild an existing learned template.")
@click.option("--merge", "merge_flag", is_flag=True, help="Merge into an existing vault even if the name differs.")
@click.option("--role", default=None, help="Target role for this application.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def optimize(
    ctx: click.Context,
    file: Path,
    market: str | None,
    persona: str | None,
    keep_template: bool,
    template_id: str | None,
    override: str | None,
    force: bool,
    merge_flag: bool,
    role: str | None,
    json_flag: bool,
) -> None:
    """Ingest an existing resume, audit its template, and merge facts into the vault."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        if keep_template and template_id:
            raise ResumeProError(
                "ingest.conflicting_options",
                "Choose either --keep-template or --template, not both.",
                fix="Pick one template decision.",
            )
        if override and not keep_template:
            raise ResumeProError(
                "ingest.conflicting_options",
                "--override only applies together with --keep-template.",
                fix="Add --keep-template, or remove --override.",
            )
        root = find_project_root() or Path.cwd()
        resume_dir(root).mkdir(parents=True, exist_ok=True)
        session = _resolve_target(root, market, persona, save=True)
        vpath = vault_path(root)
        vault = load_vault(root=root) if vpath.is_file() else empty_vault()
        result = _ingest_readable(file)
        audit = audit_template(result, market=session["market"], persona=session["persona"])
        directory = _report_dir(root, "imports", file)
        (directory / "extraction.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (directory / "audit.json").write_text(json.dumps(audit.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        fragment, needs = to_vault(result)
        if role:
            session["role"] = role
            fragment.setdefault("preferences", {})["target_roles"] = [role]
        existing_name = (vault.get("identity") or {}).get("full_name")
        incoming_name = (fragment.get("identity") or {}).get("full_name")
        existing_facts = any(vault.get(collection) for collection in ("education", "experience", "projects"))
        replaced = bool(
            existing_facts
            and existing_name
            and incoming_name
            and str(existing_name).strip().casefold() != str(incoming_name).strip().casefold()
            and not merge_flag
        )
        if replaced:
            merged = fragment
            if not merged.get("preferences") and vault.get("preferences"):
                merged["preferences"] = vault["preferences"]
        else:
            merged = merge_vaults(vault, fragment)
        merged.setdefault("preferences", {})["target_markets"] = [session["market"]]
        if role:
            merged["preferences"]["target_roles"] = [role]
        merged["status"] = "collecting"

        decision: dict[str, Any]
        exit_code = 0
        if keep_template:
            if not audit.keep_allowed and not override:
                decision = {"decision": "rejected", "audit": audit.to_dict()}
                exit_code = 4
            else:
                learned = learn_template(
                    result,
                    audit,
                    project_root=root,
                    market=session["market"],
                    persona=session["persona"],
                    force=force,
                    allow_failed=bool(override),
                )
                decision = {
                    "decision": "keep",
                    "template": learned.to_dict(),
                    "override": override,
                }
        elif template_id:
            template_path = root / "templates" / template_id / "manifest.json"
            if not template_path.is_file():
                raise ResumeProError(
                    "template.not_available",
                    f"Template {template_id!r} is not built in this workspace.",
                    fix="Use --keep-template in Phase 1B; the six library templates arrive in Phase 3.",
                )
            decision = {"decision": "library", "template_id": template_id}
        else:
            decision = {"decision": "recommend", "recommendations": audit.recommendations}

        (directory / "template-decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        vault_saved = exit_code == 0
        if vault_saved:
            save_vault(merged, root=root, validate=False)
            session["confirmed"] = False
            if "confirm.summary" in session.get("answered", []):
                session["answered"].remove("confirm.summary")
            save_session(session, session_path(root))
        payload = {
            "ok": exit_code == 0,
            "vault": str(vpath),
            "report": str(directory),
            "extraction": str(directory / "extraction.json"),
            "audit": audit.to_dict(),
            "decision": decision,
            "needs_confirmation": needs,
            "vault_replaced": replaced,
            "vault_saved": vault_saved,
        }
        if as_json:
            _json_out(payload)
        else:
            _print_ingest(result)
            _print_audit(audit)
            if replaced:
                click.echo("Existing facts belonged to a different name; the vault was replaced. Use --merge to merge explicitly.")
            click.echo(f"Vault: {vpath}")
            click.echo(f"Report: {directory}")
            click.echo(f"Template decision: {decision.get('decision')}")
            if needs:
                click.echo("Needs confirmation: " + ", ".join(needs[:10]))
        if exit_code:
            ctx.exit(exit_code)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("file", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--app", "app_slug", default=None, help="Restyle an existing application and rebuild it.")
@click.option("--template", "template_id", required=True, help="Template id.")
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--yes", "confirm_flag", is_flag=True, help="Confirm a `minimum` gate result.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def restyle(
    ctx: click.Context,
    file: Path | None,
    app_slug: str | None,
    template_id: str,
    market: str | None,
    persona: str | None,
    confirm_flag: bool,
    json_flag: bool,
) -> None:
    """Change the template without changing facts."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        if file and app_slug:
            raise ResumeProError("restyle.conflicting_inputs", "Pass a file or --app, not both.", fix="Pick one target.")
        root = find_project_root() or Path.cwd()
        resume_dir(root).mkdir(parents=True, exist_ok=True)

        if app_slug:
            application = load_application(root, app_slug)
            _validate_template_language(root, application["market"], template_id, language=application_locale(application))
            _snapshot_version(root, application)
            application["template"]["id"] = template_id
            application["template"]["source"] = "user_learned" if template_id.startswith("user-") else "library"
            save_application(root, application)
            vault = load_vault(root=root)
            exit_code, payload = _run_build(
                root,
                vault,
                application,
                template_id=template_id,
                confirm=confirm_flag,
                snapshot=False,
            )
            if as_json:
                _json_out(payload)
            else:
                if payload.get("render"):
                    render = payload["render"]
                    click.echo(f"Restyle: {application['slug']} → {template_id}")
                    click.echo(f"HTML: {render['html']}")
                    click.echo(f"Editable preview: {render['editable_html']}")
                else:
                    click.echo(payload.get("next", "Build did not complete."), err=True)
            ctx.exit(exit_code)

        if file is None:
            raise ResumeProError(
                "restyle.missing_input",
                "Pass a file or --app.",
                fix="Use `resume restyle resume.docx --template <id>` or `resume restyle --app <slug> --template <id>`.",
            )

        session = _resolve_target(root, market, persona)
        template_dir = root / "templates" / template_id
        if not (template_dir / "manifest.json").is_file():
            raise ResumeProError(
                "template.not_available",
                f"No learned template at {template_dir}.",
                fix="Use --app for a library template after `resume tailor`, or learn a template with `resume template-import`.",
            )
        result = _ingest_readable(file)
        audit = audit_template(result, market=session["market"], persona=session["persona"])
        loaded = load_learned_template(template_dir)
        preview = build_preview(result, loaded["css"], detect_lang(result.text), result.path.name)
        directory = _report_dir(root, "restyles", file)
        (directory / "preview.html").write_text(preview, encoding="utf-8")
        report = {
            "extraction": result.to_dict(),
            "audit": audit.to_dict(),
            "template_id": template_id,
            "preview": str(directory / "preview.html"),
        }
        (directory / "restyle.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({"ok": True, **report})
        else:
            _print_ingest(result)
            click.echo(f"Template: {template_id}")
            click.echo(f"Preview: {directory / 'preview.html'}")
            click.echo("Facts are unchanged. Use --app to rebuild a canonical HTML application.")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


def _read_source(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _app_or_session(
    root: Path,
    app_slug: str | None,
    market: str | None,
    persona: str | None,
) -> tuple[dict[str, Any] | None, str, str, str | None]:
    if app_slug:
        application = load_application(root, app_slug)
        return (
            application,
            application["market"],
            application["persona"],
            (application.get("target") or {}).get("role"),
        )
    session = _resolve_target(root, market, persona)
    return None, session["market"], session["persona"], session.get("role")


def _print_match(report) -> None:
    data = report.to_dict()
    click.echo(
        f"Match: {data['score_range'][0]}–{data['score_range'][1]}% · {data['tier']} "
        f"(must {data['must_score']:.2f} · nice {data['nice_score']:.2f} · hidden {data['hidden_score']:.2f})"
    )
    if data["gaps"]:
        click.echo("Gaps:")
        for gap in data["gaps"][:8]:
            click.echo(f"  - [{gap['classification']}] {gap['requirement']}")
            click.echo(f"    {gap['fix']}")
    if data["risks"]:
        click.echo("Risks:")
        for risk in data["risks"]:
            click.echo(f"  - [{risk['type']}] {risk['question']}")
            click.echo(f"    response: {risk['response']}")
    for note in data.get("notes") or []:
        click.echo(f"  note: {note}")


def _print_qa(qa) -> None:
    data = qa.to_dict() if hasattr(qa, "to_dict") else qa
    click.echo(
        f"QA: {data['status'].upper()} · pages {data['metrics'].get('pages', '?')} · "
        f"bullets {data['metrics'].get('found_bullets', '?')}/{data['metrics'].get('selected_bullets', '?')}"
    )
    for check in data["checks"]:
        if check["status"] != "pass":
            click.echo(f"  [{check['status']}] {check['id']}: {check['detail']}")
            if check.get("fix"):
                click.echo(f"       fix: {check['fix']}")


def _print_lint(report) -> None:
    data = report.to_dict()
    click.echo(
        f"Lint: {data['counts']['errors']} error(s), {data['counts']['warnings']} warning(s), "
        f"{data['counts']['info']} info · estimated pages {data['page_estimate']}"
    )
    click.echo(f"10-second skim: {'pass' if data['skim']['passed'] else 'fail'} · found: {', '.join(data['skim']['found']) or '—'}")
    for issue in data["issues"]:
        click.echo(f"  [{issue['severity']}] {issue['code']} [{issue['path']}]: {issue['message']}")
        if issue.get("fix"):
            click.echo(f"       fix: {issue['fix']}")


@cli.command()
@click.option("--role", default=None, help="Target role; defaults to the preferred role in the vault.")
@click.option("--market", required=True, type=click.Choice(profile.MARKET_IDS))
@click.option("--persona", required=True, type=click.Choice(profile.PERSONA_IDS))
@click.option("--framework", required=True, type=click.Choice(FRAMEWORK_IDS))
@click.option("--company", default=None)
@click.option("--template", "template_id", default=None, help="Template id; defaults by market/persona.")
@click.option("--slug", default=None)
@click.option("--no-role-in-filename", "no_role_filename", is_flag=True, help="Keep the output file named resume.html.")
@click.option("--jd", "jd_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def new(
    ctx: click.Context,
    role: str | None,
    market: str,
    persona: str,
    framework: str,
    company: str | None,
    template_id: str | None,
    slug: str | None,
    no_role_filename: bool,
    jd_path: Path | None,
    json_flag: bool,
) -> None:
    """Create an application with a selected fact set and an explicit writing framework."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        session = load_session(session_path(root))
        require_consent(framework, True)
        mode = (vault.get("preferences") or {}).get("application_mode") or "unknown"
        role = role or (vault.get("preferences") or {}).get("preferred_role") or session.get("role")
        if not role:
            role = "General Application" if mode == "mass" else "Target Role"
        effective_template = template_id or default_template(market, persona)
        _validate_template_language(root, market, effective_template)
        budget = page_budget(market, persona)
        selection = select_facts(
            vault,
            market=market,
            persona=persona,
            target_role=role,
            page_max=budget["max"],
        )
        application = create_application(
            vault=vault,
            selection=selection,
            role=role,
            market=market,
            persona=persona,
            framework=framework,
            company=company,
            template_id=template_id,
            slug=slug,
            jd_path=str(jd_path) if jd_path else None,
            role_in_filename=False if no_role_filename else None,
        )
        locale = application["writing"]["locale"]
        source_locale = "en" if locale == "zh" else "zh"
        locale_gaps = collect_gaps(vault, selection, locale=locale, source_locale=source_locale)
        path = save_application(root, application)
        if as_json:
            _json_out(
                {
                    "ok": True,
                    "slug": application["slug"],
                    "path": str(path),
                    "framework": framework,
                    "template": application["template"]["id"],
                    "selected_facts": len(selection["fact_ids"]),
                    "selected_bullets": len(selection["bullet_ids"]),
                    "locale_gaps": [gap.to_dict() for gap in locale_gaps],
                    "html": application["output"]["html"],
                    "editable_html": application["output"]["editable_html"],
                }
            )
        else:
            click.echo(f"Application: {application['slug']}")
            click.echo(f"Path: {path}")
            click.echo(f"Framework: {framework} · Template: {application['template']['id']}")
            click.echo(f"Output: {application['output']['html']}")
            click.echo(f"Selected {len(selection['fact_ids'])} facts and {len(selection['bullet_ids'])} bullets.")
            if locale_gaps:
                click.echo(f"Warning: {len(locale_gaps)} selected fact(s) have no {locale!r} text; build will block until they are written.")
            click.echo("Next: `resume lint --app <slug>` or `resume tailor --app <slug> --jd jd.md`.")
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command("lint")
@click.option("--app", "app_slug", default=None)
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def lint_cmd(ctx: click.Context, app_slug: str | None, market: str | None, persona: str | None, json_flag: bool) -> None:
    """Run content and CN-market lint plus the 10-second skim test."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        application, resolved_market, resolved_persona, role = _app_or_session(root, app_slug, market, persona)
        report = run_lint(
            vault,
            market=resolved_market,
            persona=resolved_persona,
            application=application,
            target_role=role,
        )
        if application:
            report_path = application_dir(root, application["slug"]) / "lint.json"
        else:
            report_path = resume_dir(root) / "lint.json"
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({"ok": report.ok, "report": str(report_path), "lint": report.to_dict()})
        else:
            _print_lint(report)
            click.echo(f"Report: {report_path}")
        ctx.exit(0 if report.ok else 4)
    except ResumeProError as error:
        _handle(ctx, error)



@cli.command()
@click.option("--jd", "jd_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--app", "app_slug", default=None)
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def match(ctx: click.Context, jd_path: Path, app_slug: str | None, market: str | None, persona: str | None, json_flag: bool) -> None:
    """Score the vault against a JD; report only."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        application, resolved_market, resolved_persona, role = _app_or_session(root, app_slug, market, persona)
        report = match_vault(
            vault,
            _read_source(jd_path),
            market=resolved_market,
            persona=resolved_persona,
            target_role=role,
        )
        if application:
            report_path = application_dir(root, application["slug"]) / "match.json"
        else:
            directory = resume_dir(root) / "matches"
            directory.mkdir(parents=True, exist_ok=True)
            report_path = directory / f"{_timestamp()}.json"
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({"ok": True, "report": str(report_path), "match": report.to_dict()})
        else:
            _print_match(report)
            click.echo(f"Report: {report_path}")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("file", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--jd", "jd_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--app", "app_slug", default=None)
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--role", default=None)
@click.option("--framework", type=click.Choice(FRAMEWORK_IDS), default=None)
@click.option("--template", "template_id", default=None)
@click.option("--slug", default=None)
@click.option("--no-role-in-filename", "no_role_filename", is_flag=True, help="Keep the output file named resume.html.")
@click.option("--merge", "merge_flag", is_flag=True, help="Merge into an existing vault even if the name differs.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def tailor(
    ctx: click.Context,
    file: Path | None,
    jd_path: Path,
    app_slug: str | None,
    market: str | None,
    persona: str | None,
    role: str | None,
    framework: str | None,
    template_id: str | None,
    slug: str | None,
    no_role_filename: bool,
    merge_flag: bool,
    json_flag: bool,
) -> None:
    """Select facts for one JD and create or update an application. No render yet."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        if file and app_slug:
            raise ResumeProError(
                "tailor.conflicting_inputs",
                "Pass a file or --app, not both.",
                fix="Use the file to ingest new facts, or --app to retarget an existing application.",
            )
        root = require_project_root()
        vault = load_vault(root=root)
        application = load_application(root, app_slug) if app_slug else None

        if file:
            result = _ingest_readable(file)
            fragment, _ = to_vault(result)
            existing_name = (vault.get("identity") or {}).get("full_name")
            incoming_name = (fragment.get("identity") or {}).get("full_name")
            existing_facts = any(vault.get(collection) for collection in ("education", "experience", "projects"))
            replaced = bool(
                existing_facts
                and existing_name
                and incoming_name
                and str(existing_name).strip().casefold() != str(incoming_name).strip().casefold()
                and not merge_flag
            )
            vault = fragment if replaced else merge_vaults(vault, fragment)
            vault["status"] = "collecting"
            save_vault(vault, root=root, validate=False)
            if not role:
                role = ((fragment.get("preferences") or {}).get("target_roles") or [None])[0]

        resolved_market = (application or {}).get("market") or market
        resolved_persona = (application or {}).get("persona") or persona
        if not resolved_market or not resolved_persona:
            session = load_session(session_path(root))
            resolved_market = resolved_market or session.get("market")
            resolved_persona = resolved_persona or session.get("persona")
        if not resolved_market or not resolved_persona:
            raise ResumeProError(
                "tailor.target_missing",
                "Market and persona are required.",
                fix="Pass --market and --persona, or run `resume intake` first.",
            )
        if not role:
            role = (application or {}).get("target", {}).get("role")
        if not role:
            session_data = load_session(session_path(root))
            role = (vault.get("preferences") or {}).get("preferred_role") or session_data.get("role")
        mode = (vault.get("preferences") or {}).get("application_mode") or "unknown"
        if not role:
            role = "General Application" if mode == "mass" else "Target Role"

        chosen_framework = framework or (application or {}).get("writing", {}).get("framework")
        require_consent(chosen_framework, True)
        effective_template = template_id or (application or {}).get("template", {}).get("id") or default_template(resolved_market, resolved_persona)
        _validate_template_language(root, resolved_market, effective_template)

        jd_text = _read_source(jd_path)
        report = match_vault(vault, jd_text, market=resolved_market, persona=resolved_persona, target_role=role)
        budget = page_budget(resolved_market, resolved_persona)
        selection = select_facts(
            vault,
            market=resolved_market,
            persona=resolved_persona,
            target_role=role,
            jd_terms=set(report.keywords),
            page_max=budget["max"],
        )
        new_application = create_application(
            vault=vault,
            selection=selection,
            role=role,
            market=resolved_market,
            persona=resolved_persona,
            framework=chosen_framework,
            company=(application or {}).get("target", {}).get("company"),
            template_id=template_id or (application or {}).get("template", {}).get("id"),
            slug=slug or (application or {}).get("slug"),
            jd_path=str(jd_path),
            role_in_filename=False if no_role_filename else None,
        )
        if application:
            new_application["created_at"] = application.get("created_at", new_application["created_at"])
        path = save_application(root, new_application)
        match_path = application_dir(root, new_application["slug"]) / "match.json"
        match_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out(
                {
                    "ok": True,
                    "slug": new_application["slug"],
                    "path": str(path),
                    "match": report.to_dict(),
                    "match_report": str(match_path),
                    "selected_facts": len(selection["fact_ids"]),
                    "selected_bullets": len(selection["bullet_ids"]),
                }
            )
        else:
            _print_match(report)
            click.echo(f"Application: {new_application['slug']}")
            click.echo(f"Path: {path}")
            click.echo(f"Match report: {match_path}")
            click.echo("Rendering arrives in Phase 3.")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.option("--app", "app_slug", default=None)
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--persona", type=click.Choice(profile.PERSONA_IDS), default=None)
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def recommend(ctx: click.Context, app_slug: str | None, market: str | None, persona: str | None, json_flag: bool) -> None:
    """Recommend role families and proof-building plans. No live jobs."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        application, resolved_market, resolved_persona, _ = _app_or_session(root, app_slug, market, persona)
        report = recommend_roles(vault, market=resolved_market, persona=resolved_persona)
        report_path = resume_dir(root) / "recommend.json"
        report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({"ok": True, "report": str(report_path), "recommendation": report.to_dict()})
        else:
            for family in report.families:
                click.echo(f"{family.tier}: {family.label} ({family.score:.2f})")
                click.echo(f"  matched: {', '.join(family.matched) or '—'}")
                click.echo(f"  plan: {family.build_plan}")
            for note in report.notes:
                click.echo(f"  note: {note}")
            click.echo(f"Report: {report_path}")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("application")
@click.option("--to", "target_locale", required=True, type=click.Choice(["en", "zh"]))
@click.option("--market", type=click.Choice(profile.MARKET_IDS), default=None)
@click.option("--role", default=None, help="Target-language role title.")
@click.option("--template", "template_id", default=None)
@click.option("--framework", type=click.Choice(FRAMEWORK_IDS), default=None)
@click.option("--draft", "draft_flag", is_flag=True, help="Render even when target-locale facts are missing, with visible markers.")
@click.option("--yes", "confirm_flag", is_flag=True, help="Confirm a `minimum` gate result.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def localize(
    ctx: click.Context,
    application: str,
    target_locale: str,
    market: str | None,
    role: str | None,
    template_id: str | None,
    framework: str | None,
    draft_flag: bool,
    confirm_flag: bool,
    json_flag: bool,
) -> None:
    """Re-derive the resume for the other market and language. Never translates rendered text."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        source_app = load_application(root, application)
        result = localize_application(
            root,
            vault,
            source_app,
            target_locale=target_locale,
            target_market=market,
            target_role=role,
            template_id=template_id,
            framework=framework,
            draft=draft_flag,
        )
        payload: dict[str, Any] = {"ok": result.parity.status == "pass", "localize": result.to_dict()}
        if result.parity.status == "fail" and not draft_flag:
            payload["next"] = "Fix the parity failures or use --draft to inspect the marked output."
            if as_json:
                _json_out(payload)
            else:
                click.echo(f"Parity: FAIL — {result.parity_path}")
                for note in result.parity.notes:
                    click.echo(f"  {note}")
                for gap in result.gaps:
                    click.echo(f"  missing {result.target_locale}: {gap.path}")
            ctx.exit(4)

        exit_code, build_payload = _run_build(
            root,
            result.render_vault,
            result.application,
            confirm=confirm_flag,
            draft=draft_flag,
        )
        payload["build"] = build_payload
        payload["ok"] = exit_code == 0 and result.parity.status == "pass"
        if as_json:
            _json_out(payload)
        else:
            click.echo(f"Parity: {result.parity.status.upper()} — {result.parity_path}")
            click.echo(f"Target application: {result.application_path}")
            for gap in result.gaps:
                click.echo(f"  missing {result.target_locale}: {gap.path}")
            for warning in result.warnings:
                click.echo(f"  warning: {warning}")
            if build_payload.get("render"):
                click.echo(f"HTML: {build_payload['render']['html']}")
                click.echo(f"Editable preview: {build_payload['render']['editable_html']}")
            elif build_payload.get("next"):
                click.echo(build_payload["next"], err=True)
        ctx.exit(exit_code if result.parity.status == "pass" else 4)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("application")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def audit(ctx: click.Context, application: str, json_flag: bool) -> None:
    """Check the rendered HTML for parseability, layout, content, market, and privacy."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        app = load_application(root, application)
        directory = application_dir(root, app["slug"])
        render_path = directory / "render.json"
        render_data = {}
        if render_path.is_file():
            try:
                render_data = json.loads(render_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        html_path = directory / (app.get("output") or {}).get("html", "resume.html")
        draft = False
        if html_path.is_file():
            draft = 'data-draft="true"' in html_path.read_text(encoding="utf-8")
        qa = run_qa(
            root,
            vault,
            app,
            template_id=render_data.get("template_id"),
            draft=draft,
        )
        qa_path = directory / "qa.json"
        qa_path.write_text(json.dumps(qa.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        app["qa"] = {
            "status": qa.status,
            "report": str(qa_path),
            "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        save_application(root, app)
        if as_json:
            _json_out({"ok": qa.status != "fail", "report": str(qa_path), "qa": qa.to_dict()})
        else:
            _print_qa(qa)
            click.echo(f"Report: {qa_path}")
        ctx.exit(0 if qa.status != "fail" else 4)
    except ResumeProError as error:
        _handle(ctx, error)


def _version_ref(root: Path, slug: str, ref: str) -> tuple[dict[str, Any], Path]:
    directory = application_dir(root, slug)
    if ref == "current":
        return load_application(root, slug), directory
    version_dir = directory / "versions" / ref
    app_path = version_dir / "application.yaml"
    if not app_path.is_file():
        raise ResumeProError(
            "diff.version_missing",
            f"No version {ref!r} for application {slug!r}.",
            fix="Run `resume build` to create a version, then list `.resume/applications/<slug>/versions/`.",
        )
    return yaml.safe_load(app_path.read_text(encoding="utf-8")), version_dir


def _visible_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    for tag in soup(["style", "script", "noscript"]):
        tag.decompose()
    return [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]


@cli.command()
@click.argument("application")
@click.argument("version_a")
@click.argument("version_b")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def diff(ctx: click.Context, application: str, version_a: str, version_b: str, json_flag: bool) -> None:
    """Compare two versions (or `current`) of an application."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        app_a, dir_a = _version_ref(root, application, version_a)
        app_b, dir_b = _version_ref(root, application, version_b)
        facts_a = set(app_a["selection"].get("fact_ids") or [])
        facts_b = set(app_b["selection"].get("fact_ids") or [])
        bullets_a = set(app_a["selection"].get("bullet_ids") or [])
        bullets_b = set(app_b["selection"].get("bullet_ids") or [])
        sections_a = {s["id"]: (s.get("enabled"), s.get("order")) for s in app_a["selection"].get("sections") or []}
        sections_b = {s["id"]: (s.get("enabled"), s.get("order")) for s in app_b["selection"].get("sections") or []}
        section_changes = sorted(
            section
            for section in set(sections_a) | set(sections_b)
            if sections_a.get(section) != sections_b.get(section)
        )
        html_a = (app_a.get("output") or {}).get("html", "resume.html")
        html_b = (app_b.get("output") or {}).get("html", "resume.html")
        lines_a = _visible_lines(dir_a / html_a) if (dir_a / html_a).is_file() else _visible_lines(dir_a / "resume.html")
        lines_b = _visible_lines(dir_b / html_b) if (dir_b / html_b).is_file() else _visible_lines(dir_b / "resume.html")
        diff_lines = list(difflib.unified_diff(lines_a, lines_b, lineterm=""))
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        payload = {
            "ok": True,
            "application": application,
            "from": version_a,
            "to": version_b,
            "template_from": (app_a.get("template") or {}).get("id"),
            "template_to": (app_b.get("template") or {}).get("id"),
            "market_from": app_a.get("market"),
            "market_to": app_b.get("market"),
            "page_budget_from": app_a.get("page_budget"),
            "page_budget_to": app_b.get("page_budget"),
            "facts_added": sorted(facts_b - facts_a),
            "facts_removed": sorted(facts_a - facts_b),
            "bullets_added": sorted(bullets_b - bullets_a),
            "bullets_removed": sorted(bullets_a - bullets_b),
            "sections_changed": section_changes,
            "dropped_from": app_a["selection"].get("dropped") or [],
            "dropped_to": app_b["selection"].get("dropped") or [],
            "text_lines_added": added,
            "text_lines_removed": removed,
        }
        diff_path = application_dir(root, application) / f"diff-{version_a}-{version_b}.json".replace("/", "_")
        diff_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if as_json:
            _json_out({**payload, "report": str(diff_path)})
        else:
            click.echo(f"Template: {payload['template_from']} → {payload['template_to']}")
            click.echo(f"Facts: +{len(payload['facts_added'])} / -{len(payload['facts_removed'])}")
            click.echo(f"Bullets: +{len(payload['bullets_added'])} / -{len(payload['bullets_removed'])}")
            click.echo(f"Text lines: +{added} / -{removed}")
            if section_changes:
                click.echo("Sections changed: " + ", ".join(section_changes))
            click.echo(f"Report: {diff_path}")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


@cli.command()
@click.argument("image", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--app", "app_slug", default=None, help="Application slug, used to warn about market photo policy.")
@click.option("--clear", "clear_flag", is_flag=True, help="Remove the stored photo.")
@click.option("--json", "json_flag", is_flag=True, help="Emit one JSON object to stdout.")
@click.pass_context
def photo(ctx: click.Context, image: Path | None, app_slug: str | None, clear_flag: bool, json_flag: bool) -> None:
    """Store an optional portrait for the resume header. The slot is invisible when empty."""
    as_json = _json_enabled(ctx, json_flag)
    try:
        root = require_project_root()
        vault = load_vault(root=root)
        identity = vault.setdefault("identity", {})
        warnings: list[str] = []
        if clear_flag:
            identity.pop("photo", None)
            message = "Photo cleared."
        else:
            if image is None:
                raise ResumeProError(
                    "photo.missing_file",
                    "No image was provided.",
                    fix="Pass a JPEG, PNG, or WebP file, or use --clear.",
                )
            suffix = image.suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
                raise ResumeProError(
                    "photo.unsupported_format",
                    f"Unsupported image type {suffix or '(none)'}.",
                    fix="Use JPEG, PNG, or WebP.",
                )
            assets = resume_dir(root) / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            target = assets / f"photo{suffix}"
            shutil.copy2(image, target)
            identity["photo"] = str(target.resolve())
            message = f"Photo stored at {target}."
        save_vault(vault, root=root)
        if app_slug and not clear_flag:
            app = load_application(root, app_slug)
            policy = profile.load_market(app["market"]).get("photo_policy")
            if policy == "forbidden":
                warnings.append(f"Market {app['market']!r} forbids photos; the photo is stored but will be suppressed at render time.")
        payload = {"ok": True, "photo": identity.get("photo"), "message": message, "warnings": warnings}
        if as_json:
            _json_out(payload)
        else:
            click.echo(message)
            for warning in warnings:
                click.echo(f"  warning: {warning}")
            click.echo("Rebuild the application to embed the photo in the HTML.")
        ctx.exit(0)
    except ResumeProError as error:
        _handle(ctx, error)


def main() -> None:
    try:
        cli()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        click.echo("Aborted.", err=True)
        raise SystemExit(130)
    except Exception as exc:
        root = find_project_root() or Path.cwd()
        report_path = None
        try:
            reports = resume_dir(root) / "reports"
            reports.mkdir(parents=True, exist_ok=True)
            report_path = reports / f"internal-error-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json"
            report_path.write_text(
                json.dumps({"error": repr(exc), "traceback": traceback.format_exc()}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            report_path = None
        click.echo(f"7: internal error: {exc}", err=True)
        if report_path is not None:
            click.echo(f"  report: {report_path}", err=True)
        raise SystemExit(7)


if __name__ == "__main__":
    main()
