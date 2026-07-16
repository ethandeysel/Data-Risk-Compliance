"""
Loads the extracted compliance JSON (stage 04) into the datasets the
Excel exporter needs: one flat row per section (with page references for
citation), plus per-act / per-regulator / per-topic rollups and the
value lists used for the Query sheet dropdowns.
"""

from pathlib import Path
import json
import os
import urllib.parse

import pandas as pd

# Base URL the Source link points at.  Defaults to the GitHub copy so the
# link works even when the workbook is not on the machine that holds the
# PDFs; override with PDF_BASE_URL (e.g. a local "file:///…/" path).
PDF_BASE_URL = os.getenv(
    "PDF_BASE_URL",
    "https://github.com/ethandeysel/Data-Risk-Compliance/blob/main/",
)


# Column order for the Compliance Database / Query result.  Kept
# query-friendly: identity first, then the fields a DTIA answer cites.
COLUMNS = [
    "Country", "Act", "Section", "Heading", "Pages",
    "Financial Relevance", "Confidence", "Topics", "Data Types",
    "Authority", "Summary", "DTIA Summary", "Requirements",
    "Source Quote", "Source",
]


def _pages(section):
    start = section.get("page_start")
    end = section.get("page_end")
    if start is None:
        return ""
    if end and end != start:
        return f"{start}–{end}"
    return str(start)


# Safety cap on a single requirement's length — high enough that real
# requirements show in full and only a pathologically long one is trimmed
# (the prompt already asks for concise, ~20-word requirements).
_REQ_MAX_CHARS = int(os.getenv("REQUIREMENT_MAX_CHARS", "350"))


def _one_line(text):
    text = " ".join(text.split())  # collapse any internal newlines/spaces
    if len(text) > _REQ_MAX_CHARS:
        text = text[:_REQ_MAX_CHARS - 1].rstrip() + "…"
    return text


def _requirements_text(section):
    """Render a section's requirements as a bulleted checklist, one line
    each (truncated to keep rows manageable)."""
    parts = []
    for req in section.get("requirements", []):
        if isinstance(req, dict):
            text = req.get("text", "").strip()
            otype = req.get("obligation_type", "").strip()
            if not text:
                continue
            prefix = f"• [{otype}] " if otype else "• "
            parts.append(prefix + _one_line(text))
        elif str(req).strip():
            parts.append("• " + _one_line(str(req).strip()))
    return "\n".join(parts)


def _source_url(country, act):
    """Link to the source PDF (GitHub by default; see PDF_BASE_URL)."""
    rel = f"data/acts/{country}/{act}.pdf"
    return PDF_BASE_URL + urllib.parse.quote(rel)


class DataLoader:

    def __init__(self, extracted_folder="data/extracted"):
        self.folder = Path(extracted_folder)
        self.rows = []
        self.acts = {}
        self.regulators = {}
        self.topics = {}
        self.data_types = {}
        self.categories = {}
        self.countries = set()

    # -----------------------------------------------------------------

    def load(self):
        if not self.folder.exists():
            raise FileNotFoundError(f"{self.folder} does not exist.")

        for path in sorted(self.folder.rglob("*.json")):
            self._load_document(path)

        self.df = pd.DataFrame(self.rows, columns=COLUMNS)
        if not self.df.empty:
            self.df.sort_values(
                ["Country", "Act", "Section"], inplace=True,
                key=lambda col: col.map(_natural_key)
                if col.name == "Section" else col,
            )
        return self

    # -----------------------------------------------------------------

    def _load_document(self, path):
        with open(path, encoding="utf-8") as f:
            document = json.load(f)

        country = document.get("country", "Unknown")
        act = document.get("document", path.stem)
        self.countries.add(country)

        act_key = (country, act)
        act_row = self.acts.setdefault(act_key, {
            "Country": country, "Act": act, "Sections": 0,
            "Regulators": set(), "Topics": set(), "Data Types": set(),
            "Financial Relevance": "",
        })

        for section in document.get("sections", []):
            self._process_section(country, act, act_row, section)

    # -----------------------------------------------------------------

    def _process_section(self, country, act, act_row, section):
        act_row["Sections"] += 1

        authority = section.get("authority", "")
        if authority:
            act_row["Regulators"].add(authority)
            reg = self.regulators.setdefault(
                authority, {"Country": set(), "Acts": set()}
            )
            reg["Country"].add(country)
            reg["Acts"].add(act)

        relevance = section.get("financial_relevance", "")
        if relevance and relevance not in ("None", "Unknown"):
            # Keep the highest relevance seen for the act.
            act_row["Financial Relevance"] = _max_relevance(
                act_row["Financial Relevance"], relevance
            )

        category = section.get("primary_category", "")
        if category:
            self.categories[category] = self.categories.get(category, 0) + 1

        topics = section.get("topics", []) or []
        for topic in topics:
            act_row["Topics"].add(topic)
            self.topics[topic] = self.topics.get(topic, 0) + 1

        dtypes = section.get("data_types", []) or []
        for dtype in dtypes:
            act_row["Data Types"].add(dtype)
            self.data_types[dtype] = self.data_types.get(dtype, 0) + 1

        self.rows.append({
            "Country": country,
            "Act": act,
            "Section": section.get("section", ""),
            # Prefer the model's plain-language title; fall back to the raw
            # parsed heading (which is blank/uninformative for many docs).
            "Heading": section.get("title") or section.get("heading", ""),
            "Pages": _pages(section),
            "Category": category,
            "Financial Relevance": relevance,
            "Confidence": section.get("confidence", ""),
            "Topics": ", ".join(topics),
            "Data Types": ", ".join(dtypes),
            "Authority": authority,
            "Summary": section.get("summary", ""),
            "DTIA Summary": section.get("dtia_summary", ""),
            "Requirements": _requirements_text(section),
            "Source Quote": section.get("source_quote", ""),
            "Source": _source_url(country, act),
        })

    # -----------------------------------------------------------------

    def summary(self):
        return {
            "countries": len(self.countries),
            "acts": len(self.acts),
            "regulators": len(self.regulators),
            "topics": len(self.topics),
            "rows": len(self.rows),
        }

    @property
    def country_list(self):
        return sorted(self.countries)

    @property
    def topic_list(self):
        return sorted(self.topics.keys())

    @property
    def regulator_list(self):
        return sorted(self.regulators.keys())

    @property
    def datatype_list(self):
        return sorted(self.data_types.keys())

    @property
    def category_list(self):
        return sorted(self.categories.keys())

    @property
    def relevance_list(self):
        order = ["High", "Medium", "Low", "None"]
        return [r for r in order if any(
            row["Financial Relevance"] == r for row in self.rows
        )]


# ---------------------------------------------------------------------

_RELEVANCE_RANK = {"": 0, "None": 0, "Low": 1, "Medium": 2, "High": 3}


def _max_relevance(a, b):
    return a if _RELEVANCE_RANK.get(a, 0) >= _RELEVANCE_RANK.get(b, 0) else b


def _natural_key(value):
    """Zero-pad numbers so identifiers sort naturally (2 < 10 < 10A)."""
    import re
    return re.sub(r"\d+", lambda m: m.group().zfill(6), str(value))
