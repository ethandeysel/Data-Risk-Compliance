"""
Stage 03 — relevance filter.

Drops table-of-contents lines, boilerplate and irrelevant sections so the
LLM (stage 04) only sees compliance-relevant text.  See
src/filter/keyword_filter.py for the (high-recall) filtering logic.

Input is read recursively and output is organised by the document's own
`country` field, so it does not matter whether the source files sit
directly in data/sections or in a country sub-folder.

Run with:  python -m scripts.03_extract_requirements
"""

import json
from pathlib import Path

from src.filter.keyword_filter import document_relevant, filter_document

INPUT = Path("data/sections")
OUTPUT = Path("data/filtered_sections")

OUTPUT.mkdir(exist_ok=True)

total_sections = 0
total_kept = 0

for act in sorted(INPUT.rglob("*.json")):

    with open(act, encoding="utf-8") as f:
        document = json.load(f)

    sections = document.get("sections", [])
    kept = filter_document(document)

    total_sections += len(sections)
    total_kept += len(kept)

    country = document.get("country", "Unknown")
    out_country = OUTPUT / country
    out_country.mkdir(parents=True, exist_ok=True)

    flag = "on-topic" if document_relevant(document) else "general"
    print(
        f"[{country}] {document['document'][:50]:50}  "
        f"kept {len(kept):>4}/{len(sections):<4}  ({flag})"
    )

    with open(out_country / act.name, "w", encoding="utf-8") as f:
        json.dump(
            {
                "country": country,
                "document": document["document"],
                "sections": kept,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

print("\n===============================")
print(f"Sections examined : {total_sections}")
print(f"Sections retained : {total_kept}")
if total_sections:
    print(f"Retention rate    : {100 * total_kept / total_sections:.1f}%")
print("===============================")
