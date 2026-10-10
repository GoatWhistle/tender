from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Embedding:
    index: int
    embedding: list[float]
    object: str = "embedding"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Embedding":
        return cls(
            index=d["index"],
            embedding=d["embedding"],
            object=d.get("object", "embedding"),
        )


@dataclass(frozen=True, slots=True)
class Usage:
    prompt_tokens: int
    total_tokens: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Usage":
        return cls(
            prompt_tokens=d.get("prompt_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
        )


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    data: list[Embedding]
    model: str
    usage: Usage
    object: str = "list"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EmbeddingResponse":
        return cls(
            data=[Embedding.from_dict(x) for x in d["data"]],
            model=d.get("model", ""),
            usage=Usage.from_dict(d.get("usage") or {}),
            object=d.get("object", "list"),
        )


@dataclass(frozen=True, slots=True)
class Value:
    text: str | None = None
    unit: str | None = None
    unit_code: str | None = None
    min: float | None = None
    min_op: str | None = None
    max: float | None = None
    max_op: str | None = None
    concrete: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class Characteristic:
    code: str
    name: str
    quantitative: bool
    kind: str
    required: bool
    values: tuple[Value, ...]


@dataclass(frozen=True, slots=True)
class Position:
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    units: tuple[str, ...]
    rubrics: tuple[str, ...]
    is_template: bool
    parent: str | None
    characteristics: tuple[Characteristic, ...]
