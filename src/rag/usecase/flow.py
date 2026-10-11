from rag.domain.catalog import Position
from rag.domain.clarify import questions
from rag.domain.sessions import Session, Stage, next_step
from rag.usecase.clarify import CharacteristicReader
from rag.usecase.interface import Catalog


class SessionFlow:
    def __init__(self, catalog: Catalog, reader: CharacteristicReader) -> None:
        self._catalog = catalog
        self._reader = reader

    def leaves(self, group: Position) -> list[Position]:
        return self._catalog.leaves(group)

    async def enter_group(self, s: Session, group: Position) -> None:
        s.enter_group(group, self._catalog.leaves(group))
        found = await self._reader.extract(s.corrected, questions(s.leaves, {}))
        s.from_description = {n: v[0] for n, v in found.items()}
        s.answers = dict(s.from_description)
        await self.advance(s)

    async def advance(self, s: Session) -> None:
        s.leaves, step = next_step(s.leaves, s.answers)
        if step.stage == Stage.SPEC and step.position is not None:
            if step.reason:
                s.selection_reason = step.reason
            await self.enter_spec(s, step.position)
            return
        s.stage = step.stage
        if step.message:
            s.message = step.message

    async def enter_spec(self, s: Session, p: Position) -> None:
        s.enter_spec(p)
        s.fill_from_description(
            await self._reader.extract("\n".join(s.context), s.characteristics)
        )
