"""Схемы поиска групп КТРУ в API."""

from pydantic import BaseModel, Field, field_validator

from app.domain.catalog import CATEGORIES
from app.domain.search import Contribution, FoundBy, GroupMatch, Method, SearchMessage
from app.usecase.search import DEFAULT_LIMIT, MAX_LIMIT


class SearchIn(BaseModel):
    text: str = Field(min_length=1, description="Описание товара; может содержать код КТРУ")
    category: str | None = Field(
        default=None, description=f"Только группы категории: {', '.join(CATEGORIES)}"
    )
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("описание из одних пробелов")
        return value

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str | None) -> str | None:
        if value is not None and value not in CATEGORIES:
            raise ValueError(f"категория {value!r} не из {list(CATEGORIES)}")
        return value


class MethodOut(BaseModel):
    # Ранг в списке метода с 1; `None` — метод группу не нашёл.
    rank: int | None
    # Слагаемое RRF.
    score: float

    @classmethod
    def of(cls, c: Contribution) -> "MethodOut":
        return cls(rank=c.rank, score=c.score)


class GroupMatchOut(BaseModel):
    code: str
    name: str
    category: str
    # Сумма слагаемых `methods`.
    score: float
    methods: dict[Method, MethodOut]
    found_by: FoundBy

    @classmethod
    def of(cls, m: GroupMatch) -> "GroupMatchOut":
        return cls(
            code=m.group.code,
            name=m.group.name,
            category=m.group.category,
            score=m.score,
            methods={c.method: MethodOut.of(c) for c in m.methods},
            found_by=m.found_by,
        )


class MessageOut(BaseModel):
    code: str
    text: str

    @classmethod
    def of(cls, m: SearchMessage) -> "MessageOut":
        return cls(code=m.code, text=m.text)


class SearchOut(BaseModel):
    # Описание как пришло, без нормализации.
    text: str
    groups: list[GroupMatchOut]
    messages: list[MessageOut]
