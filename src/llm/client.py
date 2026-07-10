"""
LLM client + runtime configuration for the extraction pipeline.

Two providers are supported behind one `generate()` call:

  * ollama  (default) — a local model, no data leaves the machine
  * gemini            — the Google Gemini API, for fast full rebuilds

Select with LLM_PROVIDER.  All other knobs are environment variables so
the pipeline can be tuned without editing code:

    LLM_PROVIDER     "ollama" (default) or "gemini"
    LLM_MODEL        Ollama model tag (default "qwen3:4b")
    LLM_HOST         Ollama host (default http://localhost:11434)
    LLM_THINK        "1" to allow qwen3 chain-of-thought (default off)
    LLM_KEEP_ALIVE   how long Ollama keeps the model resident (default 30m)
    LLM_NUM_CTX_MAX  hard ceiling for the context window (default 16384)
    LLM_BATCH_TOKENS token budget per batch of sections (default 6000)

    GEMINI_API_KEY   API key (read from environment or .env)
    GEMINI_MODEL     Gemini model (default "gemini-2.0-flash")
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# ---- Ollama settings -------------------------------------------------
MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
HOST = os.getenv("LLM_HOST", "http://localhost:11434")

# qwen3 is a hybrid reasoning model.  Its <think> pass roughly triples
# generation time for what is pure structured extraction, so it is OFF
# by default.  Set LLM_THINK=1 to re-enable it for debugging.
THINK = os.getenv("LLM_THINK", "0") == "1"

# Keep the model resident between batches so it is not reloaded.
KEEP_ALIVE = os.getenv("LLM_KEEP_ALIVE", "30m")

# The KV cache is allocated for the whole context window, so an oversized
# num_ctx wastes memory and slows prompt processing.  We size the window
# to the actual prompt at call time and clamp it here.
NUM_CTX_MAX = int(os.getenv("LLM_NUM_CTX_MAX", "16384"))
NUM_CTX_MIN = 2048

# Approximate token budget for a single batch prompt (excluding the
# shared system prompt).  Batches are packed up to this size instead of
# a fixed section count.
BATCH_TOKENS = int(os.getenv("LLM_BATCH_TOKENS", "6000"))

# ---- Gemini settings -------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def estimate_tokens(text: str) -> int:
    """Rough char/4 token estimate — good enough for batch packing."""
    return len(text) // 4


def context_window(prompt_tokens: int) -> int:
    """Pick a power-of-two context window that fits prompt + output.

    Structured extraction output roughly tracks input length, so we
    reserve at least the prompt size again (min 2048) as headroom.  Too
    small a window truncates the JSON and forces a retry.
    """
    needed = prompt_tokens + max(2048, prompt_tokens // 2)
    window = NUM_CTX_MIN
    while window < needed and window < NUM_CTX_MAX:
        window *= 2
    return min(window, NUM_CTX_MAX)


# ----------------------------------------------------------------------
# Ollama backend
# ----------------------------------------------------------------------

_ollama_client = None


def _ollama_generate(system: str, prompt: str) -> str:
    global _ollama_client
    if _ollama_client is None:
        from ollama import Client
        _ollama_client = Client(host=HOST)

    num_ctx = context_window(
        estimate_tokens(system) + estimate_tokens(prompt)
    )

    response = _ollama_client.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        options={"temperature": 0, "num_ctx": num_ctx},
        format="json",
        think=THINK,
        keep_alive=KEEP_ALIVE,
    )
    return response.message.content


# ----------------------------------------------------------------------
# Gemini backend (optional)
# ----------------------------------------------------------------------

_gemini_client = None


def _gemini_generate(system: str, prompt: str) -> str:
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set "
                "(put it in .env or the environment)."
            )
        _gemini_client = genai.Client(api_key=api_key)

    from google.genai import types

    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    return response.text


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------

def generate(system: str, prompt: str) -> str:
    """Send one system+user prompt to the configured provider."""
    if PROVIDER == "gemini":
        return _gemini_generate(system, prompt)
    return _ollama_generate(system, prompt)


def describe() -> str:
    if PROVIDER == "gemini":
        return f"gemini:{GEMINI_MODEL}"
    return f"ollama:{MODEL}"
