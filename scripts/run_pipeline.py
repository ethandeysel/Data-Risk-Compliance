"""
Run the whole DTIA pipeline end to end: stages 01 -> 05.

This is the "just make it work" entry point.  Drop new legislation under
data/acts/<Country>/*.pdf and run:

    python -m scripts.run_pipeline

Every stage is idempotent, so a re-run only does outstanding work:

  * 01 skips PDFs already turned into text  (OCR_FORCE=1 to redo)
  * 04 skips acts already extracted         (LLM_FORCE=1 to redo)
  * 02, 03, 05 are cheap and simply rebuild from their inputs

So the normal flow for a new country is: add its folder + PDFs, run this
once, and the new acts flow all the way through to the Excel workbook while
the existing South African data is left untouched.

Run only the tail of the pipeline (e.g. after tuning the LLM settings)
with the first-stage number:

    python -m scripts.run_pipeline --from 04     # run 04 and 05 only

All the stage environment variables (LLM_MODEL, LLM_NUM_GPU, LLM_PROVIDER,
etc.) are inherited as-is — set them before calling this.
"""

import subprocess
import sys

# In run order.  Names match the module paths under scripts/.
STAGES = [
    ("01", "scripts.01_extract_text"),
    ("02", "scripts.02_parse_sections"),
    ("03", "scripts.03_extract_requirements"),
    ("04", "scripts.04_extract_llm"),
    ("05", "scripts.05_export_excel"),
]


def parse_start():
    """Return the stage number to start from (default '01')."""
    if "--from" in sys.argv:
        i = sys.argv.index("--from")
        try:
            return sys.argv[i + 1].zfill(2)
        except IndexError:
            raise SystemExit("--from needs a stage number, e.g. --from 04")
    return "01"


def main():
    start = parse_start()
    stages = [s for s in STAGES if s[0] >= start]
    if not stages:
        raise SystemExit(f"No stages at or after {start} (valid: 01-05).")

    print(f"Running stages: {', '.join(n for n, _ in stages)}\n")

    for number, module in stages:
        print("#" * 70)
        print(f"# STAGE {number}  ({module})")
        print("#" * 70, flush=True)

        # -m keeps each stage's own __main__ behaviour and package imports.
        result = subprocess.run([sys.executable, "-m", module])
        if result.returncode != 0:
            raise SystemExit(
                f"\nStage {number} failed (exit {result.returncode}). "
                f"Fix it and re-run; completed work is skipped on resume."
            )

    print("\nAll stages finished.")


if __name__ == "__main__":
    main()
