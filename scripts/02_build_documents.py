from pathlib import Path
import json

from compliance.processing.build_document import build_document

INPUT = Path("data/raw_text")
OUTPUT = Path("data/documents")

OUTPUT.mkdir(exist_ok=True)

for country in INPUT.iterdir():

    if not country.is_dir():
        continue

    out = OUTPUT / country.name
    out.mkdir(exist_ok=True)

    for file in country.glob("*.json"):

        document = build_document(file)

        outfile = out / file.name

        with open(outfile, "w", encoding="utf8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        print(outfile)