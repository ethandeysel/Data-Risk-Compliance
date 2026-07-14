from pathlib import Path
import json
import os

from src.pdf.detect_pdf import needs_ocr
from src.pdf.extract_text import extract_pdf_text
from src.utils.logger import *
from src.pdf.ocr import ocr_pdf

ACTS_FOLDER = Path("data/acts")
OUTPUT_FOLDER = Path("data/raw_text")

# OCR is slow, so already-extracted PDFs are skipped and a re-run only
# processes newly added acts/countries.  Set OCR_FORCE=1 to redo everything.
FORCE = os.getenv("OCR_FORCE", "0") == "1"

OUTPUT_FOLDER.mkdir(exist_ok=True)

countries = [x for x in ACTS_FOLDER.iterdir() if x.is_dir()]

for country in countries:

    info(country.name)

    out_country = OUTPUT_FOLDER / country.name
    out_country.mkdir(exist_ok=True)

    for pdf in country.glob("*.pdf"):

        outfile = out_country / f"{pdf.stem}.json"

        if outfile.exists() and not FORCE:
            info(f"{pdf.name} -- already extracted, skipping")
            continue

        info(pdf.name)
        try:

            if needs_ocr(pdf):

                warning("Running OCR...")

                pages = ocr_pdf(pdf)

            else:

                pages = extract_pdf_text(pdf)

        except Exception as e:

            error(f"Failed to process {pdf.name}")

            error(str(e))

            continue


        output = {
            "country": country.name,
            "document": pdf.stem,
            "pages": pages
        }

        with open(outfile, "w", encoding="utf8") as f:

            json.dump(output, f, indent=2, ensure_ascii=False)

        success(outfile.name)