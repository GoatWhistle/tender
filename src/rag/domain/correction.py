from dataclasses import dataclass, field
from typing import Literal

from rag.domain.inference import Usage

type FixKind = Literal["typo", "logic", "unit", "other"]

MAX_DESCRIPTION = 4000


@dataclass(frozen=True, slots=True)
class Fix:
    before: str
    after: str
    kind: FixKind


@dataclass(frozen=True, slots=True)
class Corrected:
    original: str
    corrected: str
    fixes: list[Fix] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    usage: Usage | None = None
