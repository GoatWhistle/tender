import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from rag import conversation
from rag import discovery as ds
from rag import session as ss
from rag.catalog import router as catalog_router
from rag.clarify import FIXED, Question
from rag.comparison import display_differences
from rag.discovery import DiscoveryOut
from rag.index import CODES, POSITIONS, RAW, VECTORS
from rag.ktru import value_text
from rag.models import Value
from rag.search import Index
from rag.session import InputError, Origin, Session, Stage, StageError
from rag.spec import Doubt, Extra
from rag.suggest import Suggestion, load

GROUPS = 5

sessions: dict[str, Session] = {}
locks: dict[str, asyncio.Lock] = {}
suggestions: dict[tuple[str, str], asyncio.Task[list[Suggestion]]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.index = None
    app.state.ready = all(path.exists() for path in (CODES, POSITIONS, RAW, VECTORS))
    if app.state.ready:
        app.state.index = await asyncio.to_thread(Index)
    app.state.ste = asyncio.create_task(asyncio.to_thread(load))
    yield


app = FastAPI(title="RAG КТРУ", lifespan=lifespan)
app.include_router(catalog_router)


@app.exception_handler(StageError)
async def stage_error(request: Request, exc: StageError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InputError)
async def input_error(request: Request, exc: InputError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def model_error(request: Request, exc: RuntimeError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": f"ошибка модели: {exc}"})


class FixOut(BaseModel):
    before: str
    after: str
    kind: str


class GroupOut(BaseModel):
    code: str
    name: str
    okpd2: str
    relevance: int
    reason: str


class QuestionOut(BaseModel):
    name: str
    required: bool
    multiple: bool
    options: list[str]
    counts: list[int]


class CandidateOut(BaseModel):
    code: str
    name: str
    differences: dict[str, str]


class PositionOut(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    fixed: dict[str, str]


class BandOut(BaseModel):
    option: str
    min: float | None
    min_inclusive: bool
    max: float | None
    max_inclusive: bool


class CharacteristicOut(BaseModel):
    name: str
    required: bool
    multiple: bool
    options: list[str]
    values: list[str]
    origin: Origin | None = Field(
        None, description="откуда значение: описание поставщика, помощник или ручной выбор"
    )
    unit: str | None = None
    bands: list[BandOut] = Field(
        [], description="числовые диапазоны КТРУ по возрастанию, по одному на вариант"
    )
    number: float | None = Field(
        None, description="введённое число, если оно ещё соответствует выбранному диапазону"
    )
    warning: Doubt | None = Field(
        None,
        description="число допустимо по КТРУ, но сомнительно: large — больше крайней границы "
        "в 10 раз, small — меньше в 10 раз, negative — отрицательное при неотрицательных границах",
    )


class ExtraIn(BaseModel):
    name: str
    value: str
    reason: str = ""


class ChatMessageOut(BaseModel):
    id: str
    role: str
    text: str


class SessionOut(BaseModel):
    messages: list[ChatMessageOut]
    id: str
    stage: Stage
    description: str
    corrected: str
    fixes: list[FixOut]
    issues: list[str]
    groups: list[GroupOut] = Field(description="группы после ранжирования")
    group: str = Field(description="код группы, по которой идёт уточнение")
    answers: dict[str, str | None]
    candidates: list[CandidateOut]
    question: QuestionOut | None
    position: PositionOut | None
    characteristics: list[CharacteristicOut]
    extras: list[ExtraIn]
    extras_allowed: bool
    missing: list[str]
    message: str | None
    selection_reason: str | None


class SuggestionOut(BaseModel):
    name: str
    unit: str = Field(description="единица измерения или пустая строка")
    options: list[str] = Field(description="типичные значения без единицы")
    value: str = Field(description="значение из описания поставщика или пустая строка")
    evidence: str = Field(description="дословная цитата из описания для value")
    source: str = Field(description="СТЕ — по аналогам из каталога СТЕ, ИИ — по знаниям модели")
    share: float | None = Field(description="доля аналогов СТЕ с этой характеристикой")
    why: str


class SuggestionsOut(BaseModel):
    code: str
    items: list[SuggestionOut]


class VerdictOut(BaseModel):
    accepted: bool
    problems: list[str]
    warnings: list[str]
    fixed: ExtraIn | None
    session: SessionOut


class StartIn(BaseModel):
    description: str


class AnswerIn(BaseModel):
    option: int | None = Field(None, description="номер варианта с 1; 0 — не знаю")
    text: str | None = Field(
        None, description="ответ свободным текстом, разбирает Haiku"
    )


class PickIn(BaseModel):
    code: str


class GroupIn(BaseModel):
    automatic: bool = False
    code: str = Field(description="код из groups")


class ValuesIn(BaseModel):
    values: dict[str, list[str]] = Field(
        description="характеристика → варианты; [] — сбросить"
    )


class NumberIn(BaseModel):
    name: str
    value: float | None = Field(description="число в единице КТРУ; null — сбросить")


class TextIn(BaseModel):
    text: str
    name: str | None = Field(
        None, description="только эта характеристика; без него — все"
    )


def _question(q: Question) -> QuestionOut:
    return QuestionOut(
        name=q.name,
        required=q.required,
        multiple=q.multiple,
        options=list(q.options),
        counts=list(q.counts),
    )


def _band(label: str, v: Value) -> BandOut:
    return BandOut(
        option=label,
        min=v.min,
        min_inclusive=v.min_op != "greater",
        max=v.max,
        max_inclusive=v.max_op != "less",
    )


def _characteristic(
    s: Session, q: Question, entered: dict[str, float], doubts: dict[str, Doubt]
) -> CharacteristicOut:
    return CharacteristicOut(
        name=q.name,
        required=q.required,
        multiple=q.multiple,
        options=list(q.options),
        values=list(s.chosen.get(q.name, ())),
        origin=s.origins.get(q.name) if q.name in s.chosen else None,
        unit=q.ranges[0].unit if q.ranges else None,
        bands=[_band(label, v) for label, v in zip(q.options, q.ranges)],
        number=entered.get(q.name),
        warning=doubts.get(q.name),
    )


def view(s: Session) -> SessionOut:
    p = s.position
    entered = s.entered
    doubts = s.doubts
    comparison = display_differences(s.leaves)
    return SessionOut(
        messages=[ChatMessageOut(**m) for m in s.messages],
        id=s.id,
        stage=s.stage,
        description=s.description,
        corrected=s.corrected,
        fixes=[FixOut(before=f.before, after=f.after, kind=f.kind) for f in s.fixes],
        issues=s.issues,
        groups=[
            GroupOut(
                code=rk.hit.position.code,
                name=rk.hit.position.name,
                okpd2=rk.hit.position.okpd2,
                relevance=rk.relevance,
                reason=rk.reason,
            )
            for rk in s.ranked[:GROUPS]
        ],
        group=s.group.code,
        answers=s.answers,
        candidates=[
            CandidateOut(code=c.code, name=c.name, differences=comparison[c.code])
            for c in s.leaves
        ],
        question=_question(q) if (q := s.question) else None,
        position=PositionOut(
            code=p.code,
            name=p.name,
            okpd2=p.okpd2,
            okpd2_name=p.okpd2_name,
            fixed={
                c.name: "; ".join(value_text(v) for v in c.values)
                for c in p.characteristics
                if c.kind == FIXED
            },
        )
        if p
        else None,
        characteristics=[_characteristic(s, q, entered, doubts) for q in s.characteristics],
        extras=[ExtraIn(name=e.name, value=e.value, reason=e.reason) for e in s.extras],
        extras_allowed=s.extras_allowed,
        missing=s.missing,
        message=s.message,
        selection_reason=s.selection_reason,
    )


def _get(session_id: str) -> tuple[Session, asyncio.Lock]:
    s = sessions.get(session_id)
    if s is None:
        raise HTTPException(404, "нет такой сессии")
    return s, locks[session_id]


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    require_index(request)
    return {"status": "ok"}


def require_index(request: Request) -> Index:
    if request.app.state.index is None:
        raise HTTPException(
            503, "индекс КТРУ не настроен: задайте RAG_DATA и перезапустите сервис"
        )
    return request.app.state.index


@app.post("/sessions", status_code=201)
async def create(body: StartIn, request: Request) -> SessionOut:
    s = await ss.start(require_index(request), body.description)
    sessions[s.id] = s
    locks[s.id] = asyncio.Lock()
    return view(s)


@app.get("/sessions/{session_id}")
async def read(session_id: str) -> SessionOut:
    return view(_get(session_id)[0])


@app.delete("/sessions/{session_id}", status_code=204)
async def delete(session_id: str) -> None:
    _get(session_id)
    sessions.pop(session_id)
    locks.pop(session_id)
    for key in [k for k in suggestions if k[0] == session_id]:
        suggestions.pop(key).cancel()


@app.post("/sessions/{session_id}/answer")
async def answer(session_id: str, body: AnswerIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    if (body.option is None) == (body.text is None):
        raise InputError("нужно ровно одно из option и text")
    async with lock:
        if body.text is not None:
            await ss.reply(s, require_index(request), body.text)
        else:
            await ss.choose(s, require_index(request), body.option or None)
    return view(s)


@app.post("/sessions/{session_id}/pick")
async def pick(session_id: str, body: PickIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.pick(s, require_index(request), body.code)
    return view(s)


@app.post("/sessions/{session_id}/group")
async def switch_group(session_id: str, body: GroupIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.switch_group(s, require_index(request), body.code)
    return view(s)


@app.patch("/sessions/{session_id}/characteristics")
async def set_values(session_id: str, body: ValuesIn) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        ss.set_values(s, body.values)
    return view(s)


@app.put("/sessions/{session_id}/characteristics/number")
async def set_number(session_id: str, body: NumberIn) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        ss.set_number(s, body.name, body.value)
    return view(s)


@app.post("/sessions/{session_id}/characteristics/text")
async def describe(session_id: str, body: TextIn) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.describe(s, body.text, body.name)
    return view(s)


@app.post("/sessions/{session_id}/messages")
async def message(session_id: str, body: TextIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await conversation.respond(s, require_index(request), body.text)
    return view(s)


@app.post("/sessions/{session_id}/extras")
async def add_extra(session_id: str, body: ExtraIn) -> VerdictOut:
    s, lock = _get(session_id)
    async with lock:
        verdict = await ss.add_extra(s, Extra(body.name, body.value, body.reason))
    fixed = verdict.fixed
    return VerdictOut(
        accepted=verdict.ok,
        problems=verdict.problems,
        warnings=verdict.warnings,
        fixed=ExtraIn(name=fixed.name, value=fixed.value, reason=fixed.reason)
        if fixed
        else None,
        session=view(s),
    )


@app.post("/sessions/{session_id}/suggestions")
async def suggest(session_id: str) -> SuggestionsOut:
    s, lock = _get(session_id)
    async with lock:
        if s.position is None:
            raise StageError("позиция ещё не определена")
        key = (s.id, s.position.code)
        if key not in suggestions or suggestions[key].cancelled():
            suggestions[key] = asyncio.create_task(ss.suggest_extras(s))
        task = suggestions[key]
    try:
        items = await asyncio.shield(task)
    except Exception:
        suggestions.pop(key, None)
        raise
    return SuggestionsOut(
        code=key[1],
        items=[
            SuggestionOut(
                name=x.name,
                unit=x.unit,
                options=list(x.options),
                value=x.value,
                evidence=x.evidence,
                source=x.source,
                share=x.share,
                why=x.why,
            )
            for x in items
        ],
    )


@app.delete("/sessions/{session_id}/extras/{n}")
async def remove_extra(session_id: str, n: int) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        ss.remove_extra(s, n)
    return view(s)


@app.post("/sessions/{session_id}/finish")
async def finish(session_id: str) -> dict:
    s, lock = _get(session_id)
    async with lock:
        return ss.finish(s)


@app.post("/searches", status_code=201)
async def create_search(body: StartIn, request: Request) -> DiscoveryOut:
    require_index(request)
    return ds.view(await ds.create(body.description))


@app.post("/searches/{search_id}/candidates")
async def search_candidates(search_id: str, request: Request) -> DiscoveryOut:
    search = ds.get(search_id)
    async with search.lock:
        await ds.retrieve(search, require_index(request))
    return ds.view(search)


@app.post("/searches/{search_id}/rerank")
async def rank_candidates(search_id: str) -> DiscoveryOut:
    search = ds.get(search_id)
    async with search.lock:
        await ds.rank(search)
    return ds.view(search)


@app.post("/searches/{search_id}/select")
async def select_candidate(
    search_id: str, body: GroupIn, request: Request
) -> SessionOut:
    search = ds.get(search_id)
    async with search.lock:
        s = await ds.select(search, require_index(request), body.code, body.automatic)
        sessions[s.id] = s
        locks[s.id] = asyncio.Lock()
    return view(s)


def run() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("RAG_HOST", "127.0.0.1"),
        port=int(os.environ.get("RAG_PORT", "8100")),
    )
