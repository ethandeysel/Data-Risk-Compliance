"""
Batch compliance extraction via a local Ollama model.

The heavy lifting is a single chat() call per batch of sections.  Speed
comes from three things handled here and in client.py:

  * thinking is disabled (see client.THINK) — the model answers directly
  * the context window is sized to the prompt, not fixed at 32k
  * the model is kept resident between calls (client.KEEP_ALIVE)
"""

import json
import os
import re
import time
from collections import Counter

from .client import generate, estimate_tokens
from .prompt import SYSTEM_PROMPT, build_prompt

# A section whose text exceeds this many tokens is processed in chunks
# rather than sent whole, so it never overflows the context window (which
# silently truncates the prompt and yields empty extractions).
SECTION_TOKEN_LIMIT = int(os.getenv("LLM_CHUNK_TOKENS", "3000"))
# Overlap between consecutive chunks so a rule split across the boundary is
# still seen intact by at least one chunk.
CHUNK_OVERLAP_TOKENS = int(os.getenv("LLM_CHUNK_OVERLAP", "200"))
# Safety cap so a pathologically large "section" (a whole document the
# parser failed to split) cannot spawn hundreds of calls.
MAX_CHUNKS = int(os.getenv("LLM_MAX_CHUNKS", "20"))


# --------------------------------------------------------
# JSON extraction
# --------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_json(text: str):
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Model occasionally wraps or trails the object — grab the
        # outermost {...} and retry.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


# --------------------------------------------------------
# Ollama call
# --------------------------------------------------------

def call_model(prompt: str) -> str:
    return generate(SYSTEM_PROMPT, prompt)


# --------------------------------------------------------
# Normalise model output
# --------------------------------------------------------

def normalise_output(result):
    """Coerce whatever the model returned into {"extractions": [...]}."""

    if isinstance(result, list):
        return {"extractions": result}

    if isinstance(result, dict):
        if "extractions" in result:
            return result
        # A single extraction object without the wrapper.
        return {"extractions": [result]}

    raise ValueError("Unexpected model response type.")


# --------------------------------------------------------
# Fallback (all retries exhausted)
# --------------------------------------------------------

def _flagged_empty(identifier, reason):
    """A visibly-flagged placeholder for a section the model could not
    process, so gaps are obvious in the workbook instead of masquerading
    as a genuinely empty (Low-confidence) section."""
    return {
        "section": identifier,
        "title": "",
        "primary_category": "Other",
        "summary": f"[extraction failed: {reason}]",
        "dtia_summary": "",
        "financial_relevance": "Unknown",
        "confidence": "Extraction failed",
        "topics": [],
        "data_types": [],
        "requirements": [],
        "authority": "",
        "source_quote": "",
    }


def _empty_extractions(sections, reason="model returned no valid JSON"):
    return {
        "extractions": [
            _flagged_empty(s["identifier"], reason) for s in sections
        ]
    }


# --------------------------------------------------------
# Batch extraction
# --------------------------------------------------------

def _looks_like_timeout(exc) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "timeout" in text or "timed out" in text


def extract_batch(sections, country, act, retries=2):
    """
    Extract one batch of sections.  Always returns a dict with an
    "extractions" list — never raises — so the caller can keep going.

    On failure a multi-section batch is split in half and each half retried
    (recursing down to single sections), so one problematic section is
    isolated and flagged instead of losing the whole batch.  A timeout is
    treated as "batch too big": we split immediately rather than re-sending
    the same oversized prompt only to time out again.
    """

    prompt = build_prompt(sections, country, act)

    for attempt in range(1, retries + 1):
        try:
            return normalise_output(parse_json(call_model(prompt)))
        except Exception as e:
            print(
                f"  ! {act}: attempt {attempt}/{retries} "
                f"failed ({type(e).__name__}: {e})"
            )
            if _looks_like_timeout(e):
                break  # bigger prompt won't parse faster — split instead
            if attempt < retries:
                time.sleep(1)

    if len(sections) > 1:
        mid = len(sections) // 2
        print(
            f"  {act}: splitting failed batch of {len(sections)} sections "
            f"({mid}+{len(sections) - mid}) and retrying smaller"
        )
        left = extract_batch(sections[:mid], country, act, retries)
        right = extract_batch(sections[mid:], country, act, retries)
        return {
            "extractions": left.get("extractions", [])
            + right.get("extractions", [])
        }

    print(
        f"  ! {act}: section {sections[0]['identifier']} could not be "
        f"extracted, flagging"
    )
    return _empty_extractions(sections, reason="model output unparseable")


# --------------------------------------------------------
# Oversized sections — chunk, extract each, merge
# --------------------------------------------------------

def is_oversized(section) -> bool:
    return estimate_tokens(section.get("text", "")) > SECTION_TOKEN_LIMIT


def _chunk_text(text, max_chars, overlap_chars, max_chunks):
    """Split text into overlapping windows, preferring newline boundaries.

    Returns (chunks, truncated) where truncated is True if the section was
    too large to cover within max_chunks.
    """
    chunks = []
    start, n = 0, len(text)
    while start < n and len(chunks) < max_chunks:
        end = min(start + max_chars, n)
        if end < n:
            # Prefer to cut on a newline in the back half of the window.
            nl = text.rfind("\n", start + max_chars // 2, end)
            if nl != -1:
                end = nl
        chunks.append(text[start:end])
        if end >= n:
            return chunks, False
        start = max(end - overlap_chars, start + 1)
    return chunks, start < n


def _merge_requirements(parts):
    reqs, seen = [], set()
    for p in parts:
        for r in (p.get("requirements") or []):
            if not isinstance(r, dict):
                continue
            key = r.get("text", "").strip().lower()
            if key and key not in seen:
                seen.add(key)
                reqs.append(r)
    return reqs


def _merge_list(parts, field):
    out, seen = [], set()
    for p in parts:
        for v in (p.get(field) or []):
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


def _dedup_join(values, limit):
    out, seen = [], set()
    for v in values:
        v = (v or "").strip()
        k = v.lower()
        if v and k not in seen:
            seen.add(k)
            out.append(v)
    return " ".join(out)[:limit]


_RELEVANCE_ORDER = {"None": 0, "Unknown": 0, "Low": 1, "Medium": 2, "High": 3}


def _merge_extractions(identifier, parts, truncated):
    """Combine the per-chunk extractions of one oversized section into a
    single extraction (one row per section keeps the data model clean)."""
    parts = [p for p in parts if isinstance(p, dict)]
    if not parts:
        return _flagged_empty(identifier, "no output from any chunk")

    cats = Counter(
        p.get("primary_category", "") for p in parts
        if p.get("primary_category") and p.get("primary_category") != "Other"
    )
    category = cats.most_common(1)[0][0] if cats else "Other"

    relevance = max(
        (p.get("financial_relevance", "") for p in parts),
        key=lambda r: _RELEVANCE_ORDER.get(r, 0), default="Unknown",
    ) or "Unknown"

    note = ("Partial (oversized section - only the first part was processed)"
            if truncated else "Medium (merged from chunks)")

    return {
        "section": identifier,
        "title": next((p.get("title", "") for p in parts if p.get("title")), ""),
        "primary_category": category,
        "summary": _dedup_join((p.get("summary", "") for p in parts), 1200),
        "dtia_summary": _dedup_join(
            (p.get("dtia_summary", "") for p in parts), 600),
        "financial_relevance": relevance,
        "confidence": note,
        "topics": _merge_list(parts, "topics"),
        "data_types": _merge_list(parts, "data_types"),
        "requirements": _merge_requirements(parts),
        "authority": next(
            (p.get("authority", "") for p in parts if p.get("authority")), ""),
        "source_quote": next(
            (p.get("source_quote", "") for p in parts if p.get("source_quote")),
            ""),
    }


def extract_large_section(section, country, act):
    """Extract one oversized section by chunking its text and merging the
    per-chunk results.  Always returns a single extraction dict."""
    max_chars = SECTION_TOKEN_LIMIT * 4
    overlap = CHUNK_OVERLAP_TOKENS * 4
    chunks, truncated = _chunk_text(
        section.get("text", ""), max_chars, overlap, MAX_CHUNKS)

    parts = []
    for i, chunk in enumerate(chunks, 1):
        print(f"    chunk {i}/{len(chunks)} of section {section['identifier']}",
              flush=True)
        sub = dict(section)
        sub["text"] = chunk
        result = extract_batch([sub], country, act)
        extractions = result.get("extractions", [])
        if extractions:
            parts.append(extractions[0])

    if truncated:
        print(f"    ! section {section['identifier']} exceeds {MAX_CHUNKS} "
              f"chunks; flagged as partially processed")
    return _merge_extractions(section["identifier"], parts, truncated)
