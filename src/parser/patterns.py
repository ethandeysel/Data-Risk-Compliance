import re

# -----------------------------
# Structural elements
# -----------------------------

CHAPTER_PATTERN = re.compile(
    r"CHAPTER\s+\d+[A-Z]?",
    re.IGNORECASE,
)

PART_PATTERN = re.compile(
    r"Part\s+[A-Z]",
    re.IGNORECASE,
)

CONDITION_PATTERN = re.compile(
    r"Condition\s+\d+",
    re.IGNORECASE,
)

# Matches:
# 19. Security measures...
SECTION_PATTERN = re.compile(
    r"(?m)^(\d+)\.\s+([^\n]+)"
)

# Page numbers that appear alone
PAGE_NUMBER_PATTERN = re.compile(
    r"(?m)^\d+\s*$"
)

# Gazette headers
GAZETTE_PATTERN = re.compile(
    r"GOVERNMENT GAZETTE.*?$",
    re.MULTILINE | re.IGNORECASE,
)

ACT_HEADER_PATTERN = re.compile(
    r"Act No\.\s+\d+\s+of\s+\d{4}",
    re.IGNORECASE,
)