"""
Batch compliance extraction via a local Ollama model.

The heavy lifting is a single chat() call per batch of sections.  Speed
comes from three things handled here and in client.py:

  * thinking is disabled (see client.THINK) — the model answers directly
  * the context window is sized to the prompt, not fixed at 32k
  * the model is kept resident between calls (client.KEEP_ALIVE)
"""

import json
import re
import time

from .client import generate
from .prompt import SYSTEM_PROMPT, build_prompt


# --------------------------------------------------------
# JSON extraction
# --------------------------------------------------------

def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def parse_json(text: str):
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Model occasionally wraps or trails the object — grab the
        # outermost {...} and retry.
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


# --------------------------------------------------------
# Ollama call
# --------------------------------------------------------

def call_model(prompt: str) -> str:
    return generate(SYSTEM_PROMPT, prompt)


# --------------------------------------------------------
# Normalise model output
# --------------------------------------------------------

def normalise_output(result):
    """Coerce whatever the model returned into {"extractions": [...]}."""

    if isinstance(result, list):
        return {"extractions": result}

    if isinstance(result, dict):
        if "extractions" in result:
            return result
        # A single extraction object without the wrapper.
        return {"extractions": [result]}

    raise ValueError("Unexpected model response type.")


# --------------------------------------------------------
# Fallback (all retries exhausted)
# --------------------------------------------------------

def _empty_extractions(sections):
    return {
        "extractions": [
            {
                "section": s["identifier"],
                "primary_category": "Other",
                "summary": "",
                "dtia_summary": "",
                "financial_relevance": "Unknown",
                "confidence": "Low",
                "topics": [],
                "data_types": [],
                "requirements": [],
                "authority": "",
                "source_quote": "",
            }
            for s in sections
        ]
    }


# --------------------------------------------------------
# Batch extraction
# --------------------------------------------------------

def extract_batch(sections, country, act, retries=3):
    """
    Extract one batch of sections.  Always returns a dict with an
    "extractions" list — never raises — so the caller can keep going.
    """

    prompt = build_prompt(sections, country, act)

    for attempt in range(1, retries + 1):
        try:
            return normalise_output(parse_json(call_model(prompt)))
        except Exception as e:
            print(
                f"  ! {act}: attempt {attempt}/{retries} "
                f"failed ({type(e).__name__}: {e})"
            )
            # Failures here are malformed JSON from a local model, not
            # API rate limits — a short pause and retry is enough.
            if attempt < retries:
                time.sleep(2)

    print(f"  ! {act}: giving up on batch, writing empty extractions")
    return _empty_extractions(sections)
