import json
from pathlib import Path

from src.filter.keyword_filter import score

INPUT = Path("data/sections")
OUTPUT = Path("data/filtered_sections")

OUTPUT.mkdir(exist_ok=True)

total_sections = 0
total_kept = 0

for country in INPUT.iterdir():

    if not country.is_dir():
        continue

    out_country = OUTPUT / country.name
    out_country.mkdir(exist_ok=True)

    print(f"\n========== {country.name} ==========")

    for act in sorted(country.glob("*.json")):

        with open(act, encoding="utf8") as f:
            document = json.load(f)

        filtered = []

        print(f"\n{document['document']}")

        for section in document["sections"]:

            total_sections += 1

            matches = score(section)

            if len(matches) < 2:
                continue

            total_kept += 1

            filtered.append({

                "identifier": section["identifier"],

                "heading": section["heading"],

                "chapter": section["chapter"],

                "part": section["part"],

                "condition": section["condition"],

                "page_start": section["page_start"],

                "page_end": section["page_end"],

                "matched_keywords": matches,

                "text": section["text"]

            })

        print(
            f"Kept {len(filtered)} of {len(document['sections'])} sections"
        )

        outfile = out_country / act.name

        with open(outfile, "w", encoding="utf8") as f:

            json.dump(

                {

                    "country": document["country"],

                    "document": document["document"],

                    "sections": filtered

                },

                f,

                indent=2,

                ensure_ascii=False

            )
        

print("\n===============================")
print(f"Sections examined : {total_sections}")
print(f"Sections retained : {total_kept}")
print(
    f"Retention rate    : {100*total_kept/total_sections:.1f}%"
)
print("===============================")