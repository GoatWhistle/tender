from dataclasses import dataclass

from rag.domain.catalog import Position
from rag.domain.comparison import (
    COMPARE_MAX,
    COMPARE_MIN,
    Row,
    characteristic_rows,
    meta_row,
)
from rag.domain.errors import IndexNotReady, InputError, NotFound, PositionNotFound
from rag.domain.search import Hit
from rag.usecase.interface import Catalog
from rag.usecase.search import FOUND_LIMIT, PositionSearch


@dataclass(frozen=True, slots=True)
class Comparison:
    positions: list[Position]
    okpd2: Row
    units: Row
    characteristics: list[Row]


class CatalogQueries:
    def __init__(self, catalog: Catalog, search: PositionSearch) -> None:
        self._catalog = catalog
        self._search = search

    def ready(self) -> bool:
        return self._catalog.ready

    def require(self) -> None:
        if not self._catalog.ready:
            raise IndexNotReady()

    async def find(self, text: str, semantic: bool) -> list[Position]:
        self.require()
        if semantic:
            hits: list[Hit] = await self._search.semantic(text.strip(), FOUND_LIMIT)
            return [hit.position for hit in hits]
        return self._search.by_name(text)

    def details(self, code: str) -> Position:
        self.require()
        position = self._catalog.position(code)
        if position is None:
            raise PositionNotFound()
        return position

    def compare(self, codes: list[str]) -> Comparison:
        self.require()
        unique = list(dict.fromkeys(codes))
        if not COMPARE_MIN <= len(unique) <= COMPARE_MAX:
            raise InputError(f"сравниваются от {COMPARE_MIN} до {COMPARE_MAX} позиций")
        positions = {code: self._catalog.position(code) for code in unique}
        if missing := [code for code, p in positions.items() if p is None]:
            raise NotFound(f"нет таких позиций КТРУ: {', '.join(missing)}")
        found = [p for p in positions.values() if p is not None]
        return Comparison(
            positions=found,
            okpd2=meta_row("okpd2", [(p.okpd2,) for p in found]),
            units=meta_row("units", [tuple(sorted(p.units)) for p in found]),
            characteristics=characteristic_rows(found),
        )
