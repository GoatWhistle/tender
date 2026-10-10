"""SQLite-хранилище снимков; блокировка записи предшествует чтению ревизии."""

import json
from dataclasses import asdict
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.domain.catalog import Bound, Value
from app.domain.diagnostics import Diagnostic, DiagnosticScope, RuleRef
from app.domain.dialog import CommonField, DialogTurn, Question, QuestionOption, RequiredField
from app.domain.enum_mapping import EnumProposal, EnumResolution, EnumSelection
from app.domain.facts import CheckResult, ExclusionReason, Fact, FactSource, RuleCheck, Verification
from app.domain.search import MethodContribution
from app.domain.sessions import (
    Alternative,
    AnalysisError,
    Candidate,
    CandidateCounts,
    FactEvent,
    GroupRef,
    Message,
    NarrowingPath,
    Revision,
    SessionState,
    SessionStatus,
    UnsupportedRule,
)
from app.repository.orm.sessions import AnalysisSession, SessionMessage, SessionRevision


def decode(data: dict[str, Any]) -> SessionState:
    path = data["path"]
    return SessionState(
        session_id=data["session_id"],
        revision=data["revision"],
        status=SessionStatus(data["status"]),
        messages=tuple(Message(**m) for m in data["messages"]),
        path=NarrowingPath(path["category"], GroupRef(**path["group"]), path["positions"])
        if path
        else None,
        alternatives=tuple(
            Alternative(
                a["code"],
                a["name"],
                a["category"],
                a["score"],
                {k: MethodContribution(**v) for k, v in a["methods"].items()},
            )
            for a in data["alternatives"]
        ),
        candidates=tuple(
            Candidate(
                c["code"],
                c["name"],
                c["excluded"],
                ExclusionReason(**c["reason"]) if c.get("reason") else None,
                tuple(c.get("matched_facts", [])),
                tuple(
                    RuleCheck(check["fact_id"], CheckResult(check["result"]))
                    for check in c.get("checks", [])
                ),
                c.get("returned_reason"),
            )
            for c in data["candidates"]
        ),
        facts=tuple(_fact(f) for f in data.get("facts", [])),
        fact_history=tuple(
            FactEvent(
                **{
                    **e,
                    "before": tuple(_fact(f) for f in e["before"]),
                    "after": tuple(_fact(f) for f in e["after"]),
                }
            )
            for e in data.get("fact_history", [])
        ),
        results_stale=data.get("results_stale", False),
        analysis_revision=data.get("analysis_revision"),
        editable_fields=tuple(data.get("editable_fields", [])),
        candidate_counts=CandidateCounts(**data["candidate_counts"]),
        errors=tuple(_diagnostic(e) if "kind" in e else AnalysisError(**e) for e in data["errors"]),
        normalizations=tuple(_diagnostic(e) for e in data.get("normalizations", [])),
        warnings=tuple(data["warnings"]),
        next_question=_question(data["next_question"]) if data.get("next_question") else None,
        dialog=tuple(
            DialogTurn(**{**t, "fact": _fact(t["fact"]) if t["fact"] else None})
            for t in data.get("dialog", [])
        ),
        enum_proposals=tuple(
            EnumProposal(
                **{
                    **p,
                    "suggested": tuple(p["suggested"]),
                    "options": tuple(p["options"]),
                    "selections": tuple(
                        EnumSelection(tuple(s["values"]), s["multiple"]) for s in p["selections"]
                    ),
                }
            )
            for p in data.get("enum_proposals", [])
        ),
        enum_resolutions=tuple(
            EnumResolution(**{**r, "facts": tuple(_fact(f) for f in r["facts"])})
            for r in data.get("enum_resolutions", [])
        ),
        card_complete=data.get("card_complete", False),
        missing_required=tuple(RequiredField(**m) for m in data.get("missing_required", [])),
        common_fields=tuple(
            CommonField(c["characteristic"], tuple(c["values"]))
            for c in data.get("common_fields", [])
        ),
        unanswered=tuple(data.get("unanswered", [])),
        unsupported_rules=tuple(UnsupportedRule(**u) for u in data.get("unsupported_rules", [])),
    )


class SqlSessions:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest(self, session_id: str, *, lock: bool = False) -> SessionState | None:
        if lock:
            self._session.execute(
                update(AnalysisSession)
                .where(AnalysisSession.id == session_id)
                .values(id=session_id)
            )
        row = self._session.scalar(
            select(SessionRevision)
            .where(SessionRevision.session_id == session_id)
            .order_by(SessionRevision.revision.desc())
            .limit(1)
        )
        return decode(row.snapshot) if row else None

    def replay(self, session_id: str, key: str) -> Revision | None:
        row = self._session.scalar(
            select(SessionRevision).where(
                SessionRevision.session_id == session_id, SessionRevision.idempotency_key == key
            )
        )
        return (
            Revision(decode(row.snapshot), row.idempotency_key, row.request_text) if row else None
        )

    def save(self, revision: Revision) -> None:
        state = revision.state
        if state.revision == 0:
            self._session.add(AnalysisSession(id=state.session_id))
            self._session.flush()
        elif revision.request_text is not None:
            # ревизия ответа на вопрос нового сообщения не несёт
            message = state.messages[-1]
            self._session.add(
                SessionMessage(
                    id=message.id,
                    session_id=state.session_id,
                    revision=state.revision,
                    text=message.text,
                    created_at=message.created_at,
                )
            )
        self._session.add(
            SessionRevision(
                session_id=state.session_id,
                revision=state.revision,
                snapshot=json.loads(json.dumps(asdict(state), default=_decimal_json)),
                idempotency_key=revision.idempotency_key,
                request_text=revision.request_text,
            )
        )


def _decimal_json(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Неподдержанный тип снимка: {type(value).__name__}")


def _fact(data: dict[str, Any]) -> Fact:
    value = data["value"]
    if data["kind"] == "number":
        value = Decimal(value)
    elif data["kind"] == "range":
        value = (Decimal(value[0]), Decimal(value[1]))
    source = data["source"]
    bounds = data.get("bounds")
    return Fact(
        **{
            **data,
            "value": value,
            "source": FactSource(**source) if source else None,
            "bounds": _value(bounds) if bounds else None,
            "verification": Verification(
                **{
                    **data["verification"],
                    "message_ids": tuple(data["verification"]["message_ids"]),
                }
            )
            if data.get("verification")
            else None,
        }
    )


def _value(data: dict[str, Any]) -> Value:
    def number(key: str) -> Decimal | None:
        return Decimal(data[key]) if data[key] is not None else None

    def bound(key: str) -> Bound | None:
        return Bound(data[key]) if data[key] is not None else None

    return Value(
        data["code"],
        data["text"],
        data["unit"],
        data["unit_code"],
        number("concrete"),
        number("min"),
        bound("min_op"),
        number("max"),
        bound("max_op"),
    )


def _question(data: dict[str, Any]) -> Question:
    return Question(**{**data, "options": tuple(QuestionOption(**o) for o in data["options"])})


def _diagnostic(data: dict[str, Any]) -> Diagnostic:
    return Diagnostic(
        **{
            **data,
            "source": FactSource(**data["source"]),
            "scope": DiagnosticScope(
                **{**data["scope"], "position_codes": tuple(data["scope"]["position_codes"])}
            ),
            "rule_ref": tuple(
                RuleRef(**{**r, "value_codes": tuple(r["value_codes"])}) for r in data["rule_ref"]
            ),
            "expected": tuple(data["expected"]),
            "candidates": tuple(data["candidates"]),
        }
    )
