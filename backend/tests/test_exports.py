from fastapi.testclient import TestClient

from settings import Settings


def test_complete_card_exports_saved_revision(facts_api: TestClient) -> None:
    client = facts_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    state = client.post(url + "/messages", json={"text": "Стол ширина 100 см ЛДСП"}).json()
    assert state["card_complete"]
    response = client.post(url + "/export")
    assert response.status_code == 200
    card = response.json()
    assert card["format"] == "ste_demo_v1"
    assert card["document_kind"] == "card"
    assert card["session_id"] == sid
    assert card["revision"] == state["revision"]
    assert card["ktru_code"] == "table-large"
    assert card["group"]["code"] == "tables"
    assert card["card_complete"] is True
    assert card["missing_required"] == []
    width = next(c for c in card["characteristics"] if c["fact"]["characteristic_name"] == "Ширина")
    assert width["catalog_refs"] == [
        {"position_code": "table-large", "characteristic_code": "width", "name": "Ширина"}
    ]
    fact = width["fact"]
    assert fact["raw_value"] == "100"
    assert fact["raw_unit"] == "см"
    assert fact["value"] == "100"
    assert fact["unit_code"] == "004"
    assert fact["origin"] == "parser"
    assert fact["status"] == "accepted_from_text"
    assert fact["source"]["message_id"] == state["messages"][0]["id"]
    assert client.get(url).json() == state


def test_incomplete_and_unresolved_documents_are_drafts(facts_api: TestClient) -> None:
    client = facts_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    empty = client.post(url + "/export").json()
    assert empty["document_kind"] == "draft"
    assert empty["ktru_code"] is None
    assert empty["characteristics"] == []
    state = client.post(url + "/messages", json={"text": "Стол ширина 1200 мм"}).json()
    # Единственное значение материала заполнено из справочника; его удаление оставляет пробел.
    material = next(f for f in state["facts"] if f["origin"] == "catalog")
    card = client.post(url + "/export").json()
    assert any(c["fact"]["status"] == "derived_from_catalog" for c in card["characteristics"])
    state = client.patch(
        url + "/facts/" + material["id"],
        json={"action": "delete", "expected_revision": state["revision"]},
    ).json()
    assert state["status"] == "resolved"
    assert state["missing_required"]
    draft = client.post(url + "/export").json()
    assert draft["document_kind"] == "draft"
    assert draft["ktru_code"] == "table-large"
    assert draft["card_complete"] is False
    assert draft["missing_required"] == [
        {"characteristic": "material", "name": "Вид материала столешницы"}
    ]
    assert material["id"] not in [c["fact"]["id"] for c in draft["characteristics"]]
    assert client.post(url + "/export", json={"expected_revision": 0}).status_code == 409
    assert client.get(url).json() == state


def test_decimal_and_range_export(facts_api: TestClient) -> None:
    client = facts_api
    sid = client.post("/api/v1/sessions").json()["session_id"]
    url = f"/api/v1/sessions/{sid}"
    state = client.post(
        url + "/messages",
        json={"text": "Стол ширина 100,000000000000000001–120,000000000000000002 см"},
    ).json()
    card = client.post(url + "/export").json()
    fact = card["characteristics"][0]["fact"]
    assert fact["kind"] == "range"
    assert fact["value"] == ["100.000000000000000001", "120.000000000000000002"]
    assert fact["unit_code"] == "004"
    assert card["ktru_code"] is None
    assert len(card["characteristics"][0]["catalog_refs"]) == 2
    assert client.get(url).json() == state


def test_export_filters_saved_facts_and_preserves_provenance_and_bounds(
    client: TestClient, settings: "Settings"
) -> None:
    # Сохранённая ревизия моделирует все поддерживаемые статусы извлечения; проверяем HTTP,
    # а не повторяем здесь тесты принятия фактов анализатором.
    from dataclasses import replace
    from decimal import Decimal

    from sqlalchemy.orm import Session

    from app.domain.catalog import Bound, Value
    from app.domain.facts import Fact, FactSource, FactStatus, Verification
    from app.domain.sessions import (
        Candidate,
        CatalogRef,
        GroupRef,
        NarrowingPath,
        Revision,
        SessionState,
        SessionStatus,
    )
    from app.repository.database import create_db_engine
    from app.repository.sessions import SqlSessions
    from app.repository.unit_of_work import SqlUnitOfWork

    statuses: tuple[FactStatus, ...] = (
        "accepted_from_text",
        "accepted_from_model",
        "confirmed_by_user",
        "derived_from_catalog",
        "proposed",
        "ambiguous",
        "deleted",
        "superseded",
    )
    source = FactSource("m1", "дерево", 0, 6)
    verification = Verification(
        "Материал — дерево",
        ("m1",),
        "hash",
        1,
        "extractor-v1",
        "verifier-v1",
        "supported",
        {"supported": 0.99},
        True,
    )
    facts = tuple(
        Fact(
            status,
            None,
            "Материал",
            "дерево",
            None,
            "дерево",
            None,
            "text",
            source if status in ("accepted_from_text", "accepted_from_model") else None,
            "identity",
            origin=(
                "decision"
                if status == "accepted_from_model"
                else "catalog"
                if status == "derived_from_catalog"
                else "parser"
                if status == "accepted_from_text"
                else "user"
            ),
            status=status,
            verification=verification if status == "accepted_from_model" else None,
        )
        for status in statuses
    )
    bounds = Value(
        "range-original",
        min=Decimal("0.000000000000000001"),
        min_op=Bound.greater,
        max=Decimal("10.000000000000000001"),
        max_op=Bound.less_or_equal,
        unit="мм",
        unit_code="003",
    )
    interval = Fact(
        "interval",
        None,
        "Размер",
        "интервал",
        "мм",
        "интервал",
        "003",
        "interval",
        None,
        "catalog_value",
        origin="catalog",
        status="derived_from_catalog",
        bounds=bounds,
    )
    unbound = replace(facts[0], id="unbound", characteristic_name=None)
    unknown = replace(facts[0], id="unknown", characteristic_name="Нет в снимке")
    state = SessionState(
        "saved",
        status=SessionStatus.RESOLVED,
        path=NarrowingPath("Мебель", GroupRef("group", "Группа"), 1),
        candidates=(Candidate("leaf", "Позиция"),),
        card_complete=True,
        catalog_refs=(
            CatalogRef("leaf", "original-material-id", "Материал"),
            CatalogRef("leaf", "original-size-id", "Размер"),
        ),
        facts=(*facts, interval, unbound, unknown),
    )
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as sql, SqlUnitOfWork(sql):
            SqlSessions(sql).save(Revision(state))
    finally:
        engine.dispose()
    url = "/api/v1/sessions/saved"
    before = client.get(url).json()
    exported = client.post(url + "/export").json()
    values = {c["fact"]["id"]: c for c in exported["characteristics"]}
    assert set(values) == {
        "accepted_from_text",
        "accepted_from_model",
        "confirmed_by_user",
        "derived_from_catalog",
        "interval",
        "unknown",
    }
    assert (
        values["accepted_from_model"]["fact"]["verification"]["extractor_revision"]
        == "extractor-v1"
    )
    assert values["confirmed_by_user"]["fact"]["source"] is None
    assert values["accepted_from_text"]["fact"]["unit_code"] is None
    assert (
        values["accepted_from_text"]["catalog_refs"][0]["characteristic_code"]
        == "original-material-id"
    )
    assert values["unknown"]["catalog_refs"] == []
    assert values["interval"]["fact"]["bounds"] == {
        "code": "range-original",
        "text": None,
        "unit": "мм",
        "unit_code": "003",
        "concrete": None,
        "min": "1E-18",
        "min_op": "greater",
        "max": "10.000000000000000001",
        "max_op": "lessOrEqual",
    }
    assert exported["catalog_version"] is None
    assert exported["catalog_snapshot"] is None
    assert client.get(url).json() == before
    # После сбоя прежние кандидаты могут остаться в снимке: код не выдаётся за актуальный.
    engine = create_db_engine(settings.database_url)
    try:
        with Session(engine) as sql, SqlUnitOfWork(sql):
            SqlSessions(sql).save(
                Revision(
                    replace(
                        state, revision=1, results_stale=True, status=SessionStatus.TECHNICAL_ERROR
                    )
                )
            )
    finally:
        engine.dispose()
    stale = client.post(url + "/export").json()
    assert stale["document_kind"] == "draft"
    assert stale["ktru_code"] is None
    assert stale["card_complete"] is False
    assert stale["revision"] == 1
