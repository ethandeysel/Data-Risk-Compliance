"""
Prompt for legislative compliance extraction (DTIA knowledge base).

The output schema is kept to the fields that actually drive DTIA querying
and citation.  Removed vs. the original: actors, keywords, per-requirement
booleans, trigger and applies_to — none of which were surfaced in the
workbook.  Summaries and requirements are asked for in full (not clipped
for speed) since extraction now runs on a GPU.

Controlled vocabularies are kept (compressed) so categories, topics and
data types stay consistent enough to filter on.
"""

CATEGORIES = [
    "Definitions", "Cross-border Transfer",
    "International Data Transfer Mechanisms", "International Processing",
    "Security", "Third Party Processing", "Cloud Services",
    "Data Collection", "Processing", "Data Sharing", "Data Storage",
    "Retention", "Deletion", "Data Subject Rights", "Consent",
    "Special Personal Information", "Children", "Customer Information",
    "Employee Information", "Financial Data", "KYC", "AML",
    "Incident Reporting", "Breach Notification", "Governance",
    "Record Keeping", "Regulator Powers", "Enforcement", "Exemptions",
    "Other",
]

TOPICS = [
    "Cross-border Transfer", "International Processing", "Data Storage",
    "Data Residency", "Security", "Encryption", "Access Control",
    "Processing", "Collection", "Retention", "Deletion", "Data Sharing",
    "Third Party Processing", "Outsourcing", "Cloud Services",
    "Incident Reporting", "Breach Notification", "Consent",
    "Customer Information", "Employee Information",
    "Special Personal Information", "Children", "Financial Data",
    "KYC", "AML", "Governance", "Record Keeping",
]

DATA_TYPES = [
    "Personal Information", "Financial Data", "Customer Data",
    "Employee Data", "Health Data", "Children's Data",
    "Biometric Data", "Special Personal Information",
]

OBLIGATION_TYPES = [
    "Must", "Must Not", "May", "Should", "Condition",
    "Notification", "Authorisation", "Restriction",
]


SYSTEM_PROMPT = f"""You are a legal compliance analyst building a searchable database for Data Transfer Impact Assessments (DTIAs).

Convert each legislative section into structured JSON. Rules:
- Analyse each section independently.
- Extract only what is explicitly stated. Never infer obligations, regulators, penalties or legal advice. If something is not explicit, use "" or [].
- Country, Act, Chapter, Part and Pages are context — do not repeat them in summaries.
- Ignore page headers, indexes, tables of contents, editorial/historical notes and repealed provisions. Do NOT ignore definitions.

Return VALID JSON ONLY, no markdown or commentary, in this exact shape:
{{"extractions":[{{"section":"","primary_category":"","summary":"","dtia_summary":"","financial_relevance":"","confidence":"","topics":[],"data_types":[],"requirements":[{{"text":"","obligation_type":""}}],"authority":"","source_quote":""}}]}}

Field rules:
- section: the section identifier given to you.
- primary_category: EXACTLY ONE of: {", ".join(CATEGORIES)}.
- summary: 2-4 complete sentences (roughly 40-90 words) stating what the section actually does — the specific obligations, prohibitions, permissions and conditions it creates, and who they apply to. Be concrete and self-contained; do NOT merely restate the heading or write "this section deals with X".
- dtia_summary: 1-3 sentences on why this section matters for a Data Transfer Impact Assessment — the specific safeguards, conditions or restrictions bearing on transferring, storing or processing data across borders or with third parties. "" only if genuinely irrelevant to a DTIA.
- financial_relevance: ONE of High | Medium | Low | None. High = directly concerns financial institutions, banks, insurers, payment providers, investment firms/funds, securities, capital markets, AML/CFT, or the handling or taxation of financial or customer-financial data. Medium = applies to business generally but has clear financial-sector implications. Low = only incidental. None = no financial angle at all.
- confidence: High (explicit) | Medium (minor interpretation) | Low (ambiguous).
- topics: only topics the section SUBSTANTIVELY addresses (usually 1-4), not everything tangentially mentioned. Only from: {", ".join(TOPICS)}.
- data_types: only data types the section actually governs, only from: {", ".join(DATA_TYPES)}.
- requirements: list EVERY legally operative statement as its own object — each obligation, prohibition, permission, condition, notification duty, safeguard, record-keeping rule or cross-border condition. Be exhaustive: a substantive section usually yields several. Do NOT merge distinct statements, and do NOT pad with non-operative narration. Each text is a clear, self-contained paraphrase (or short quote) of the rule. obligation_type is ONE of: {", ".join(OBLIGATION_TYPES)}. Use [] only when the section is purely definitional or narrative with no operative rule.
- authority: explicitly named regulator/authority only, else "".
- source_quote: shortest supporting passage, verbatim, <=40 words.

Return one extraction object per section provided."""


def build_prompt(sections, country, act):

    lines = [f"COUNTRY: {country}", f"ACT: {act}", ""]

    for s in sections:
        lines.append("----------")
        for label, key in (
            ("CHAPTER", "chapter"),
            ("PART", "part"),
            ("CONDITION", "condition"),
        ):
            value = s.get(key)
            if value:
                lines.append(f"{label}: {value}")
        lines.append(f"SECTION: {s['identifier']}")
        lines.append(f"HEADING: {s.get('heading', '')}")
        lines.append(
            f"PAGES: {s.get('page_start', '')}-{s.get('page_end', '')}"
        )
        lines.append("TEXT:")
        lines.append(s.get("text", ""))
        lines.append("")

    return "\n".join(lines)
