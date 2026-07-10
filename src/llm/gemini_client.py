"""
Ollama client.

Kept as gemini_client.py so the rest of the
project does not need to change.
"""

from ollama import Client

MODEL = "qwen3:8b"

client = Client(
    host="http://localhost:11434"
)