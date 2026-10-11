from fastapi import APIRouter

from rag.controller.http.deps import SessionsDep
from rag.controller.http.schemas import (
    AnswerIn,
    ExtraIn,
    GroupIn,
    NumberIn,
    OutcomeOut,
    PickIn,
    SessionOut,
    StartIn,
    SuggestionOut,
    SuggestionsOut,
    TextIn,
    ValuesIn,
    VerdictOut,
)

router = APIRouter(prefix="/sessions", tags=["Сессии"])


@router.post("", status_code=201)
async def create(body: StartIn, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.start(body.description))


@router.get("/{session_id}")
async def read(session_id: str, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(sessions.read(session_id))


@router.delete("/{session_id}", status_code=204)
async def delete(session_id: str, sessions: SessionsDep) -> None:
    sessions.delete(session_id)


@router.post("/{session_id}/answer")
async def answer(session_id: str, body: AnswerIn, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.answer(session_id, body.option, body.text))


@router.post("/{session_id}/pick")
async def pick(session_id: str, body: PickIn, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.pick(session_id, body.code))


@router.post("/{session_id}/group")
async def switch_group(
    session_id: str, body: GroupIn, sessions: SessionsDep
) -> SessionOut:
    return SessionOut.of(await sessions.switch_group(session_id, body.code))


@router.patch("/{session_id}/characteristics")
async def set_values(
    session_id: str, body: ValuesIn, sessions: SessionsDep
) -> SessionOut:
    return SessionOut.of(await sessions.set_values(session_id, body.values))


@router.put("/{session_id}/characteristics/number")
async def set_number(
    session_id: str, body: NumberIn, sessions: SessionsDep
) -> SessionOut:
    return SessionOut.of(await sessions.set_number(session_id, body.name, body.value))


@router.post("/{session_id}/characteristics/text")
async def describe(session_id: str, body: TextIn, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.describe(session_id, body.text, body.name))


@router.post("/{session_id}/messages")
async def message(session_id: str, body: TextIn, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.message(session_id, body.text))


@router.post("/{session_id}/extras")
async def add_extra(
    session_id: str, body: ExtraIn, sessions: SessionsDep
) -> VerdictOut:
    verdict, s = await sessions.add_extra(session_id, body.to_domain())
    return VerdictOut.of(verdict, s)


@router.delete("/{session_id}/extras/{n}")
async def remove_extra(session_id: str, n: int, sessions: SessionsDep) -> SessionOut:
    return SessionOut.of(await sessions.remove_extra(session_id, n))


@router.post("/{session_id}/suggestions")
async def suggest(session_id: str, sessions: SessionsDep) -> SuggestionsOut:
    code, items = await sessions.suggestions(session_id)
    return SuggestionsOut(code=code, items=[SuggestionOut.of(x) for x in items])


@router.post("/{session_id}/finish")
async def finish(session_id: str, sessions: SessionsDep) -> OutcomeOut:
    return OutcomeOut.of(await sessions.finish(session_id))
