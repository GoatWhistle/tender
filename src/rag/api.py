import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from rag import session as ss
from rag.clarify import FIXED, Question
from rag.ktru import value_text
from rag.search import Index
from rag.session import InputError, Session, Stage, StageError
from rag.spec import Extra

GROUPS = 5

sessions: dict[str, Session] = {}
locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.index = await asyncio.to_thread(Index)
    yield


app = FastAPI(title="RAG КТРУ", lifespan=lifespan)


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


class PositionOut(BaseModel):
    code: str
    name: str
    okpd2: str
    okpd2_name: str
    fixed: dict[str, str]


class CharacteristicOut(BaseModel):
    name: str
    required: bool
    multiple: bool
    options: list[str]
    values: list[str]


class ExtraIn(BaseModel):
    name: str
    value: str
    reason: str = ""


class SessionOut(BaseModel):
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


class VerdictOut(BaseModel):
    accepted: bool
    problems: list[str]
    fixed: ExtraIn | None
    session: SessionOut


class StartIn(BaseModel):
    description: str


class AnswerIn(BaseModel):
    option: int | None = Field(None, description="номер варианта с 1; 0 — не знаю")
    text: str | None = Field(None, description="ответ свободным текстом, разбирает Haiku")


class PickIn(BaseModel):
    code: str


class GroupIn(BaseModel):
    code: str = Field(description="код из groups")


class ValuesIn(BaseModel):
    values: dict[str, list[str]] = Field(description="характеристика → варианты; [] — сбросить")


class TextIn(BaseModel):
    text: str
    name: str | None = Field(None, description="только эта характеристика; без него — все")


def _question(q: Question) -> QuestionOut:
    return QuestionOut(
        name=q.name, required=q.required, multiple=q.multiple, options=list(q.options), counts=list(q.counts)
    )


def view(s: Session) -> SessionOut:
    p = s.position
    return SessionOut(
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
        candidates=[CandidateOut(code=c.code, name=c.name) for c in s.leaves],
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
        characteristics=[
            CharacteristicOut(
                name=q.name,
                required=q.required,
                multiple=q.multiple,
                options=list(q.options),
                values=list(s.chosen.get(q.name, ())),
            )
            for q in s.characteristics
        ],
        extras=[ExtraIn(name=e.name, value=e.value, reason=e.reason) for e in s.extras],
        extras_allowed=s.extras_allowed,
        missing=s.missing,
        message=s.message,
    )


def _get(session_id: str) -> tuple[Session, asyncio.Lock]:
    s = sessions.get(session_id)
    if s is None:
        raise HTTPException(404, "нет такой сессии")
    return s, locks[session_id]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions", status_code=201)
async def create(body: StartIn, request: Request) -> SessionOut:
    s = await ss.start(request.app.state.index, body.description)
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


@app.post("/sessions/{session_id}/answer")
async def answer(session_id: str, body: AnswerIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    if (body.option is None) == (body.text is None):
        raise InputError("нужно ровно одно из option и text")
    async with lock:
        if body.text is not None:
            await ss.reply(s, request.app.state.index, body.text)
        else:
            await ss.choose(s, request.app.state.index, body.option or None)
    return view(s)


@app.post("/sessions/{session_id}/pick")
async def pick(session_id: str, body: PickIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.pick(s, request.app.state.index, body.code)
    return view(s)


@app.post("/sessions/{session_id}/group")
async def switch_group(session_id: str, body: GroupIn, request: Request) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.switch_group(s, request.app.state.index, body.code)
    return view(s)


@app.patch("/sessions/{session_id}/characteristics")
async def set_values(session_id: str, body: ValuesIn) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        ss.set_values(s, body.values)
    return view(s)


@app.post("/sessions/{session_id}/characteristics/text")
async def describe(session_id: str, body: TextIn) -> SessionOut:
    s, lock = _get(session_id)
    async with lock:
        await ss.describe(s, body.text, body.name)
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
        fixed=ExtraIn(name=fixed.name, value=fixed.value, reason=fixed.reason) if fixed else None,
        session=view(s),
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


def run() -> None:
    uvicorn.run(
        app,
        host=os.environ.get("RAG_HOST", "127.0.0.1"),
        port=int(os.environ.get("RAG_PORT", "8100")),
    )
