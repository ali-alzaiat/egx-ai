"""Scrub API keys out of any text before it is logged, stored or returned (pure)."""

import re

REDACTED = "[redacted]"

# Shapes of provider keys and the places they leak into error text (URLs, auth headers).
_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)([?&](?:api[_-]?)?key=)[^&\s'\"]+"),
    re.compile(
        r"(?i)((?:x-api-key|x-goog-api-key|api[_-]key)['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9._\-]{8,}"
    ),
)


def scrub(text: str, *secrets: str) -> str:
    """Remove each exact secret, then anything shaped like a provider key, from ``text``."""
    out = text
    for secret in secrets:
        if len(secret) >= 4:
            out = out.replace(secret, REDACTED)
    for pattern in _PATTERNS:
        if pattern.groups:
            out = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", out)
        else:
            out = pattern.sub(REDACTED, out)
    return out
