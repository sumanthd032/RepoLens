"""Answer generation: prompt builder, LLM backends, citation validator, grounding scorer."""

from repolens.generation.llm import BaseLLMClient, create_llm_client
from repolens.generation.prompt import (
    NOT_FOUND_MARKER,
    build_system_prompt,
    build_user_message,
)
from repolens.generation.scorer import GroundingResult, GroundingScorer
from repolens.generation.validator import (
    Citation,
    CitationValidator,
    ValidationResult,
    parse_citations,
)

__all__ = [
    "NOT_FOUND_MARKER",
    "BaseLLMClient",
    "Citation",
    "CitationValidator",
    "GroundingResult",
    "GroundingScorer",
    "ValidationResult",
    "build_system_prompt",
    "build_user_message",
    "create_llm_client",
    "parse_citations",
]
