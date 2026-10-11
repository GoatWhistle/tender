import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _optional(name: str) -> str | None:
    return os.environ.get(name) or None


@dataclass(frozen=True, slots=True)
class Settings:
    data: Path = field(default_factory=lambda: Path(_env("RAG_DATA", "data")))
    host: str = field(default_factory=lambda: _env("RAG_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_env("RAG_PORT", "8100")))

    embeddings_url: str = field(
        default_factory=lambda: _env("EMBEDDINGS_URL", "https://api.polza.ai/api/v1")
    )
    embeddings_model: str = field(
        default_factory=lambda: _env("EMBEDDINGS_MODEL", "qwen/qwen3-embedding-8b")
    )
    embeddings_api_key: str | None = field(
        default_factory=lambda: _optional("EMBEDDINGS_API_KEY")
    )
    embeddings_query_instruction: str = "Given a product description from a supplier, retrieve the matching KTRU catalog position"
    embed_batch: int = field(default_factory=lambda: int(_env("EMBED_BATCH", "32")))
    embed_concurrency: int = field(
        default_factory=lambda: int(_env("EMBED_CONCURRENCY", "8"))
    )

    claude_fast_model: str = field(
        default_factory=lambda: _env("CLAUDE_FAST_MODEL", "haiku")
    )
    claude_smart_model: str = field(
        default_factory=lambda: _env("CLAUDE_SMART_MODEL", "sonnet")
    )

    llm_url: str | None = field(default_factory=lambda: _optional("LLM_URL"))
    llm_api_key: str | None = field(default_factory=lambda: _optional("LLM_API_KEY"))
    llm_fast_model: str = field(
        default_factory=lambda: _env("LLM_FAST_MODEL", "gpt-5-mini")
    )
    llm_smart_model: str = field(
        default_factory=lambda: _env("LLM_SMART_MODEL", "gpt-5")
    )
    llm_reasoning: bool = field(
        default_factory=lambda: _env("LLM_REASONING", "false") == "true"
    )
    llm_timeout: float = field(
        default_factory=lambda: float(_env("LLM_TIMEOUT", "180"))
    )


def load_settings() -> Settings:
    load_dotenv()
    return Settings()
