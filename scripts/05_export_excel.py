"""
Stage 05 — build the DTIA query workbook from the extracted sections.

Run with:  python -m scripts.05_export_excel
Override the output path with EXCEL_OUTPUT.
"""

import os
from pathlib import Path

from src.excel.loaders import DataLoader
from src.excel.workbook import create_workbook
from src.excel.writers import ExcelWriter

OUTPUT = Path(os.getenv("EXCEL_OUTPUT", "DTIA_Compliance_Database.xlsx"))

print("Loading data...")
loader = DataLoader().load()
print(loader.summary())

wb = create_workbook()
ExcelWriter(wb, loader).build()

try:
    wb.save(OUTPUT)
except PermissionError:
    # The workbook is almost always open in Excel — save alongside it so
    # the run is not wasted, and tell the user how to refresh the main file.
    fallback = OUTPUT.with_name(OUTPUT.stem + "_new" + OUTPUT.suffix)
    wb.save(fallback)
    print(
        f"\n! {OUTPUT} is open (locked). Saved to {fallback} instead.\n"
        f"  Close Excel and re-run to update {OUTPUT}."
    )
else:
    print(f"\nDone. Workbook saved as {OUTPUT}")
