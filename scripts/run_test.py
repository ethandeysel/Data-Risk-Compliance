"""
Smoke-test the pipeline: run only the 5 smallest acts of every country.

Use this to check a run end to end — especially a newly added country —
before committing to the full multi-hour extraction:

    python -m scripts.run_test

What it does differently from run_pipeline:

  * stages 01-03 still process every act (they are cheap and the LLM stage
    needs the real section counts to know which acts are "smallest")
  * stage 04 extracts only the 5 smallest acts per country (LLM_MAX_ACTS=5)
  * stage 05 writes to a SEPARATE workbook so the real database is untouched

Already-extracted acts are skipped as usual, so re-running only fills gaps.
Because the cap is the *5 smallest acts* (not the 5 smallest not-yet-done),
a country whose 5 smallest are already extracted produces nothing new — the
whole point being to give each fresh country a quick sample.

Override any of these before running, e.g. a 3-act test into the real file:

    LLM_MAX_ACTS=3  EXCEL_OUTPUT=DTIA_Compliance_Database.xlsx  python -m scripts.run_test
"""

import os

# setdefault so an explicit environment value always wins.
os.environ.setdefault("LLM_MAX_ACTS", "10")
os.environ.setdefault("EXCEL_OUTPUT", "DTIA_Compliance_Database_TEST.xlsx")

from scripts import run_pipeline

if __name__ == "__main__":
    print(
        f"TEST RUN — {os.environ['LLM_MAX_ACTS']} smallest acts/country "
        f"-> {os.environ['EXCEL_OUTPUT']}\n"
    )
    run_pipeline.main()
