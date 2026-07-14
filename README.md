# DTIA Compliance Database

Builds a searchable compliance knowledge base from national legal acts,
regulations and guidelines, used to answer **Data Transfer Impact
Assessment (DTIA)** questions in Excel — e.g. *"which laws apply to
transferring data between the EU and South Africa, and on what page?"* or
*"what are the requirements to store financial data in the UK?"*

Currently loaded with South African legislation; the same pipeline scales
to other countries by dropping their PDFs under `data/acts/<Country>/`.

## Pipeline

Each stage reads the previous stage's output. Directories are organised by
country: `data/<stage>/<Country>/<act>.json`.

| Stage | Script | In → Out | What it does |
|-------|--------|----------|--------------|
| 01 | `scripts/01_extract_text.py` | `data/acts` → `data/raw_text` | PDF text extraction (OCR fallback) |
| 02 | `scripts/02_parse_sections.py` | `data/raw_text` → `data/sections` | Split into legislative sections |
| 03 | `scripts/03_extract_requirements.py` | `data/sections` → `data/filtered_sections` | Keyword filter to compliance-relevant sections |
| 04 | `scripts/04_extract_llm.py` | `data/filtered_sections` → `data/extracted` | LLM structured extraction (Ollama) |
| 05 | `scripts/05_export_excel.py` | `data/extracted` → `DTIA_Compliance_Database.xlsx` | Build the query workbook |

Run each stage from the repo root, e.g. `python -m scripts.04_extract_llm`,
or run the **whole pipeline** in one command:

```
python -m scripts.run_pipeline           # stages 01 -> 05
python -m scripts.run_pipeline --from 04 # just 04 and 05
```

Every stage is idempotent (01 skips already-extracted PDFs, 04 skips
already-extracted acts), so a re-run only does outstanding work.

**Smoke test first.** To sanity-check the chain (especially a newly added
country) before the full multi-hour run, process just the 5 smallest acts
per country into a separate `_TEST` workbook:

```
python -m scripts.run_test
```

Stages 01–03 still process everything (they're cheap); only the LLM stage
is capped, and already-extracted acts are skipped, so a fresh country gets
a quick 5-act sample while finished countries produce nothing new.

### Adding another country

Drop the PDFs under `data/acts/<Country>/` (e.g. `data/acts/Nigeria/`) and
run `python -m scripts.run_pipeline`. The new country flows all the way
through to the workbook; existing countries are skipped, not reprocessed.
Note that new PDFs must go through 01→03 before 04 sees them — running only
04/05 will not pick up a country that hasn't been text-extracted and
filtered yet, which is why the single command runs the full chain.

### New machine setup

1. Install [Ollama](https://ollama.com) and pull the model:
   `ollama pull qwen3:4b`
2. `pip install -r requirements.txt`
3. (OCR only — needed if any PDFs are scanned) install Tesseract + Ghostscript.
4. Run `python -m scripts.run_pipeline`.

## Stage 02 — section parser

`src/parser/parser.py` splits each document into sections. It detects the
numbering style per document:

- **Style A** — `12. Security measures` (a number, dot, heading). Most
  Acts (POPIA, Banks Act, FICA, Cybercrimes…).
- **Style B** — decimal numbering `12.1 …` with the heading on its own
  line above (Joint Standards, directives, the cybersecurity policy
  framework). These get running headers and TOC lines stripped, then are
  split on the top-level number — otherwise the whole body collapses into
  one section with no per-section page references.

## Stage 03 — relevance filter

Keeps every section a DTIA might rely on (high recall) and drops genuine
noise (table-of-contents lines, boilerplate, tiny structural fragments).
On-topic documents (privacy, cyber, financial, AML…) keep every
substantive section; broad/general acts fall back to keyword signals.
See `src/filter/keyword_filter.py`.

## Stage 04 — LLM extraction

Turns each section into structured compliance JSON (category, summary,
DTIA relevance, requirements, authority, topics, data types, source
quote — see `src/llm/prompt.py`). Two backends behind one interface:

- **`ollama`** (default) — a local model, no data leaves the machine.
- **`gemini`** — the Google Gemini API, for a fast full rebuild.

It reads the **filtered** sections (stage 03), **skips acts already in
`data/extracted`** (so an interrupted run resumes), and packs batches by
token budget.

Oversized sections (a whole document the parser failed to split, a long
schedule) would overflow the context window and silently return nothing,
so any section above `LLM_CHUNK_TOKENS` is split into overlapping chunks,
each extracted, and the requirements/summaries merged back into one row.
When the model still can't produce valid JSON, the section is written with
a visible flag (`confidence = "Extraction failed"`, or `"Partial…"` for a
section too large to fully cover) rather than a blank Low-confidence row —
so gaps show up in the workbook instead of looking like real empty data.

### Configuration (environment variables)

| Var | Default | Purpose |
|-----|---------|---------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `LLM_MODEL` | `qwen3:8b` | Ollama model tag (needs `ollama pull qwen3:8b`) |
| `LLM_HOST` | `http://localhost:11434` | Ollama host |
| `LLM_THINK` | `0` | `1` re-enables qwen3 chain-of-thought (much slower) |
| `LLM_KEEP_ALIVE` | `30m` | Keep the model resident between batches |
| `LLM_NUM_GPU` | *(auto)* | GPU layers to offload. Unset = Ollama auto-detects; `999` forces the whole model onto the GPU |
| `LLM_NUM_CTX_MAX` | `16384` | Context-window ceiling |
| `LLM_BATCH_TOKENS` | `6000` | Token budget per batch |
| `LLM_CHUNK_TOKENS` | `3000` | Sections larger than this are chunked instead of sent whole (avoids context-window truncation) |
| `LLM_CHUNK_OVERLAP` | `200` | Token overlap between chunks so a rule split across the boundary is still seen intact |
| `LLM_MAX_CHUNKS` | `20` | Cap on chunks per section; a section beyond this is flagged as partially processed |
| `LLM_FORCE` | `0` | `1` re-extracts acts even if output exists |
| `LLM_MAX_SECTIONS` | `0` | Skip acts larger than this (0 = no limit). Do the quick acts first, big ones overnight |
| `LLM_MAX_ACTS` | `0` | Process only the N smallest acts per country (0 = no limit). Used by `run_test` for a fast smoke test |
| `GEMINI_API_KEY` | — | Required for `LLM_PROVIDER=gemini` (read from `.env`) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model |

### Performance notes

Generation dominates the cost, so tokens/sec is the number that matters.

**On a GPU machine**, Ollama offloads the model to the card automatically —
you do not have to configure anything; the speedup is just there. Confirm
it is actually on the GPU while a run is going with `ollama ps` (the
`PROCESSOR` column should read `100% GPU`). If it shows CPU or a partial
split, the model did not fit — either the card is too small for the model,
or force the issue and watch it fail loudly with `LLM_NUM_GPU=999`. With
headroom to spare you can also afford a larger model (`LLM_MODEL=qwen3:8b`)
or re-enable reasoning (`LLM_THINK=1`) for higher-quality extraction.

On **CPU only** (e.g. the original AMD Ryzen 7 5800HS box) it runs at
roughly **2–3 tokens/sec** and a full rebuild takes hours — run it
overnight (it resumes) or use the Gemini backend. Levers already applied:
thinking disabled, a **trimmed output schema**, a smaller default model
(`qwen3:4b`), context sized to the prompt, high-recall filtering, resume.

```
# GPU box: full model on the card, run everything
LLM_NUM_GPU=999 python -m scripts.run_pipeline

# fast local iteration on stage 04 only
LLM_MODEL=qwen3:4b python -m scripts.04_extract_llm

# fast full rebuild via cloud (sends legal text to Google)
LLM_PROVIDER=gemini python -m scripts.04_extract_llm
```

> On Windows PowerShell, set env vars first: `$env:LLM_NUM_GPU=999` then run
> the command on the next line (the inline `VAR=value cmd` form is bash-only).

## Stage 05 — Excel workbook

`DTIA_Compliance_Database.xlsx` with:

- **Query** — the DTIA query engine: dropdowns (Country, Category, Topic,
  Data Type, Financial Relevance, Authority) plus a keyword box, over a
  live `FILTER()` that returns matching sections **with Act and page
  reference**. Requires Excel 365 (dynamic arrays).
- **Compliance Database** — every extracted section, one row each.
- **Acts / Regulators / Topics** — rollups.

> If the Query results show a single row or `#SPILL`, click cell `A14`
> and press Enter — some Excel builds need the dynamic formula re-entered
> once after the file is generated.
