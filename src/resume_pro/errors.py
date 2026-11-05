# SPDX-License-Identifier: MIT
"""Shared error and issue types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    code: str
    path: str
    message: str
    fix: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "fix": self.fix,
            "severity": self.severity,
        }


class ResumeProError(Exception):
    """An error with a stable code, a path, and a concrete fix."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        path: str = "",
        fix: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.fix = fix
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "path": self.path,
            "message": self.message,
            "fix": self.fix,
            "details": self.details,
        }

    def render(self) -> str:
        lines = [f"{self.code}: {self.path + ': ' if self.path else ''}{self.message}"]
        if self.fix:
            lines.append(f"  fix: {self.fix}")
        return "\n".join(lines)


class VaultError(ResumeProError):
    pass


class IntakeError(ResumeProError):
    pass


class GateError(ResumeProError):
    pass


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity != "error"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
        }
