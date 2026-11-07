# SPDX-License-Identifier: MIT
"""Default redaction of personal identifiers from stdout JSON and logs.

The contract redacts phone, email, ID number, and home address from what the
CLI prints (which an agent/model may see). Local report files on disk keep the
full data; redaction only applies to emitted output unless --include-pii is set.
"""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Keys whose values are personal identifiers. Matched case-insensitively.
_PII_KEYS = {
    "email",
    "phone",
    "telephone",
    "mobile",
    "id_number",
    "id_card",
    "national_id",
    "home_address",
    "address",
    "street",
    "street_address",
}

# Unambiguous patterns safe to redact inside free text.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_CN_ID_RE = re.compile(r"(?<![0-9])[0-9]{17}[0-9Xx](?![0-9])")


def _redact_text(value: str) -> str:
    value = _EMAIL_RE.sub(REDACTED, value)
    value = _CN_ID_RE.sub(REDACTED, value)
    return value


def redact_pii(data: Any) -> Any:
    """Return a copy of ``data`` with personal identifiers masked.

    Structured PII fields (email, phone, ID number, home address) are masked by
    key; email addresses and Chinese ID numbers are also masked wherever they
    appear in string values. Names and cities are intentionally preserved.
    """
    if isinstance(data, dict):
        result: dict[str, Any] = {}
        for key, value in data.items():
            if str(key).lower() in _PII_KEYS and value not in (None, "", [], {}):
                result[key] = REDACTED
            else:
                result[key] = redact_pii(value)
        return result
    if isinstance(data, (list, tuple)):
        return [redact_pii(item) for item in data]
    if isinstance(data, str):
        return _redact_text(data)
    return data