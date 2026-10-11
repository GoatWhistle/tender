import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from rag.domain.clarify import questions
from rag.domain.errors import InputError, SessionNotFound, StageError
from rag.domain.sessions import Origin, Outcome, Session, Stage
from rag.domain.spec import Extra, Verdict, band
from rag.domain.suggestions import Suggestion
from rag.usecase.clarify import CharacteristicReader
from rag.usecase.conversation import Conversation
from rag.usecase.correction import Corrector
from rag.usecase.flow import SessionFlow
from rag.usecase.interface import SessionsRepository
from rag.usecase.locks import KeyedLocks
from rag.usecase.rerank import Reranker
from rag.usecase.search import PositionSearch
from rag.usecase.spec import ExtraValidator
from rag.usecase.suggest import Suggester


class Sessions:
    def __init__(
        self,
        repository: SessionsRepository,
        flow: SessionFlow,
        corrector: Corrector,
        search: PositionSearch,
        reranker: Reranker,
        reader: CharacteristicReader,
        validator: ExtraValidator,
        suggester: Suggester,
        conversation: Conversation,
    ) -> None:
        self._repository = repository
        self._flow = flow
        self._corrector = corrector
        self._search = search
        self._reranker = reranker
        self._reader = reader
        self._validator = validator
        self._suggester = suggester
        self._conversation = conversation
        self._locks = KeyedLocks()
        self._suggestions: dict[tuple[str, str], asyncio.Task[list[Suggestion]]] = {}

    @asynccontextmanager
    async def _session(self, session_id: str) -> AsyncIterator[Session]:
        if self._repository.get(session_id) is None:
            raise SessionNotFound()
        async with self._locks(session_id):
            s = self._repository.get(session_id)
            if s is None:
                raise SessionNotFound()
            yield s

    def read(self, session_id: str) -> Session:
        s = self._repository.get(session_id)
        if s is None:
            raise SessionNotFound()
        return s

    def adopt(self, s: Session) -> Session:
        self._repository.add(s)
        return s

    async def start(self, text: str) -> Session:
        if not text.strip():
            raise InputError("пустое описание")
        corrected = await self._corrector.run(text)
        hits = await self._search.semantic(corrected.corrected)
        ranked = (await self._reranker.run(corrected.corrected, hits)).ranked
        if not ranked:
            raise InputError("поиск ничего не нашёл")
        s = Session.of(corrected, ranked)
        await self._flow.enter_group(s, ranked[0].hit.position)
        return self.adopt(s)

    def delete(self, session_id: str) -> None:
        self.read(session_id)
        self._repository.remove(session_id)
        self._locks.drop(session_id)
        for key in [k for k in self._suggestions if k[0] == session_id]:
            self._suggestions.pop(key).cancel()

    async def answer(
        self, session_id: str, option: int | None, text: str | None
    ) -> Session:
        if (option is None) == (text is None):
            raise InputError("нужно ровно одно из option и text")
        async with self._session(session_id) as s:
            if text is not None:
                await self._reply(s, text)
            else:
                await self._choose(s, option or None)
            return s

    async def _reply(self, s: Session, text: str) -> None:
        s.expect(Stage.CLARIFY)
        if s.question is None:
            raise StageError("вопросов нет")
        got = await self._reader.answer(text, questions(s.leaves, s.answers))
        s.message = got.comment
        if got.picked:
            s.answers.update({name: values[0] for name, values in got.picked.items()})
            s.context.append(text)
            await self._flow.advance(s)

    async def _choose(self, s: Session, option: int | None) -> None:
        s.expect(Stage.CLARIFY)
        q = s.question
        if q is None:
            raise StageError("вопросов нет")
        if option is not None and not 1 <= option <= len(q.options):
            raise InputError(f"номер варианта от 1 до {len(q.options)}")
        s.answers[q.name] = q.options[option - 1] if option else None
        if option:
            s.context.append(f"{q.name}: {q.options[option - 1]}")
        s.message = None
        await self._flow.advance(s)

    async def pick(self, session_id: str, code: str) -> Session:
        async with self._session(session_id) as s:
            s.expect(Stage.CLARIFY, Stage.PICK)
            p = s.leaf(code)
            s.message = None
            await self._flow.enter_spec(s, p)
            return s

    async def switch_group(self, session_id: str, code: str) -> Session:
        async with self._session(session_id) as s:
            await self.enter_ranked_group(s, code)
            return s

    async def enter_ranked_group(self, s: Session, code: str) -> None:
        s.expect(Stage.CLARIFY, Stage.PICK, Stage.SPEC, Stage.FAILED)
        group = s.ranked_group(code)
        s.message = None
        await self._flow.enter_group(s, group)

    async def set_values(
        self, session_id: str, values: dict[str, list[str]]
    ) -> Session:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC)
            for name, labels in values.items():
                q = s.characteristic(name)
                if bad := [label for label in labels if label not in q.options]:
                    raise InputError(f"«{name}»: нет вариантов {bad}")
                if not q.multiple and len(labels) > 1:
                    raise InputError(f"«{name}»: нужен один вариант")
            s.set_values(
                {name: tuple(dict.fromkeys(labels)) for name, labels in values.items()},
                Origin.MANUAL,
            )
            s.message = None
            return s

    async def set_number(self, session_id: str, name: str, x: float | None) -> Session:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC)
            q = next((q for q in s.characteristics if q.name == name), None)
            if q is None or not q.exact:
                raise InputError(f"«{name}» не принимает числовое значение")
            s.message = None
            if x is None:
                s.clear_number(name)
                return s
            label = band(q, x)
            if label is None:
                raise InputError(f"«{name}»: {x:g} не попадает ни в один диапазон КТРУ")
            s.set_values({name: (label,)}, Origin.MANUAL)
            s.numbers[name] = x
            return s

    async def describe(self, session_id: str, text: str, name: str | None) -> Session:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC)
            qs = [s.characteristic(name)] if name is not None else s.characteristics
            got = await self._reader.answer(text, qs)
            s.message = got.comment
            picked = dict(got.picked)
            for q in qs:
                if q.name in got.numbers and (label := band(q, got.numbers[q.name])):
                    picked[q.name] = (label,)
                    s.numbers[q.name] = got.numbers[q.name]
            s.set_values(picked, Origin.ASSISTANT)
            return s

    async def message(self, session_id: str, text: str) -> Session:
        async with self._session(session_id) as s:
            updated = await self._conversation.respond(s, text)
            self._repository.replace(updated)
            return updated

    async def add_extra(self, session_id: str, extra: Extra) -> tuple[Verdict, Session]:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC)
            if not s.extras_allowed:
                raise InputError(
                    "КТРУ запрещает дополнительные характеристики для этой позиции (noNewFeatures)"
                )
            if not extra.complete:
                raise InputError("нужны название и значение")
            assert s.position is not None
            verdict = await self._validator.run(s.position, s.chosen, s.extras, extra)
            if verdict.ok:
                s.extras.append(extra)
            s.message = None
            return verdict, s

    async def remove_extra(self, session_id: str, n: int) -> Session:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC)
            if not 0 <= n < len(s.extras):
                raise InputError(f"нет своей характеристики с номером {n}")
            s.extras.pop(n)
            return s

    async def suggestions(self, session_id: str) -> tuple[str, list[Suggestion]]:
        async with self._session(session_id) as s:
            s.expect(Stage.SPEC, Stage.DONE)
            if s.position is None:
                raise StageError("позиция ещё не определена")
            key = (s.id, s.position.code)
            if key not in self._suggestions or self._suggestions[key].cancelled():
                self._suggestions[key] = asyncio.create_task(self._suggest(s))
            task = self._suggestions[key]
        try:
            items = await asyncio.shield(task)
        except Exception:
            self._suggestions.pop(key, None)
            raise
        return key[1], items

    async def _suggest(self, s: Session) -> list[Suggestion]:
        if not s.extras_allowed or s.position is None:
            return []
        return await self._suggester.run(s.position, "\n".join(s.context))

    async def finish(self, session_id: str) -> Outcome:
        async with self._session(session_id) as s:
            return s.finish()
