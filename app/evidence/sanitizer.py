import re
from typing import Any

MAX_TEXT_LENGTH = 4000

SENSITIVE_KEY_PATTERN = re.compile(
    r"(password|passwd|secret|api[_-]?key|token)",
    re.IGNORECASE,
)

SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?P<key>password|passwd|secret|api[_-]?key|token)"
    r"(\s*[:=]\s*)"
    r"(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)

BEARER_TOKEN_PATTERN = re.compile(
    r"(Authorization\s*:\s*Bearer\s+)"
    r"(?P<token>[^\s]+)",
    re.IGNORECASE,
)


def sanitize_text(text: str) -> str:
    sanitized = SENSITIVE_VALUE_PATTERN.sub(
        lambda match: f"{match.group('key')}=[REDACTED]",
        text,
    )

    sanitized = BEARER_TOKEN_PATTERN.sub(
        r"\1[REDACTED]",
        sanitized,
    )

    if len(sanitized) > MAX_TEXT_LENGTH:
        sanitized = sanitized[: MAX_TEXT_LENGTH - len("[TRUNCATED]")] + "[TRUNCATED]"

    return sanitized


def sanitize_mapping(data: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}

    for key, value in data.items():
        if SENSITIVE_KEY_PATTERN.search(str(key)):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_mapping(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_mapping(item)
                if isinstance(item, dict)
                else sanitize_text(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        elif isinstance(value, str):
            sanitized[key] = sanitize_text(value)
        else:
            sanitized[key] = value

    return sanitized
