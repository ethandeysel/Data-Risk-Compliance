"""
Backward-compatibility shim.

The client now lives in client.py and supports multiple providers.
This module is kept so older imports keep working.
"""

from .client import MODEL, generate  # noqa: F401
