"""
LLM client + runtime configuration for the extraction pipeline.

Two providers are supported behind one `generate()` call:

  * ollama  (default) — a local model, no data leaves the machine
  * gemini            — the Google Gemini API, for fast full rebuilds

Select with LLM_PROVIDER.  All other knobs are environment variables so
the pipeline can be tuned without editing code:

    LLM_PROVIDER     "ollama" (default) or "gemini"
    LLM_MODEL        Ollama model tag (default "qwen3:8b")
    LLM_HOST         Ollama host (default http://localhost:11434)
    LLM_THINK        "1" to allow qwen3 chain-of-thought (default off)
    LLM_KEEP_ALIVE   how long Ollama keeps the model resident (default 30m)
    LLM_NUM_CTX_MAX  hard ceiling for the context window (default 16384)
    LLM_BATCH_TOKENS token budget per batch of sections (default 6000)
    LLM_NUM_GPU      GPU layers to offload (unset = Ollama auto-detects;
                     999 forces the whole model onto the GPU)

    GEMINI_API_KEY   API key (read from environment or .env)
    GEMINI_MODEL     Gemini model (default "gemini-2.0-flash")
"""

import os
import threading

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()

# ---- Ollama settings -------------------------------------------------
# qwen3:8b by default now that extraction runs on a GPU — richer summaries
# and requirements than the 4b that CPU speed forced.  Override with
# LLM_MODEL.  Needs `ollama pull qwen3:8b`.
MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
HOST = os.getenv("LLM_HOST", "http://localhost:11434")

# qwen3 is a hybrid reasoning model.  Its <think> pass roughly triples
# generation time for what is pure structured extraction, so it is OFF
# by default.  Set LLM_THINK=1 to re-enable it for debugging.
THINK = os.getenv("LLM_THINK", "0") == "1"

# Keep the model resident between batches so it is not reloaded.
KEEP_ALIVE = os.getenv("LLM_KEEP_ALIVE", "30m")

# Per-request timeout (seconds).  Without this a single hung or runaway
# generation stalls the whole run indefinitely; with it the call raises,
# the batch is retried, and if it keeps failing the section is flagged and
# the run moves on.  Generous by default so legitimate slow calls survive.
TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))

# How many batches to send to Ollama at once.  1 = serial (default).
# Higher values use an idle GPU better and cut wall-clock — set the Ollama
# server's OLLAMA_NUM_PARALLEL to at least this, or the requests just queue.
CONCURRENCY = max(1, int(os.getenv("LLM_CONCURRENCY", "1")))

# GPU layer offload.  Ollama already offloads as many layers as fit the
# card automatically, so this is left unset by default.  Set it to force a
# specific count — e.g. LLM_NUM_GPU=999 to push the whole model onto the
# GPU (fails loudly if it does not fit, which is what you want to know).
_num_gpu = os.getenv("LLM_NUM_GPU")
NUM_GPU = int(_num_gpu) if _num_gpu not in (None, "") else None

# The KV cache is allocated for the whole context window, so an oversized
# num_ctx wastes memory and slows prompt processing.  We size the window
# to the actual prompt at call time and clamp it here.
NUM_CTX_MAX = int(os.getenv("LLM_NUM_CTX_MAX", "8192"))
NUM_CTX_MIN = 2048

# Approximate token budget for a single batch prompt (excluding the
# shared system prompt).  Batches are packed up to this size...
BATCH_TOKENS = int(os.getenv("LLM_BATCH_TOKENS", "6000"))

# ...but also capped at this many sections, whichever comes first.  A batch
# of many small sections makes the model emit one very large JSON response
# (all their summaries + requirements), which is slow and error-prone —
# packing 15-20 sections was timing out where 5 succeeded.
BATCH_SECTIONS = int(os.getenv("LLM_BATCH_SECTIONS", "6"))

# ---- Gemini settings -------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def estimate_tokens(text: str) -> int:
    """Rough char/4 token estimate — good enough for batch packing."""
    return len(text) // 4


def context_window(prompt_tokens: int) -> int:
    """Pick a power-of-two context window that fits prompt + output.

    Structured extraction output roughly tracks input length, so we
    reserve the prompt size again (min 3072) as headroom.  Batches are
    capped at BATCH_SECTIONS so output stays bounded; an oversized window
    only lets the model run longer and risk the request timeout.
    """
    needed = prompt_tokens + max(3072, prompt_tokens // 2)
    window = NUM_CTX_MIN
    while window < needed and window < NUM_CTX_MAX:
        window *= 2
    return min(window, NUM_CTX_MAX)


# ----------------------------------------------------------------------
# Ollama backend
# ----------------------------------------------------------------------

_ollama_client = None
_ollama_lock = threading.Lock()


def _ollama_generate(system: str, prompt: str) -> str:
    global _ollama_client
    if _ollama_client is None:
        with _ollama_lock:
            if _ollama_client is None:
                from ollama import Client
                # timeout so one hung request cannot stall the whole run.
                _ollama_client = Client(host=HOST, timeout=TIMEOUT)

    num_ctx = context_window(
        estimate_tokens(system) + estimate_tokens(prompt)
    )

    options = {"temperature": 0, "num_ctx": num_ctx}
    if NUM_GPU is not None:
        options["num_gpu"] = NUM_GPU

    response = _ollama_client.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        options=options,
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

# The provider can change at runtime: if Gemini runs out of quota we
# fall back to local Ollama for the rest of the run.
_active_provider = PROVIDER


def _is_quota_error(exc) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(
        s in text for s in (
            "429", "403", "resource_exhausted", "quota",
            "rate limit", "rate_limit", "exhausted", "permission",
        )
    )


def generate(system: str, prompt: str) -> str:
    """Send one system+user prompt to the active provider.

    When the active provider is Gemini and it fails (quota/rate limit, or
    any error), we switch to local Ollama for the remainder of the run so
    an unsupervised job keeps making progress instead of stalling.
    """
    global _active_provider

    if _active_provider == "gemini":
        try:
            return _gemini_generate(system, prompt)
        except Exception as exc:
            reason = "quota/rate limit" if _is_quota_error(exc) else \
                f"{type(exc).__name__}"
            print(
                f"[client] Gemini unavailable ({reason}); "
                f"switching to local Ollama ({MODEL}) for the rest of the run."
            )
            _active_provider = "ollama"

    return _ollama_generate(system, prompt)


def describe() -> str:
    if PROVIDER == "gemini":
        return f"gemini:{GEMINI_MODEL} (falls back to ollama:{MODEL})"
    return f"ollama:{MODEL}"
