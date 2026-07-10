# Complete replacement for scripts/04_extract_gemini.py

import json
from pathlib import Path
from datetime import datetime

from tqdm import tqdm

from src.llm.extractor import extract_batch

INPUT_DIR = Path("data/sections")
OUTPUT_DIR = Path("data/extracted")

BATCH_SIZE = 5

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def batch(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


print("=" * 70)
print("DTIA Compliance Extraction")
print("=" * 70)

countries = sorted(d for d in INPUT_DIR.iterdir() if d.is_dir())

total_sections = 0
processed_sections = 0
total_batches = 0

for country_dir in countries:

    print(f"\n===== {country_dir.name} =====")

    out_dir = OUTPUT_DIR / country_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    for act_file in sorted(country_dir.glob("*.json")):

        print(f"\nProcessing: {act_file.stem}")

        with open(act_file, encoding="utf-8") as f:
            document = json.load(f)

        sections = document["sections"]
        total_sections += len(sections)

        extracted_sections = []

        for section_batch in tqdm(
            list(batch(sections, BATCH_SIZE)),
            desc="Gemini",
            leave=False
        ):
            print()
            print(
                f"Batch sections: "
                f"{section_batch[0]['identifier']} "
                f"to "
                f"{section_batch[-1]['identifier']}"
            )
            result = extract_batch(
                section_batch,
                document["country"],
                document["document"]
            )

            returned = result.get("extractions", [])

            lookup = {
                str(item.get("section", "")): item
                for item in returned
            }

            for parsed in section_batch:

                sid = str(parsed["identifier"])
                llm = lookup.get(sid, {})

                extracted_sections.append({

                    "section": sid,
                    "heading": parsed.get("heading", ""),
                    "chapter": parsed.get("chapter", ""),
                    "part": parsed.get("part", ""),
                    "condition": parsed.get("condition", ""),
                    "page_start": parsed.get("page_start"),
                    "page_end": parsed.get("page_end"),

                    "primary_category": llm.get(
                        "primary_category",
                        "Other"
                    ),

                    "summary": llm.get("summary", ""),
                    "dtia_summary": llm.get(
                        "dtia_summary",
                        ""
                    ),

                    "authority": llm.get(
                        "authority",
                        ""
                    ),

                    "financial_relevance": llm.get(
                        "financial_relevance",
                        "Unknown"
                    ),

                    "confidence": llm.get(
                        "confidence",
                        "Low"
                    ),

                    "topics": llm.get(
                        "topics",
                        []
                    ),

                    "data_types": llm.get(
                        "data_types",
                        []
                    ),

                    "actors": llm.get(
                        "actors",
                        []
                    ),

                    "keywords": llm.get(
                        "keywords",
                        []
                    ),

                    "requirements": llm.get(
                        "requirements",
                        []
                    ),

                    "source_quote": llm.get(
                        "source_quote",
                        ""
                    )

                })

            processed_sections += len(section_batch)
            total_batches += 1

        output = {
            "country": document["country"],
            "document": document["document"],
            "generated": datetime.now().isoformat(),
            "sections": extracted_sections
        }

        with open(
            out_dir / act_file.name,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                output,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(f"Saved {len(extracted_sections)} sections.")

print("\n" + "=" * 70)
print("Extraction Complete")
print("=" * 70)
print(f"Countries : {len(countries)}")
print(f"Sections  : {processed_sections}")
print(f"Batches   : {total_batches}")
print("=" * 70)
