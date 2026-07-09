import json
from pathlib import Path

from src.parser.parser import SectionParser

RAW = Path("data/raw_text")
OUTPUT = Path("data/sections")

OUTPUT.mkdir(exist_ok=True)

parser = SectionParser()

for country in RAW.iterdir():

    if not country.is_dir():
        continue

    print(f"\n{country.name}")

    out_country = OUTPUT / country.name
    out_country.mkdir(exist_ok=True)

    for file in sorted(country.glob("*.json")):

        print(f"Parsing {file.name}")

        parsed = parser.parse(file)

        outfile = out_country / file.name

        with open(outfile, "w", encoding="utf-8") as f:
            json.dump(
                parsed,
                f,
                indent=2,
                ensure_ascii=False,
            )

print("\nFinished.")