"""
Stage 03 relevance filter.

Goal: keep every section a DTIA might rely on (high recall), while
dropping genuine noise (table-of-contents lines, boilerplate, tiny
structural fragments) so the local LLM does not waste time on them.

Two levels of decision:

  * Document level — most documents here (privacy, cyber, financial,
    AML…) are inherently on-topic.  For those we keep every *substantive*
    section rather than second-guessing individual ones, which is what
    previously dropped relevant text (e.g. a Cybercrimes Act section that
    happened to hit only one keyword).

  * Section level — for broad, general documents we fall back to keyword
    signals so irrelevant sections are dropped.
"""

import re

# --------------------------------------------------------------------
# Keyword signals
# --------------------------------------------------------------------

# A single STRONG hit is enough to keep a section.
STRONG = {
    "cross-border", "cross border", "outside the republic", "transborder",
    "personal information", "personal data", "special personal",
    "data subject", "data protection", "processing of personal",
    "transfer of personal",
    "cyber", "cybersecurity", "cyber-resilience", "cyber resilience",
    "information security", "data breach", "security breach",
    "breach notification", "incident",
    "encryption", "outsourcing", "cloud",
    "money laundering", "terrorist financing", "kyc",
    "customer due diligence", "record keeping", "retention period",
}

# SUPPORTING signals — two or more distinct hits keep a section.
SUPPORT = {
    "security", "confidentiality", "integrity", "availability",
    "access control", "authentication", "breach", "compromise",
    "consent", "collection", "storage", "retain", "archive",
    "delete", "destruction", "disclosure", "sharing", "processing",
    "process", "processor", "operator", "recipient", "third party",
    "bank", "banking", "financial", "insurance", "payment", "payments",
    "credit", "investment", "customer", "client", "account",
    "governance", "notification", "notify", "report", "supervisory",
    "regulator", "authority", "information regulator", "confidential",
    "record", "records",
}

# --------------------------------------------------------------------
# Document / section classification
# --------------------------------------------------------------------

DOC_RELEVANT = re.compile(
    r"privacy|data protection|popia|paia|personal information|"
    r"cyber|information security|resilience|"
    r"financial intelligence|fica|money laundering|anti-money|aml|"
    r"payment|bank|insurance|conduct standard|joint standard|directive|"
    r"financial sector|financial advisory|advisory and intermediary|"
    r"outsourc|cloud|governance|open finance",
    re.IGNORECASE,
)

# Table-of-contents / index lines: dotted leaders like "Governance ...... 7"
DOT_LEADER = re.compile(r"\.{4,}")

DEFINITION = re.compile(r"definition|interpretation", re.IGNORECASE)

BOILERPLATE = re.compile(
    r"^\s*(short title|commencement|repeal|amendment of laws?|"
    r"table of contents|index|arrangement of sections|long title|"
    r"herroeping|kort titel|inwerkingtreding)\b",
    re.IGNORECASE,
)

# A substantive section normally has more body text than this.
MIN_TEXT = 180


def _blob(section) -> str:
    return (section.get("heading", "") + "\n" + section.get("text", "")).lower()


def matched(section):
    """All distinct keywords (strong + support) found in the section."""
    text = _blob(section)
    return sorted(k for k in (STRONG | SUPPORT) if k in text)


# Backwards-compatible alias (older callers imported `score`).
score = matched


def _signals(section):
    text = _blob(section)
    strong = sum(1 for k in STRONG if k in text)
    support = sum(1 for k in SUPPORT if k in text)
    return strong, support


def is_noise(section) -> bool:
    """True for TOC lines, boilerplate and tiny structural fragments."""
    heading = section.get("heading", "")
    text = section.get("text", "").strip()

    # Dotted-leader TOC entry (short line pointing at a page number).
    if DOT_LEADER.search(heading) and len(text) < 400:
        return True

    strong, support = _signals(section)

    # Boilerplate with no compliance signal.
    if BOILERPLATE.match(heading) and strong == 0 and support < 2:
        return True

    # Very short fragment with no signal at all.
    if len(text) < MIN_TEXT and strong == 0 and support == 0:
        return True

    return False


def document_relevant(document) -> bool:
    """Is the whole document inherently on-topic for a DTIA?"""
    title = document.get("document", "")
    if DOC_RELEVANT.search(title):
        return True
    # Otherwise judge by how many sections carry a strong signal.
    sections = document.get("sections", [])
    if not sections:
        return False
    strong_sections = sum(1 for s in sections if _signals(s)[0] >= 1)
    return strong_sections >= max(3, 0.15 * len(sections))


def keep_section(section, doc_relevant: bool) -> bool:
    """Decide whether a single section survives the filter."""
    if is_noise(section):
        return False

    # Definitions and interpretation clauses are always useful.
    if DEFINITION.search(section.get("heading", "")):
        return True

    strong, support = _signals(section)

    if doc_relevant:
        # Keep every substantive section of an on-topic document.
        return len(section.get("text", "").strip()) >= MIN_TEXT or strong >= 1

    # Broad/general document: require a real keyword signal.
    return strong >= 1 or support >= 2


def filter_document(document):
    """Return the list of sections to keep for one document."""
    doc_relevant = document_relevant(document)
    return [
        s for s in document.get("sections", [])
        if keep_section(s, doc_relevant)
    ]
