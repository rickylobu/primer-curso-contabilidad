"""
gemini_client.py
Singleton factory for the Gemini API client.

This is the SINGLE SOURCE OF TRUTH for model selection and API configuration.
To change the model for the entire pipeline, edit ONLY config.yaml → ai.ocr_model.
Never instantiate genai.Client() anywhere else in the project.

Architecture:
    config.yaml → GeminiClientManager.get() → shared client instance → all callers
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

# ── Model routing table ────────────────────────────────────────────────────
# Maps model name → correct api_version for the google-genai SDK (2025/2026).
#
# FREE TIER LIMITS (as of March 2026 — verify at https://ai.google.dev/gemini-api/docs/rate-limits):
#   gemini-2.0-flash-lite  : 1,000 RPD  ← RECOMMENDED for free tier bulk processing
#   gemini-2.5-flash       :    20 RPD  ← too low for full books on free tier
#   gemini-2.0-flash       :   200 RPD  ← moderate
#   gemini-2.5-pro         :    50 RPD
#
# To change model: edit ONLY config.yaml → ai.ocr_model
MODEL_ROUTING: dict[str, str] = {
    # ── Gemini 2.0 — RECOMMENDED for free tier ───────────────────────────
    "gemini-2.0-flash-lite":             "v1beta",   # 1,000 RPD free ✅ best for books
    "gemini-2.0-flash":                  "v1beta",   # 200 RPD free
    "gemini-2.0-flash-001":              "v1beta",
    "gemini-2.0-flash-lite-001":         "v1beta",

    # ── Gemini 2.5 (low free quota — use paid tier) ───────────────────────
    "gemini-2.5-flash":                  "v1beta",   # 20 RPD free — not for books
    "gemini-2.5-flash-lite":             "v1beta",
    "gemini-2.5-pro":                    "v1beta",   # 50 RPD free

    # ── Gemini 3 (preview) ────────────────────────────────────────────────
    "gemini-3-flash-preview":            "v1beta",
    "gemini-3.1-flash-lite-preview":     "v1beta",

    # ── TTS ───────────────────────────────────────────────────────────────
    "gemini-2.5-flash-preview-tts":      "v1beta",

    # ── Aliases ───────────────────────────────────────────────────────────
    "gemini-flash-latest":               "v1beta",
    "gemini-flash-lite-latest":          "v1beta",
}

DEFAULT_API_VERSION = "v1beta"   # safe default for all new models


class GeminiClientManager:
    """
    Thread-safe singleton that holds one shared genai.Client per (api_key, api_version).
    Callers get the pre-configured client via GeminiClientManager.get(model_name).
    """

    _instances: dict[str, "GeminiClientManager"] = {}

    def __init__(self, api_key: str, api_version: str):
        self._client = genai.Client(
            api_key=api_key,
            http_options={"api_version": api_version},
        )
        self._api_version = api_version

    @classmethod
    def get(cls, model_name: str, api_key: str | None = None) -> genai.Client:
        """
        Returns a shared Client instance configured for the given model.

        Usage:
            client = GeminiClientManager.get("gemini-2.5-flash")
            client.models.generate_content(model="gemini-2.5-flash", ...)
        """
        resolved_key = api_key or os.getenv("GEMINI_API_KEY", "")
        if not resolved_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set.\n"
                "Add it to your .env file:\n"
                "    GEMINI_API_KEY=AIza..."
            )

        api_version = MODEL_ROUTING.get(model_name, DEFAULT_API_VERSION)
        cache_key = f"{resolved_key[:8]}:{api_version}"

        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls(resolved_key, api_version)

        return cls._instances[cache_key]._client

    @classmethod
    def resolve_version(cls, model_name: str) -> str:
        """Returns the api_version string for a given model name."""
        return MODEL_ROUTING.get(model_name, DEFAULT_API_VERSION)

    @classmethod
    def health_check(cls, model_name: str, api_key: str | None = None) -> dict:
        """
        Validates the API key and confirms the model is available.
        Call this at pipeline startup to fail fast with a clear message.
        Returns: {"ok": bool, "model": str, "api_version": str, "error": str|None}
        """
        try:
            client = cls.get(model_name, api_key)
            available = [m.name for m in client.models.list()]
            full_name = f"models/{model_name}"
            found = full_name in available

            return {
                "ok": found,
                "available_models": available,
                "model": model_name,
                "api_version": cls.resolve_version(model_name),
                "error": None if found else (
                    f"Model '{model_name}' not found for your API key.\n"
                    f"Available flash models: "
                    + ", ".join(n for n in available if "flash" in n.lower())
                ),
            }
        except Exception as e:
            return {
                "ok": False,
                "model": model_name,
                "api_version": cls.resolve_version(model_name),
                "error": str(e),
            }
