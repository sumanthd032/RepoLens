"""Application configuration.

A single :class:`Config` object is the source of truth for every tunable in RepoLens.
Values are resolved with the following precedence (highest first):

1. Explicit constructor arguments.
2. Environment variables (and a ``.env`` file).
3. A ``.repolens.toml`` file (project-local, or ``~/.repolens/config.toml`` globally).
4. The defaults declared on the models below.

The default LLM backend is **Groq** (a free, OpenAI-compatible hosted tier) so RepoLens
works out of the box without a paid API key. Embedding/reranker/NLI models run locally.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

LLMBackend = Literal["groq", "anthropic", "openai", "ollama"]
Severity = Literal["low", "medium", "high"]

# Where RepoLens looks for a TOML config file, in priority order.
_PROJECT_TOML = Path(".repolens.toml")
_GLOBAL_TOML = Path.home() / ".repolens" / "config.toml"


def _resolve_toml_path() -> Path | None:
    """Return the first config TOML that exists, or ``None`` if there is none."""
    for candidate in (_PROJECT_TOML, _GLOBAL_TOML):
        if candidate.is_file():
            return candidate
    return None


class IndexConfig(BaseModel):
    """``[index]`` — ingestion and embedding settings."""

    languages: list[str] = Field(
        default_factory=lambda: [
            "python",
            "go",
            "javascript",
            "typescript",
            "rust",
            "c",
            "cpp",
            "java",
        ]
    )
    embedding_model: str = "jinaai/jina-embeddings-v2-base-code"
    max_chunk_tokens: int = Field(default=512, gt=0)
    chunk_overlap_tokens: int = Field(default=64, ge=0)
    ignore_file: str = ".repolensignore"


class RetrievalConfig(BaseModel):
    """``[retrieval]`` — hybrid search and reranking settings."""

    top_k_dense: int = Field(default=20, gt=0)
    top_k_bm25: int = Field(default=20, gt=0)
    top_k_rerank: int = Field(default=8, gt=0)
    graph_expansion_hops: int = Field(default=1, ge=0)


class GenerationConfig(BaseModel):
    """``[generation]`` — LLM backend and answer-verification settings."""

    llm_backend: LLMBackend = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    max_answer_tokens: int = Field(default=2048, gt=0)
    max_retries: int = Field(default=2, ge=0)
    grounding_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class DriftConfig(BaseModel):
    """``[drift]`` — documentation-drift detection settings."""

    ci_mode: bool = False
    severity_threshold: Severity = "low"


class Config(BaseSettings):
    """Top-level configuration object loaded from env, ``.env`` and ``.repolens.toml``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Runtime / storage ---------------------------------------------------
    data_dir: Path = Field(
        default=Path("~/.repolens"),
        validation_alias=AliasChoices("REPOLENS_DATA_DIR", "data_dir"),
    )
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("REPOLENS_LOG_LEVEL", "log_level"),
    )

    # --- LLM credentials -----------------------------------------------------
    groq_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key")
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key")
    )
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key")
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "ollama_base_url"),
    )

    # --- Nested sections (populated from the TOML tables) --------------------
    index: IndexConfig = Field(default_factory=IndexConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)

    @field_validator("data_dir", mode="after")
    @classmethod
    def _expand_data_dir(cls, value: Path) -> Path:
        """Expand ``~`` and make the data directory absolute."""
        return value.expanduser()

    @field_validator("log_level", mode="after")
    @classmethod
    def _normalise_log_level(cls, value: str) -> str:
        return value.upper()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Insert a TOML source below env/.env so env always wins over the file."""
        sources: list[PydanticBaseSettingsSource] = [
            init_settings,
            env_settings,
            dotenv_settings,
        ]
        toml_path = _resolve_toml_path()
        if toml_path is not None:
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_path))
        sources.append(file_secret_settings)
        return tuple(sources)


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return the cached, validated application configuration.

    Cached so the TOML/env files are read only once per process. Call
    :func:`get_config.cache_clear` (e.g. in tests) to force a reload.
    """
    return Config()
