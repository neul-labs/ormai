"""
Input sanitization for audit logging.

Provides functions to detect and redact sensitive data from inputs.
"""

import re
from typing import Any

# Regex patterns for detecting sensitive data in field names
# Matches common patterns like: password, pwd, p@ss, api_key, etc.
SENSITIVE_PATTERNS = re.compile(
    r"(?i)("
    r"password|pwd|passwd|pass|wpa|wap|"
    r"secret|private|private_key|"
    r"token|access_token|auth_token|refresh_token|bearer|"
    r"api_?key|apikey|api_?secret|"
    r"credential|user_id|"
    r"session|session_id|sid|"
    r"oauth|client_?secret|"
    r"card|cc_?num|cvv|cvc|"
    r"ssn|social_?security|"
    r"jwt"
    r")"
)


def sanitize_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitize sensitive data from inputs.

    Args:
        inputs: Dictionary of input values to sanitize

    Returns:
        Dictionary with sensitive values redacted
    """

    def sanitize_value(key: str, value: Any) -> Any:
        """Recursively sanitize a value, redacting sensitive fields."""
        if SENSITIVE_PATTERNS.search(key):
            return "[REDACTED]"
        elif isinstance(value, dict):
            return {k: sanitize_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [sanitize_value(str(i), v) for i, v in enumerate(value)]
        else:
            return value

    return {key: sanitize_value(key, value) for key, value in inputs.items()}
