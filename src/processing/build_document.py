from pathlib import Path
import json

from compliance.processing.clean_text import clean_page


def build_document(json_file: Path):

    with open(json_file, encoding="utf8") as f:
        raw = json.load(f)

    pages = []

    for page in raw["pages"]:

        pages.append(
            {
                "page": page["page"],
                "text": clean_page(page["text"])
            }
        )

    return {
        "country": raw["country"],
        "document": raw["document"],
        "pages": pages
    }
