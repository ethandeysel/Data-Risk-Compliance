"""
Batch extraction using Gemini.
"""

import json
import re
import time


from .gemini_client import client, MODEL
from .prompt import SYSTEM_PROMPT, build_prompt


# --------------------------------------------------------
# Clean markdown
# --------------------------------------------------------

def clean_json(text: str):

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    if text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# --------------------------------------------------------
# Extract JSON
# --------------------------------------------------------

def parse_json(text):

    text = clean_json(text)

    try:
        return json.loads(text)

    except Exception:

        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL
        )

        if match:
            return json.loads(match.group())

        raise


# --------------------------------------------------------
# Gemini call
# --------------------------------------------------------

def call_gemini(prompt):

    response = client.chat(

        model=MODEL,

        messages=[

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": prompt
            }

        ],

        options={

            "temperature": 0,

            "num_ctx": 32768

        },

        format="json"

    )

    return response.message.content

# --------------------------------------------------------
# Normalise Gemini output
# --------------------------------------------------------

def normalise_output(result, sections):

    # Gemini returned a list
    if isinstance(result, list):

        return {

            "extractions": result

        }

    # Gemini returned expected object
    if isinstance(result, dict):

        if "extractions" in result:

            return result

        # Sometimes Gemini returns a single object
        return {

            "extractions": [result]

        }

    raise ValueError(
        "Unexpected Gemini response."
    )


# --------------------------------------------------------
# Batch extraction
# --------------------------------------------------------

def extract_batch(
    sections,
    country,
    act,
    retries=6
):

    prompt = build_prompt(
        sections,
        country,
        act
    )

    wait = 10

    for attempt in range(retries):

        try:
            print("=" * 70)
            print("Sending prompt to Ollama")
            print(f"Characters: {len(prompt):,}")
            print(f"Approx tokens: {len(prompt)//4:,}")
            print("=" * 70)
            parsed = parse_json(
                call_gemini(prompt)
            )

            return normalise_output(
                parsed,
                sections
            )

        except Exception as e:

            print()

            print("=" * 70)
            print(f"{act}")
            print(f"Attempt {attempt+1}/{retries}")
            print(type(e).__name__)
            print(e)
            print("=" * 70)

            time.sleep(wait)

            wait = min(wait * 2, 120)

    # ----------------------------------------------------
    # Fallback
    # ----------------------------------------------------

    return {

        "extractions": [

            {

                "section": s["identifier"],

                "heading": s["heading"],

                "summary": "",

                "authority": "",

                "financial_relevance": "Unknown",

                "confidence": "Low",

                "topics": [],

                "data_types": [],

                "requirements": [],

                "source_quote": ""

            }

            for s in sections

        ]

    }