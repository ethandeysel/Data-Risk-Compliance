"""
Section relevance scoring for the DTIA database.

A separate, cheap LLM pass over the *already-extracted* sections.  Where
stage 04 reads the full section text, this reads only the model's own
summary + heading + topics — a short prompt, so it runs far faster than
extraction — and rates how relevant the section is to a cyber-security /
data-protection consultancy answering client data-compliance questions.

The score is written back into the extracted JSON (`relevance_score`,
`relevance_reason`) so the Excel exporter can show it as a column and a
"minimum relevance" filter.  Scores flag rather than delete: nothing is
lost, you choose the cut in the workbook.

Rubric (0-3)
  3  Core: data protection / privacy, cross-border transfer, breach
     notification, cyber / information-security obligations, data-subject
     rights, consent, retention / erasure, or financial-data (AML/KYC)
     handling.
  2  Supporting: definitions of those terms, the regulator and its powers,
     penalties / enforcement, record-keeping, audit, outsourcing / third
     parties, licensing conditions that involve data.
  1  Tangential: general governance / procedure that only sometimes bears
     on data compliance.
  0  Irrelevant: commencement / assent dates, quorum, officials' pay /
     leave, pure amendment mechanics, or unrelated subject matter (tax
     administration, share capital, company structure, …).
"""

import os

from .client import generate
from .extractor import parse_json

SYSTEM_PROMPT = (
    "You classify sections of legislation and regulatory guidance for a "
    "database that a cyber-security and data-protection consultancy uses to "
    "answer client questions about data compliance and cross-border data "
    "transfers. Rate each section's relevance to that purpose on a 0-3 "
    "scale.\n"
    "3 = core: data protection/privacy, cross-border data transfer, breach "
    "notification, cyber/information-security duties, data-subject rights, "
    "consent, data retention/erasure, or financial-data (AML/KYC) handling.\n"
    "2 = supporting: definitions of those terms, the regulator/authority and "
    "its powers, penalties/enforcement, record-keeping, audit, "
    "outsourcing/third-party, or licensing conditions involving data.\n"
    "1 = tangential: general governance or procedure that only sometimes "
    "bears on data compliance.\n"
    "0 = irrelevant: commencement/assent dates, quorum, officials' pay or "
    "leave, pure amendment mechanics (\"omit X, substitute Y\"), or unrelated "
    "subject matter such as tax administration, share capital or company "
    "structure.\n"
    'Reply with ONLY JSON: {"score": <0-3 integer>, "reason": "<=10 words"}.'
)

# When scoring fails we keep the section (score 2) rather than risk hiding
# something relevant — recall matters more than precision here.
_FALLBACK_SCORE = 2


def _clip(text, limit):
    text = " ".join(str(text or "").split())
    return text[:limit]


# How many requirement bullets to show the scorer.  The obligations are
# the clearest signal of what a section actually does, so we include a
# generous sample (capped to keep the prompt short and fast).
_MAX_REQS = int(os.getenv("RELEVANCE_MAX_REQS", "8"))


def build_prompt(section, country, act):
    heading = section.get("title") or section.get("heading", "")
    topics = ", ".join(section.get("topics", []) or [])
    dtypes = ", ".join(section.get("data_types", []) or [])
    reqs = []
    for r in section.get("requirements", []):
        if isinstance(r, dict) and r.get("text"):
            otype = str(r.get("obligation_type", "")).strip()
            prefix = f"[{otype}] " if otype else ""
            reqs.append(prefix + r["text"])
        if len(reqs) >= _MAX_REQS:
            break
    lines = [
        f"Country: {country}",
        f"Act: {act}",
        f"Section: {section.get('section', '')}",
        f"Heading: {_clip(heading, 200)}",
        f"Summary: {_clip(section.get('summary', ''), 600)}",
    ]
    if topics:
        lines.append(f"Topics: {_clip(topics, 200)}")
    if dtypes:
        lines.append(f"Data types: {_clip(dtypes, 200)}")
    if reqs:
        n = len(section.get("requirements", []))
        label = (f"Requirements ({len(reqs)} of {n} shown):"
                 if n > len(reqs) else "Requirements:")
        lines.append(label)
        lines.extend(f"- {_clip(r, 160)}" for r in reqs)
    lines.append("\nScore this section 0-3 on relevance to a data-compliance "
                 "database, considering the requirements above.")
    return "\n".join(lines)


def score_section(section, country, act):
    """Return (score:int 0-3, reason:str).  Never raises."""
    prompt = build_prompt(section, country, act)
    try:
        result = parse_json(generate(SYSTEM_PROMPT, prompt))
        score = int(result.get("score"))
        if score < 0 or score > 3:
            raise ValueError(f"score {score} out of range")
        reason = str(result.get("reason", "")).strip()[:120]
        return score, reason
    except Exception as e:
        return _FALLBACK_SCORE, f"[scoring failed: {type(e).__name__}]"
