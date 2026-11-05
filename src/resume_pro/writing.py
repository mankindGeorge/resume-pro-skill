# SPDX-License-Identifier: MIT
"""Writing frameworks and explicit consent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ResumeProError


@dataclass(frozen=True)
class Framework:
    id: str
    label: str
    summary: str
    brief: str
    best_for: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "summary": self.summary,
            "brief": self.brief,
            "best_for": self.best_for,
        }


FRAMEWORKS: dict[str, Framework] = {
    "star": Framework(
        "star",
        "STAR",
        "Situation, Task, Action, Result.",
        "For each bullet: state the situation and task briefly, describe the action you personally took, then end with a measurable result.",
        "Behavioral interviews and early-career bullets",
    ),
    "xyz": Framework(
        "xyz",
        "XYZ",
        "Accomplished X, measured by Y, by doing Z.",
        "Start with the outcome (X), attach a measure (Y), then name the action (Z). Keep the measure real or omit it.",
        "Engineering and data roles",
    ),
    "fab": Framework(
        "fab",
        "FAB",
        "Feature, Advantage, Benefit.",
        "Name what you built, why it was better, and what changed for the user or business.",
        "Product, design, and customer-facing roles",
    ),
    "car": Framework(
        "car",
        "CAR",
        "Challenge, Action, Result.",
        "Lead with the challenge, describe your action, and close with the result. Good when the context matters.",
        "Cross-functional and problem-solving roles",
    ),
    "result_first": Framework(
        "result_first",
        "Result first",
        "Lead with the outcome, then the action.",
        "Put the result in the first clause. Add enough action detail to make the result credible.",
        "Experienced candidates and dense resumes",
    ),
    "user_voice": Framework(
        "user_voice",
        "User voice",
        "Keep the candidate's own phrasing and tone.",
        "Tighten the candidate's wording without replacing their voice. Do not add corporate language.",
        "Candidates with a distinctive voice or creative roles",
    ),
}

FRAMEWORK_IDS = tuple(FRAMEWORKS)


class WritingError(ResumeProError):
    pass


def get_framework(framework_id: str | None) -> Framework:
    if not framework_id:
        raise WritingError(
            "writing.framework_missing",
            "No writing framework was chosen.",
            fix="Choose one of: " + ", ".join(FRAMEWORK_IDS) + ".",
        )
    framework = FRAMEWORKS.get(framework_id)
    if framework is None:
        raise WritingError(
            "writing.framework_unknown",
            f"Unknown writing framework {framework_id!r}.",
            fix="Choose one of: " + ", ".join(FRAMEWORK_IDS) + ".",
        )
    return framework


def require_consent(framework_id: str | None, consent: bool) -> Framework:
    framework = get_framework(framework_id)
    if not consent:
        raise WritingError(
            "writing.consent_missing",
            f"The user has not consented to the {framework.label} framework.",
            fix="Ask the user to choose a framework before rewriting; never apply one silently.",
        )
    return framework


def framework_brief(framework_id: str) -> str:
    return get_framework(framework_id).brief


def frameworks_payload() -> list[dict[str, Any]]:
    return [framework.to_dict() for framework in FRAMEWORKS.values()]
