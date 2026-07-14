import re

from .patterns import (
    PAGE_NUMBER_PATTERN,
    GAZETTE_PATTERN,
    ACT_HEADER_PATTERN,
)

# A line that is nothing but a number.
_ISOLATED_NUMBER = re.compile(r"^\s*\d+\s*$")


def _strip_edge_numbers(text: str) -> str:
    """Drop isolated numbers only in the page's header/footer zone.

    Page numbers live in the first/last few non-empty lines of a page; a
    bare number mid-page is a Style-C section marker (UK/AU
    legislation.gov.uk exports, e.g. "1\\nUnauthorised access…") and must
    survive so the parser can split on it.
    """
    lines = text.split("\n")
    nonempty = [i for i, line in enumerate(lines) if line.strip()]
    if not nonempty:
        return text
    zone = set(nonempty[:3]) | set(nonempty[-2:])
    return "\n".join(
        "" if (i in zone and _ISOLATED_NUMBER.match(line)) else line
        for i, line in enumerate(lines)
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

    # Remove isolated page numbers, but keep mid-page section numbers so
    # the Style-C parser can split on them (see _strip_edge_numbers).
    text = _strip_edge_numbers(text)

    # Remove repeated blank lines
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

