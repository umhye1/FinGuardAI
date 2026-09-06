import re

PATTERNS = [
    (re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I), "[EMAIL]"),
    (re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)"), "[ID_NUMBER]"),
    (re.compile(r"(?<!\d)(?:\+82[- ]?|0)1[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)"), "[PHONE]"),
    (re.compile(r"(?<!\d)\d{2,6}[- ]\d{2,6}[- ]\d{2,8}(?!\d)"), "[NUMBER]"),
]


def mask(text: str) -> str:
    """Baseline only: not a complete PII detector or a promise of anonymization."""
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text
