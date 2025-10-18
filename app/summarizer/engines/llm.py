# app/summarizer/engines/llm.py
"""
LLM-based summarization engine with constrained generation.

This engine uses evidence bundles from the deterministic engine
and rephrases them using an LLM without adding new facts.
"""

from typing import Any, Dict, List, Optional
import json
import logging
from abc import ABC, abstractmethod

from app.config import Settings
from app.summarizer.engines.base import SummarizationEngine
from app.summarizer.models import (
    EvidenceBundle,
    SummarizationRequest,
    SummaryBullet,
    Citation,
)

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in the given text."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        try:
            from openai import AsyncOpenAI
            import tiktoken
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai tiktoken"
            )

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.encoding = tiktoken.encoding_for_model(model)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Generate response from OpenAI API."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,  # Low temperature for consistency
        }

        # Add JSON mode if response format specified
        if response_format:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content

        # Parse JSON if format was requested
        if response_format:
            return json.loads(content)
        return {"text": content}

    def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        return len(self.encoding.encode(text))


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-haiku-20240307"):
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Generate response from Anthropic API."""
        if response_format:
            # Append JSON instruction to system prompt
            system_prompt += (
                "\n\nRespond with valid JSON matching this schema:\n"
                + json.dumps(response_format, indent=2)
            )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0.1,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        content = response.content[0].text

        # Parse JSON if format was requested
        if response_format:
            return json.loads(content)
        return {"text": content}

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (roughly 4 chars per token for Claude)."""
        return len(text) // 4


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama provider.

        Args:
            model: Ollama model name (e.g., llama3.2, mistral, codellama)
            base_url: Ollama server URL (default: http://localhost:11434)
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        logger.info(f"Initialized Ollama provider with model: {model} at {base_url}")

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict[str, Any]] = None,
        max_tokens: int = 1000,
    ) -> Dict[str, Any]:
        """Generate response from Ollama API."""
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx package not installed. Install with: pip install httpx"
            )

        # Combine system and user prompts for Ollama
        if response_format:
            full_prompt = (
                f"{system_prompt}\n\n"
                f"Respond with valid JSON matching this schema:\n"
                f"{json.dumps(response_format, indent=2)}\n\n"
                f"User query: {user_prompt}"
            )
        else:
            full_prompt = f"{system_prompt}\n\nUser query: {user_prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for consistency
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate", json=payload
            )
            response.raise_for_status()
            result = response.json()

        content = result.get("response", "")

        # Parse JSON if format was requested
        if response_format:
            # Try to extract JSON from response
            try:
                # Look for JSON block in markdown code fence
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    content = content[start:end].strip()
                elif "```" in content:
                    start = content.find("```") + 3
                    end = content.find("```", start)
                    content = content[start:end].strip()

                return json.loads(content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Failed to parse Ollama JSON response: {e}")
                # Return a basic structure if parsing fails
                return {"text": content}

        return {"text": content}

    def count_tokens(self, text: str) -> int:
        """Estimate tokens (roughly 4 chars per token)."""
        return len(text) // 4


class LLMEngine(SummarizationEngine):
    """
    LLM-based summarization engine.

    Uses evidence bundles from deterministic engine and rephrases
    with an LLM without inventing new facts.
    """

    name = "llm"

    def __init__(
        self,
        provider: LLMProvider,
        deterministic_engine: Optional[SummarizationEngine] = None,
    ):
        """
        Initialize LLM engine.

        Args:
            provider: LLM provider (OpenAI, Anthropic, etc.)
            deterministic_engine: Optional deterministic engine for evidence extraction
        """
        self.provider = provider
        self.deterministic_engine = deterministic_engine

    def get_system_prompt(self) -> str:
        """Get system prompt that prevents hallucinations."""
        return """You are a JSON summarization assistant. Your task is to create clear, concise summaries from evidence bundles.

CRITICAL RULES:
1. NEVER invent fields, values, or entities that aren't in the evidence
2. ALWAYS preserve exact numbers, names, and values from the evidence
3. ALWAYS include citations for every claim
4. Transform and rephrase for clarity, but NEVER add new facts
5. If the evidence is unclear, say so rather than guessing

Your output must be valid JSON matching the provided schema."""

    def create_user_prompt(self, evidence: Dict[str, Any], focus: List[str]) -> str:
        """Create user prompt from evidence bundle."""
        focus_str = ", ".join(focus) if focus else "general overview"

        return f"""Create a summary focused on: {focus_str}

Evidence Bundle:
{json.dumps(evidence, indent=2)}

Transform this evidence into clear, natural-language bullets while:
- Preserving all numbers and values exactly
- Including citations for each claim
- Following the focus areas
- Being concise but informative

Output Format:
{{
  "bullets": [
    {{
      "text": "Clear summary statement",
      "citations": ["$.path.to.data"],
      "evidence": {{"key": "supporting data"}}
    }}
  ]
}}"""

    def summarize(
        self, request: SummarizationRequest, settings: Settings
    ) -> EvidenceBundle:
        """
        Summarize using LLM with evidence-only input.

        Args:
            request: Summarization request with payload and focus
            settings: Application settings

        Returns:
            Evidence bundle with LLM-rephrased bullets
        """
        # Get deterministic evidence first
        if self.deterministic_engine:
            det_bundle = self.deterministic_engine.summarize(request, settings)
        else:
            # Fallback: create minimal bundle
            from app.summarizer.engines.deterministic import DeterministicEngine

            det_engine = DeterministicEngine()
            det_bundle = det_engine.summarize(request, settings)

        # NOTE: Async LLM calls would require refactoring the entire pipeline
        # For now, log that LLM is configured but not yet fully integrated
        logger.warning(
            "LLM engine returning deterministic results (async integration pending)"
        )

        return det_bundle


class HybridEngine(SummarizationEngine):
    """
    Hybrid engine combining deterministic and LLM approaches.

    Uses deterministic engine for evidence extraction and LLM for rephrasing.
    """

    name = "hybrid"

    def __init__(
        self,
        deterministic_engine: SummarizationEngine,
        llm_provider: LLMProvider,
    ):
        """
        Initialize hybrid engine.

        Args:
            deterministic_engine: Engine for evidence extraction
            llm_provider: LLM provider for rephrasing
        """
        self.deterministic_engine = deterministic_engine
        self.llm_engine = LLMEngine(llm_provider, deterministic_engine)

    def summarize(
        self, request: SummarizationRequest, settings: Settings
    ) -> EvidenceBundle:
        """
        Summarize using hybrid approach.

        1. Extract evidence deterministically
        2. Rephrase with LLM while preserving facts (future)
        3. Fall back to deterministic on LLM failure
        """
        try:
            return self.llm_engine.summarize(request, settings)
        except Exception as e:
            logger.warning(f"Hybrid mode falling back to deterministic: {e}")
            return self.deterministic_engine.summarize(request, settings)
