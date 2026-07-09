import re

from .patterns import (
    PAGE_NUMBER_PATTERN,
    GAZETTE_PATTERN,
    ACT_HEADER_PATTERN,
)


def clean_page(text: str) -> str:
    """
    Clean a single extracted page.
    """

    # OCR ligatures
    replacements = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "’": "'",
        "“": '"',
        "”": '"',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Remove Gazette headers
    text = GAZETTE_PATTERN.sub("", text)

    # Remove Act headers
    text = ACT_HEADER_PATTERN.sub("", text)

    # Remove isolated page numbers
    text = PAGE_NUMBER_PATTERN.sub("", text)

    # Remove repeated blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove line numbers that appear on their own
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)

    # Remove repeated whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove page headers like "No. 37067"
    text = re.sub(r"No\.\s+\d+", "", text)

    # Remove Government Gazette text
    text = re.sub(
        r"GOVERNMENT GAZETTE.*",
        "",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()

