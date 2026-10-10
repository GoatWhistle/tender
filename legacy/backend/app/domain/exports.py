"""Демонстрационный документ СТЕ из одного сохранённого снимка сессии."""

from dataclasses import dataclass
from typing import Literal

from app.domain.dialog import RequiredField
from app.domain.facts import Fact
from app.domain.sessions import CatalogRef, GroupRef, SessionState, SessionStatus


@dataclass(frozen=True)
class ExportCharacteristic:
    fact: Fact
    catalog_refs: tuple[CatalogRef, ...]


@dataclass(frozen=True)
class CardExport:
    session_id: str
    revision: int
    document_kind: Literal["card", "draft"]
    ktru_code: str | None
    group: GroupRef | None
    card_complete: bool
    missing_required: tuple[RequiredField, ...]
    results_stale: bool
    characteristics: tuple[ExportCharacteristic, ...]
    format: str = "ste_demo_v1"
    catalog_version: str | None = None
    catalog_snapshot: str | None = None


def export_card(state: SessionState) -> CardExport:
    remaining = [c for c in state.candidates if not c.excluded]
    code = (
        remaining[0].code
        if state.status == SessionStatus.RESOLVED
        and not state.results_stale
        and len(remaining) == 1
        else None
    )
    complete = bool(code and state.card_complete and not state.missing_required)
    return CardExport(
        session_id=state.session_id,
        revision=state.revision,
        document_kind="card" if complete else "draft",
        ktru_code=code,
        group=state.path.group if state.path else None,
        card_complete=complete,
        missing_required=state.missing_required,
        results_stale=state.results_stale,
        characteristics=tuple(
            ExportCharacteristic(
                fact,
                tuple(
                    ref
                    for ref in state.catalog_refs
                    if ref.name == fact.characteristic_name
                    and (
                        ref.position_code == code
                        if code
                        else any(c.code == ref.position_code for c in remaining)
                    )
                ),
            )
            for fact in state.facts
            if fact.accepted
        ),
    )
