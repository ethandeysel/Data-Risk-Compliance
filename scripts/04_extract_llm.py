"""
Stage 04 — LLM compliance extraction.

Reads the keyword-filtered sections produced by stage 03, sends each act
through the local Ollama model in batches, and writes structured
compliance JSON for the Excel exporter (stage 05).

Speed notes
-----------
* Input is data/filtered_sections (≈1/4 of the raw sections) — stage 03
  exists precisely so we do not pay for LLM calls on irrelevant text.
* Acts already extracted are skipped, so an interrupted run resumes
  instead of starting over.  Set LLM_FORCE=1 to re-extract everything.
* Batches are packed by token budget (see client.BATCH_TOKENS) rather
  than a fixed section count, keeping every prompt inside the context
  window and avoiding the retries a truncated prompt causes.

Run with:  python -m scripts.04_extract_llm
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# The Windows console defaults to cp1252; force UTF-8 so progress output
# never crashes on a stray non-ASCII character.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from src.llm.client import BATCH_TOKENS, describe, estimate_tokens
from src.llm.extractor import extract_batch
from src.llm.prompt import CATEGORIES, DATA_TYPES, TOPICS

# Lower-cased lookups so we can keep only controlled-vocabulary values
# (the query dropdowns are built from these lists).
_CATEGORIES = {c.lower(): c for c in CATEGORIES}
_TOPICS = {t.lower(): t for t in TOPICS}
_DATA_TYPES = {d.lower(): d for d in DATA_TYPES}


def _allowed(values, lookup):
    """Keep only values in the controlled vocabulary (case-insensitive)."""
    out = []
    for v in values or []:
        canon = lookup.get(str(v).strip().lower())
        if canon and canon not in out:
            out.append(canon)
    return out

INPUT_DIR = Path(os.getenv("LLM_INPUT_DIR", "data/filtered_sections"))
OUTPUT_DIR = Path(os.getenv("LLM_OUTPUT_DIR", "data/extracted"))
FORCE = os.getenv("LLM_FORCE", "0") == "1"

# Skip acts with more than this many sections — lets you extract the
# quick ones first and leave the big acts for an overnight run (resume
# picks them up).  0 = no limit.
MAX_SECTIONS = int(os.getenv("LLM_MAX_SECTIONS", "0"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def pack_batches(sections):
    """Group sections into batches that fit the per-prompt token budget."""
    batch, budget = [], 0
    for section in sections:
        cost = estimate_tokens(section.get("text", "")) + 100
        if batch and budget + cost > BATCH_TOKENS:
            yield batch
            batch, budget = [], 0
        batch.append(section)
        budget += cost
    if batch:
        yield batch


def clean_requirements(requirements):
    """Drop empty requirement objects the model sometimes echoes."""
    cleaned = []
    for req in requirements or []:
        if isinstance(req, dict) and req.get("text", "").strip():
            cleaned.append({
                "text": req.get("text", "").strip(),
                "obligation_type": req.get("obligation_type", ""),
            })
    return cleaned


def merge_section(parsed, llm):
    """Combine the parsed section metadata with the LLM extraction."""
    return {
        "section": str(parsed["identifier"]),
        "heading": parsed.get("heading", ""),
        "chapter": parsed.get("chapter", ""),
        "part": parsed.get("part", ""),
        "condition": parsed.get("condition", ""),
        "page_start": parsed.get("page_start"),
        "page_end": parsed.get("page_end"),
        "primary_category": _CATEGORIES.get(
            str(llm.get("primary_category", "")).strip().lower(), "Other"
        ),
        "summary": llm.get("summary", ""),
        "dtia_summary": llm.get("dtia_summary", ""),
        "authority": llm.get("authority", ""),
        "financial_relevance": llm.get("financial_relevance", "Unknown"),
        "confidence": llm.get("confidence", "Low"),
        "topics": _allowed(llm.get("topics", []), _TOPICS),
        "data_types": _allowed(llm.get("data_types", []), _DATA_TYPES),
        "requirements": clean_requirements(llm.get("requirements", [])),
        "source_quote": llm.get("source_quote", ""),
    }


def extract_document(document):
    """Run every batch of one act and return the merged section list."""
    sections = document["sections"]
    batches = list(pack_batches(sections))
    extracted = []

    for i, section_batch in enumerate(batches, 1):
        print(
            f"  batch {i}/{len(batches)} "
            f"({len(section_batch)} sections, "
            f"{section_batch[0]['identifier']}–"
            f"{section_batch[-1]['identifier']})",
            flush=True,
        )

        result = extract_batch(
            section_batch,
            document["country"],
            document["document"],
        )

        lookup = {
            str(item.get("section", "")): item
            for item in result.get("extractions", [])
        }

        for parsed in section_batch:
            llm = lookup.get(str(parsed["identifier"]), {})
            extracted.append(merge_section(parsed, llm))

    return extracted


def main():
    print("=" * 70)
    print(f"DTIA Compliance Extraction  ({describe()})")
    print(f"Input : {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)

    if not INPUT_DIR.exists():
        raise SystemExit(
            f"Input directory {INPUT_DIR} does not exist. "
            f"Run stage 03 first."
        )

    countries = sorted(d for d in INPUT_DIR.iterdir() if d.is_dir())
    loose = [p for p in INPUT_DIR.glob("*.json")]
    if loose:
        print(
            f"! {len(loose)} JSON file(s) sit directly in {INPUT_DIR} and "
            f"will be skipped — move them into a country sub-folder."
        )

    total_sections = 0
    total_acts = 0
    skipped_acts = 0
    start = time.time()

    for country_dir in countries:
        print(f"\n===== {country_dir.name} =====")
        out_dir = OUTPUT_DIR / country_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)

        for act_file in sorted(country_dir.glob("*.json")):
            out_file = out_dir / act_file.name

            if out_file.exists() and not FORCE:
                print(f"\n- {act_file.stem} -- already extracted, skipping")
                skipped_acts += 1
                continue

            print(f"\n>> {act_file.stem}")
            with open(act_file, encoding="utf-8") as f:
                document = json.load(f)

            sections = document.get("sections")
            if not sections:
                print("  (no sections after filtering)")
                continue

            if MAX_SECTIONS and len(sections) > MAX_SECTIONS:
                print(
                    f"  ({len(sections)} sections > LLM_MAX_SECTIONS="
                    f"{MAX_SECTIONS}, leaving for a later run)"
                )
                skipped_acts += 1
                continue

            t0 = time.time()
            extracted = extract_document(document)

            output = {
                "country": document["country"],
                "document": document["document"],
                "generated": datetime.now().isoformat(timespec="seconds"),
                "sections": extracted,
            }
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)

            total_sections += len(extracted)
            total_acts += 1
            print(
                f"  done: {len(extracted)} sections in "
                f"{time.time() - t0:.0f}s"
            )

    elapsed = time.time() - start
    print("\n" + "=" * 70)
    print("Extraction complete")
    print("=" * 70)
    print(f"Countries       : {len(countries)}")
    print(f"Acts extracted  : {total_acts}")
    print(f"Acts skipped    : {skipped_acts}")
    print(f"Sections        : {total_sections}")
    print(f"Elapsed         : {elapsed / 60:.1f} min")
    if total_sections:
        print(f"Avg per section : {elapsed / total_sections:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
