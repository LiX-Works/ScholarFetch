"""Redaction for persisted reports. Live authentication stays in the process."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

SECRET_FIELDS = {
    "api_key", "apikey", "authorization", "cookie", "cookies", "password",
    "secret", "token", "access_token", "refresh_token", "credentials",
    "profile_root", "source_path", "config_path", "request_headers",
}
URL_RE = re.compile(r"https?://[^\s<>\"']+")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
KEY_RE = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b")


def redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"}:
            return value
        host = parts.hostname or ""
        if parts.port:
            host += f":{parts.port}"
        return urlunsplit((parts.scheme, host, parts.path, "", ""))
    except ValueError:
        return "[invalid-url]"


def redact_text(value: str) -> str:
    value = URL_RE.sub(lambda match: redact_url(match.group(0)), value)
    value = EMAIL_RE.sub("[redacted-email]", value)
    value = KEY_RE.sub("[redacted-secret]", value)
    value = re.sub(r"(?i)\b(?:authorization|cookie|api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,;]+", "[redacted-auth]", value)
    return value


def sanitize(value):
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()
                if str(key).lower() not in SECRET_FIELDS and not str(key).lower().endswith("_api_key")}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value
