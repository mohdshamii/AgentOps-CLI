"""
Secret masking and sensitive data leak prevention.
"""

import os
import re
from typing import List, Optional

# Common regex patterns for credentials and tokens
SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),                         # OpenAI/Anthropic keys
    re.compile(r"(AIza[0-9A-Za-z-_]{35})"),                       # Google API keys
    re.compile(r"(ghp_[a-zA-Z0-9]{36})"),                         # GitHub tokens
    re.compile(r"(glpat-[a-zA-Z0-9\-_]{20,})"),                   # GitLab tokens
    re.compile(r"(bearer\s+[a-zA-Z0-9_\-\.]{20,})", re.IGNORECASE), # Bearer tokens
    re.compile(r"(password\s*[:=]\s*['\"][^'\"]+['\"])", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"])", re.IGNORECASE),
]


def mask_secrets(text: str, custom_secrets: Optional[List[str]] = None) -> str:
    """Masks known sensitive values and common token patterns in output strings."""
    if not text:
        return text

    masked = text

    # Mask known environment variable values
    env_keys_to_mask = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_API_KEY",
    ]
    for key in env_keys_to_mask:
        val = os.getenv(key)
        if val and len(val) >= 4:
            masked = masked.replace(val, f"[{key}_REDACTED]")

    # Mask any custom provided secret strings
    if custom_secrets:
        for secret in custom_secrets:
            if secret and len(secret) >= 4:
                masked = masked.replace(secret, "[SECRET_REDACTED]")

    # Pattern replacements
    for pattern in SECRET_PATTERNS:
        masked = pattern.sub("[REDACTED_CREDENTIAL]", masked)

    return masked

