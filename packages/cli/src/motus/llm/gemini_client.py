# Copyright (c) 2024-2025 Veritas Collaborative, LLC
# SPDX-License-Identifier: LicenseRef-MCSL

"""
Gemini LLM Client for Motus.

This module provides the integration with Google's Gemini 2.0 Flash model
for internal Motus reasoning tasks (summarization, drift detection).
"""

import os
from typing import Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None

from ..logging import get_logger

logger = get_logger(__name__)


class GeminiClient:
    """Client for interacting with Gemini models."""

    def __init__(self, model_name: str = "gemini-2.0-flash-exp"):
        if genai is None:
            raise ImportError(
                "google-genai package is required. Install with: pip install google-genai"
            )

        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment")

        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name

    def generate_content(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate content using Gemini."""
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,  # Low temperature for deterministic tasks
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )

            return response.text if response.text else ""

        except Exception as e:
            logger.error(
                "Gemini generation failed",
                error_type=type(e).__name__,
                error=str(e)
            )
            return f"Error generating content: {str(e)}"

    def summarize_text(self, text: str, max_words: int = 100) -> str:
        """Summarize text using Gemini."""
        prompt = f"Summarize the following text in {max_words} words or less, capturing the key technical decisions and intent:\n\n{text}"
        return self.generate_content(prompt, system_instruction="You are a technical summarizer.")

_client_instance = None

def get_gemini_client() -> GeminiClient:
    """Get or create the global Gemini client instance."""
    global _client_instance
    if _client_instance is None:
        _client_instance = GeminiClient()
    return _client_instance
