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

Run each stage from the repo root, e.g. `python -m scripts.04_extract_llm`.

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

### Configuration (environment variables)

| Var | Default | Purpose |
|-----|---------|---------|
| `LLM_PROVIDER` | `ollama` | `ollama` or `gemini` |
| `LLM_MODEL` | `qwen3:4b` | Ollama model tag |
| `LLM_HOST` | `http://localhost:11434` | Ollama host |
| `LLM_THINK` | `0` | `1` re-enables qwen3 chain-of-thought (much slower) |
| `LLM_KEEP_ALIVE` | `30m` | Keep the model resident between batches |
| `LLM_NUM_CTX_MAX` | `16384` | Context-window ceiling |
| `LLM_BATCH_TOKENS` | `6000` | Token budget per batch |
| `LLM_FORCE` | `0` | `1` re-extracts acts even if output exists |
| `LLM_MAX_SECTIONS` | `0` | Skip acts larger than this (0 = no limit). Do the quick acts first, big ones overnight |
| `GEMINI_API_KEY` | — | Required for `LLM_PROVIDER=gemini` (read from `.env`) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model |

### Performance notes

Inference runs on **CPU** here (AMD Ryzen 7 5800HS, no Ollama-usable GPU)
at roughly **2–3 tokens/sec**, and generation dominates the cost. Levers
applied: thinking disabled, a **trimmed output schema**, a smaller default
model (`qwen3:4b`), context sized to the prompt, high-recall filtering,
and resume. A full local rebuild still takes hours — run it overnight (it
resumes) or use the Gemini backend for a fast rebuild:

```
# fast local iteration
LLM_MODEL=qwen3:4b python -m scripts.04_extract_llm

# fast full rebuild via cloud (sends legal text to Google)
LLM_PROVIDER=gemini python -m scripts.04_extract_llm
```

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
