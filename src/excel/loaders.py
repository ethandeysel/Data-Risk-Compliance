"""
Loads the extracted compliance JSON (stage 04) into the datasets the
Excel exporter needs: one flat row per section (with page references for
citation), plus per-act / per-regulator / per-topic rollups and the
value lists used for the Query sheet dropdowns.

Post-processing (all on by default, toggle with env vars) cleans the raw
4b output before it reaches the workbook:
  * POST_FIN_FLOOR  — a section with a financial topic/keyword can't stay
                      financial_relevance "None"
  * POST_DEDUP      — drop content-identical duplicate rows within an act
                      (the parser's page-split parts often extract the same)
  * POST_DROP_NOISE — drop sections with no topics, requirements, DTIA
                      summary or authority (definitions / stray page text)
"""

from pathlib import Path
import json
import os
import re
import urllib.parse

import pandas as pd

# Where the Source link points.  "acts" (default) = an internal link to the
# section's row on the Acts sheet (always works, wherever the workbook
# lives).  "pdf" = the GitHub copy of the source PDF (see PDF_BASE_URL).
SOURCE_LINK = os.getenv("SOURCE_LINK", "acts").lower()
PDF_BASE_URL = os.getenv(
    "PDF_BASE_URL",
    "https://github.com/ethandeysel/Data-Risk-Compliance/blob/main/",
)

# Post-processing toggles.
POST_FIN_FLOOR = os.getenv("POST_FIN_FLOOR", "1") == "1"
POST_DEDUP = os.getenv("POST_DEDUP", "1") == "1"
POST_DROP_NOISE = os.getenv("POST_DROP_NOISE", "1") == "1"


# Column order for the Compliance Database / Query result.  Kept
# query-friendly: identity first, then the fields a DTIA answer cites.
COLUMNS = [
    "Country", "Act", "Section", "Heading", "Pages",
    "Financial Relevance", "Confidence", "Topics", "Data Types",
    "Authority", "Summary", "DTIA Summary",
    "Requirements", "Requirements (2)",
    "Source Quote", "Source",
]

# The two Requirements columns split a section's checklist in half so rows
# are ~half as tall (less vertical scrolling).
REQ_COLS = ("Requirements", "Requirements (2)")

# Topics that make a section financially relevant on their own.
_FIN_TOPICS = {"Financial Data", "KYC", "AML", "Customer Information"}
_FIN_KEYWORDS = re.compile(
    r"\b(bank|insur|payment|financ|invest|securit|taxation|credit|"
    r"monetary|deposit|lending)", re.IGNORECASE,
)


def _pages(section):
    start = section.get("page_start")
    end = section.get("page_end")
    if start is None:
        return ""
    if end and end != start:
        return f"{start}–{end}"
    return str(start)


# Safety cap on a single requirement's length — high enough that real
# requirements show in full and only a pathologically long one is trimmed.
_REQ_MAX_CHARS = int(os.getenv("REQUIREMENT_MAX_CHARS", "350"))


def _one_line(text):
    text = " ".join(text.split())  # collapse any internal newlines/spaces
    if len(text) > _REQ_MAX_CHARS:
        text = text[:_REQ_MAX_CHARS - 1].rstrip() + "…"
    return text


def _requirement_bullets(section):
    """One '• …' line per requirement (truncated to keep rows manageable)."""
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
    return parts


def _requirements_split(section):
    """Split the checklist into two roughly equal columns."""
    bullets = _requirement_bullets(section)
    half = (len(bullets) + 1) // 2
    return "\n".join(bullets[:half]), "\n".join(bullets[half:])


def _pdf_url(country, act):
    rel = f"data/acts/{country}/{act}.pdf"
    return PDF_BASE_URL + urllib.parse.quote(rel)


def _reqs(row):
    """Combined requirements text across both columns."""
    return (str(row["Requirements"]) + "\n" + str(row["Requirements (2)"]))


def _financial_signal(row):
    """'topic' if the section carries a financial topic, 'keyword' if only
    its text hints financial, else None."""
    topics = {t.strip() for t in row["Topics"].split(",") if t.strip()}
    if topics & _FIN_TOPICS:
        return "topic"
    blob = f"{row['Heading']} {row['Summary']} {_reqs(row)}"
    return "keyword" if _FIN_KEYWORDS.search(blob) else None


def _signal_score(row):
    """How many of topics/requirements/DTIA-summary/authority are present."""
    return sum([
        bool(str(row["Topics"]).strip()),
        bool(_reqs(row).strip()),
        bool(str(row["DTIA Summary"]).strip()),
        bool(str(row["Authority"]).strip()),
    ])


class DataLoader:

    def __init__(self, extracted_folder="data/extracted"):
        self.folder = Path(extracted_folder)
        self.rows = []
        self.acts = {}
        self.regulators = {}
        self.topics = {}
        self.data_types = {}
        self.countries = set()
        self.raw_rows = 0

    # -----------------------------------------------------------------

    def load(self):
        if not self.folder.exists():
            raise FileNotFoundError(f"{self.folder} does not exist.")

        for path in sorted(self.folder.rglob("*.json")):
            self._load_document(path)

        self.raw_rows = len(self.rows)
        self._postprocess()
        self._build_rollups()
        self._set_source_links()

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
        for section in document.get("sections", []):
            self._process_section(country, act, section)

    def _process_section(self, country, act, section):
        topics = section.get("topics", []) or []
        dtypes = section.get("data_types", []) or []
        req1, req2 = _requirements_split(section)
        self.rows.append({
            "Country": country,
            "Act": act,
            "Section": section.get("section", ""),
            # Prefer the model's plain-language title; fall back to the raw
            # parsed heading (blank/uninformative for many docs).
            "Heading": section.get("title") or section.get("heading", ""),
            "Pages": _pages(section),
            "Financial Relevance": section.get("financial_relevance", ""),
            "Confidence": section.get("confidence", ""),
            "Topics": ", ".join(topics),
            "Data Types": ", ".join(dtypes),
            "Authority": section.get("authority", ""),
            "Summary": section.get("summary", ""),
            "DTIA Summary": section.get("dtia_summary", ""),
            "Requirements": req1,
            "Requirements (2)": req2,
            "Source Quote": section.get("source_quote", ""),
            "Source": "",
        })

    # -----------------------------------------------------------------
    # Post-processing
    # -----------------------------------------------------------------

    def _postprocess(self):
        if POST_FIN_FLOOR:
            for r in self.rows:
                if str(r["Financial Relevance"]).strip() in (
                        "", "None", "Unknown"):
                    sig = _financial_signal(r)
                    if sig == "topic":
                        r["Financial Relevance"] = "Medium"
                    elif sig == "keyword":
                        r["Financial Relevance"] = "Low"

        if POST_DEDUP:
            seen, kept = set(), []
            for r in self.rows:
                summ, req = r["Summary"].strip(), _reqs(r).strip()
                key = (r["Country"], r["Act"], summ, req)
                if (summ or req) and key in seen:
                    continue
                seen.add(key)
                kept.append(r)
            self.rows = kept

        if POST_DROP_NOISE:
            self.rows = [r for r in self.rows if _signal_score(r) > 0]

    def _build_rollups(self):
        """Rebuild per-act / regulator / topic rollups from the *kept* rows
        so the Acts sheet and counts match what's actually in the DB."""
        self.acts, self.regulators = {}, {}
        self.topics, self.data_types, self.countries = {}, {}, set()
        for r in self.rows:
            country, act = r["Country"], r["Act"]
            self.countries.add(country)
            a = self.acts.setdefault((country, act), {
                "Country": country, "Act": act, "Sections": 0,
                "Regulators": set(), "Topics": set(), "Data Types": set(),
                "Financial Relevance": "",
            })
            a["Sections"] += 1

            auth = r["Authority"].strip()
            if auth:
                a["Regulators"].add(auth)
                reg = self.regulators.setdefault(
                    auth, {"Country": set(), "Acts": set()})
                reg["Country"].add(country)
                reg["Acts"].add(act)

            rel = str(r["Financial Relevance"]).strip()
            if rel and rel not in ("None", "Unknown"):
                a["Financial Relevance"] = _max_relevance(
                    a["Financial Relevance"], rel)

            for t in (x.strip() for x in r["Topics"].split(",") if x.strip()):
                a["Topics"].add(t)
                self.topics[t] = self.topics.get(t, 0) + 1
            for d in (x.strip() for x in r["Data Types"].split(",")
                      if x.strip()):
                a["Data Types"].add(d)
                self.data_types[d] = self.data_types.get(d, 0) + 1

    def _set_source_links(self):
        """Fill the Source column with the link target for each row."""
        if SOURCE_LINK == "pdf":
            for r in self.rows:
                r["Source"] = _pdf_url(r["Country"], r["Act"])
            return
        # Store the act's row number on the Acts sheet (write_acts iterates
        # self.acts in this same order).  The Query builds a valid internal
        # HYPERLINK("#Acts!A"&row) from it.
        act_row = {key: i + 2 for i, key in enumerate(self.acts)}
        for r in self.rows:
            r["Source"] = act_row.get((r["Country"], r["Act"]), "")

    # -----------------------------------------------------------------

    def summary(self):
        return {
            "countries": len(self.countries),
            "acts": len(self.acts),
            "regulators": len(self.regulators),
            "topics": len(self.topics),
            "rows": len(self.rows),
            "raw_rows": self.raw_rows,
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
    def relevance_list(self):
        order = ["High", "Medium", "Low", "None"]
        return [r for r in order if any(
            row["Financial Relevance"] == r for row in self.rows
        )]


# ---------------------------------------------------------------------

_RELEVANCE_RANK = {"": 0, "None": 0, "Unknown": 0, "Low": 1, "Medium": 2,
                   "High": 3}


def _max_relevance(a, b):
    return a if _RELEVANCE_RANK.get(a, 0) >= _RELEVANCE_RANK.get(b, 0) else b


def _natural_key(value):
    """Zero-pad numbers so identifiers sort naturally (2 < 10 < 10A)."""
    return re.sub(r"\d+", lambda m: m.group().zfill(6), str(value))
