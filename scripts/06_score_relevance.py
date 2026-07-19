"""
Stage 06 — score section relevance.

A cheap second LLM pass over the extracted sections (stage 04 output).
Each section is rated 0-3 for how relevant it is to a cyber-security /
data-protection consultancy answering client data-compliance questions
(see src/llm/relevance.py for the rubric).  The score + a short reason are
written back into the extracted JSON so stage 05 can show a Relevance
column and a "minimum relevance" filter.

The prompt is short (the section's own summary + heading + topics +
requirements, not the full text), so this runs much faster than stage 04.

Resumable: a section that already has a relevance_score is skipped, so an
interrupted run picks up where it stopped.  Set RELEVANCE_FORCE=1 to
re-score everything.

Run with:  python -m scripts.06_score_relevance
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from src.llm.client import describe
from src.llm.relevance import score_section

EXTRACTED_DIR = Path(os.getenv("LLM_OUTPUT_DIR", "data/extracted"))
FORCE = os.getenv("RELEVANCE_FORCE", "0") == "1"

# Process only acts whose filename contains one of these comma-separated
# substrings (case-insensitive).  Empty = all acts.
ONLY = [s.strip().lower() for s in os.getenv("RELEVANCE_ONLY", "").split(",")
        if s.strip()]


def _needs_score(section):
    return FORCE or section.get("relevance_score") is None


def score_document(path):
    """Score every (unscored) section in one act file; save in place.

    Returns (scored, skipped, dist) where dist counts scores 0-3.
    """
    with open(path, encoding="utf-8") as f:
        document = json.load(f)

    country = document.get("country", "Unknown")
    act = document.get("document", path.stem)
    sections = document.get("sections", [])

    scored = skipped = 0
    dist = {0: 0, 1: 0, 2: 0, 3: 0}
    for section in sections:
        if not _needs_score(section):
            skipped += 1
            s = section.get("relevance_score")
            if s in dist:
                dist[s] += 1
            continue
        score, reason = score_section(section, country, act)
        section["relevance_score"] = score
        section["relevance_reason"] = reason
        dist[score] += 1
        scored += 1

    if scored:  # only rewrite the file if something changed
        with open(path, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

    return scored, skipped, dist


def main():
    print("=" * 70)
    print(f"DTIA Relevance Scoring  ({describe()})")
    print(f"Extracted: {EXTRACTED_DIR}")
    print("=" * 70)

    if not EXTRACTED_DIR.exists():
        raise SystemExit(
            f"{EXTRACTED_DIR} does not exist. Run stage 04 first."
        )

    countries = sorted(d for d in EXTRACTED_DIR.iterdir() if d.is_dir())
    total_scored = total_skipped = 0
    grand = {0: 0, 1: 0, 2: 0, 3: 0}
    start = time.time()

    for country_dir in countries:
        act_files = sorted(country_dir.glob("*.json"))
        if ONLY:
            act_files = [
                f for f in act_files
                if any(sub in f.name.lower() for sub in ONLY)
            ]
        if not act_files:
            continue

        print(f"\n===== {country_dir.name} =====")
        for act_file in act_files:
            t0 = time.time()
            scored, skipped, dist = score_document(act_file)
            total_scored += scored
            total_skipped += skipped
            for k in grand:
                grand[k] += dist[k]
            if scored:
                d = " ".join(f"{k}:{dist[k]}" for k in (3, 2, 1, 0))
                print(
                    f"  {act_file.stem[:44]:44s}  "
                    f"scored {scored:4d} ({d}) in {time.time() - t0:.0f}s"
                )
            else:
                print(f"  {act_file.stem[:44]:44s}  (all {skipped} scored)")

    elapsed = time.time() - start
    graded = sum(grand.values())
    print("\n" + "=" * 70)
    print("Relevance scoring complete")
    print("=" * 70)
    print(f"Newly scored : {total_scored}")
    print(f"Already done : {total_skipped}")
    if graded:
        print("Distribution (all scored sections):")
        for k in (3, 2, 1, 0):
            pct = 100 * grand[k] / graded
            print(f"   score {k}: {grand[k]:5d}  ({pct:4.1f}%)")
    print(f"Elapsed      : {elapsed / 60:.1f} min")
    if total_scored:
        print(f"Avg/section  : {elapsed / total_scored:.2f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
