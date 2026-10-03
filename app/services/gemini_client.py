from typing import Optional

from app.config import get_settings


_client = None


def get_gemini_client():
    global _client

    if _client is not None:
        return _client

    settings = get_settings()

    if not settings.gemini_api_key:
        return None

    try:
        from google import genai

        _client = genai.Client(
            api_key=settings.gemini_api_key
        )

        return _client

    except ImportError as exc:
        raise RuntimeError(
            "google-genai is not installed. "
            "Run: pip install google-genai"
        ) from exc


def gemini_available() -> bool:
    settings = get_settings()

    return bool(settings.gemini_api_key)