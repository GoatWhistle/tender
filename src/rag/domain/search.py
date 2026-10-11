from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from rag.domain.catalog import Position, value_text
from rag.domain.inference import Usage

TOP_K = 20
CANDIDATES = 200


@dataclass(frozen=True, slots=True)
class Scored:
    row: int
    code: str
    score: float


@dataclass(frozen=True, slots=True)
class Member:
    row: int
    score: float
    position: Position


@dataclass(frozen=True, slots=True)
class Hit:
    row: int
    score: float
    position: Position
    members: tuple[Member, ...]

    @property
    def siblings(self) -> int:
        return len(self.members)


@dataclass(frozen=True, slots=True)
class Ranked:
    hit: Hit
    relevance: int
    reason: str


@dataclass(frozen=True, slots=True)
class Reranking:
    ranked: list[Ranked]
    exact_match_code: str | None = None
    exact_match_reason: str | None = None
    usage: Usage | None = None


def group_by_name(
    scored: Iterable[Scored], positions: Mapping[str, Position], k: int = TOP_K
) -> list[Hit]:
    groups: dict[str, Hit] = {}
    for s in scored:
        p = positions[s.code]
        member = Member(s.row, s.score, p)
        hit = groups.get(p.name)
        if hit is None:
            if len(groups) == k:
                continue
            groups[p.name] = Hit(s.row, s.score, p, (member,))
        else:
            groups[p.name] = replace(hit, members=(*hit.members, member))
    return list(groups.values())


def expand(hit: Hit) -> list[tuple[Member, dict[str, str]]]:
    per_member = [
        {
            c.name: "; ".join(value_text(v) for v in c.values)
            for c in m.position.characteristics
        }
        for m in hit.members
    ]
    names = {n for chars in per_member for n in chars}
    differing = sorted(
        n for n in names if len({chars.get(n) for chars in per_member}) > 1
    )
    return [
        (m, {n: chars.get(n, "—") for n in differing})
        for m, chars in zip(hit.members, per_member, strict=True)
    ]


def exact_match(ranked: list[Ranked], hits: list[Hit], exact_id: object) -> str | None:
    if not isinstance(exact_id, int) or not 0 <= exact_id < len(hits) or not ranked:
        return None
    code = hits[exact_id].position.code
    top, rest = ranked[0], ranked[1:]
    if top.hit.position.code != code or top.relevance != 100:
        return None
    if any(item.relevance >= 100 for item in rest):
        return None
    return code


def name_rank(code: str, lowered: str, needle: str) -> int | None:
    if code == needle:
        return 0
    if code.startswith(needle):
        return 1
    if lowered.startswith(needle):
        return 2
    if all(token in lowered for token in needle.split()):
        return 3
    return None
