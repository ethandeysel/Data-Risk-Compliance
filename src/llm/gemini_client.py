"""
Gemini API client.

Loads the API key and creates a reusable client.
"""

import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY not found in .env"
    )

MODEL = "gemini-2.5-flash"

client = genai.Client(
    api_key=API_KEY
)