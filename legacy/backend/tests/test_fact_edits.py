"""Правки фактов через публичный HTTP-контракт."""

from typing import Any

from fastapi.testclient import TestClient

from tests.group_decision import ConfirmedGroup
from tests.test_answers import start


def test_edit_returns_position_and_keeps_history(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1300 мм")
    old = next(f for f in state["facts"] if f["origin"] == "parser")
    url = f"/api/v1/sessions/{sid}"
    body: dict[str, Any] = {
        "expected_revision": state["revision"],
        "action": "edit",
        "characteristic_name": "Ширина",
        "raw_value": "1000",
        "raw_unit": "мм",
        "kind": "number",
    }
    response = facts_api.patch(f"{url}/facts/{old['id']}", json=body)
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["candidate_counts"]["compatible"] == 2
    assert next(c for c in edited["candidates"] if c["code"] == "table-small")["returned_reason"]
    previous = next(f for f in edited["facts"] if f["id"] == old["id"])
    assert previous["status"] == "superseded" and previous["superseded_by"]
    assert edited["fact_history"][-1]["action"] == "edit"
    assert facts_api.get(url).json() == edited
    assert facts_api.patch(f"{url}/facts/{old['id']}", json=body).status_code == 409
    assert facts_api.get(url).json() == edited
    repeated = facts_api.post(
        f"{url}/recalculate", json={"expected_revision": edited["revision"]}
    ).json()
    assert repeated["candidate_counts"]["compatible"] == 2


def test_delete_restore_and_new_assertion(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1300 мм")
    url = f"/api/v1/sessions/{sid}"
    old = next(f for f in state["facts"] if f["origin"] == "parser")
    deleted = facts_api.patch(
        f"{url}/facts/{old['id']}",
        json={"expected_revision": state["revision"], "action": "delete"},
    ).json()
    assert deleted["candidate_counts"]["compatible"] == 2
    repeated = facts_api.post(
        f"{url}/recalculate", json={"expected_revision": deleted["revision"]}
    ).json()
    assert repeated["candidate_counts"]["compatible"] == 2
    new = facts_api.post(f"{url}/messages", json={"text": "ширина 1300 мм"}).json()
    assert new["candidate_counts"]["compatible"] == 1
    restored = facts_api.patch(
        f"{url}/facts/{old['id']}", json={"expected_revision": new["revision"], "action": "restore"}
    ).json()
    assert restored["fact_history"][-1]["action"] == "restore"
    assert restored["candidate_counts"]["compatible"] == 1
    assert facts_api.get(url).json() == restored


def test_explicit_text_correction_has_history(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1300 мм")
    state = facts_api.post(
        f"/api/v1/sessions/{sid}/messages", json={"text": "исправь ширину на 100 см"}
    ).json()
    assert state["candidate_counts"]["compatible"] == 2
    assert state["fact_history"][-1]["action"] == "text_correction"
    assert any(f["status"] == "superseded" for f in state["facts"])


def test_deleted_catalog_value_stays_missing(facts_api: TestClient) -> None:
    from tests.test_answers import choose

    sid, state = start(facts_api, "стол")
    state = choose(facts_api, sid, state, "ЛДСП")
    derived = next(f for f in state["facts"] if f["origin"] == "catalog")
    url = f"/api/v1/sessions/{sid}"
    deleted = facts_api.patch(
        f"{url}/facts/{derived['id']}",
        json={"expected_revision": state["revision"], "action": "delete"},
    ).json()
    assert deleted["card_complete"] is False
    assert deleted["missing_required"] == [{"characteristic": "width", "name": "Ширина"}]
    assert deleted["next_question"]["characteristic"] == "Ширина"
    repeated = facts_api.post(
        f"{url}/recalculate", json={"expected_revision": deleted["revision"]}
    ).json()
    assert repeated["missing_required"] == deleted["missing_required"]


def test_manual_unknown_enum_has_diagnostic(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "столешница лдсп")
    fact = next(f for f in state["facts"] if f["origin"] == "parser")
    changed = facts_api.patch(
        f"/api/v1/sessions/{sid}/facts/{fact['id']}",
        json={
            "expected_revision": state["revision"],
            "action": "edit",
            "characteristic_name": fact["characteristic_name"],
            "raw_value": "алюминий",
        },
    ).json()
    assert any(e.get("kind") == "value_not_in_catalog" for e in changed["errors"])
    assert any(
        f["raw_value"] == "алюминий" and f["status"] == "confirmed_by_user"
        for f in changed["facts"]
    )


def test_accept_unit_suggestion_and_stale_proposal(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1000 см")
    diagnostic = next(e for e in state["errors"] if e.get("kind") == "out_of_range")
    assert diagnostic["suggestion"] == "1000 мм"
    old = next(f for f in state["facts"] if f["id"] == diagnostic["fact_id"])
    assert old["unit_code"] == "004"
    body = {
        "expected_revision": state["revision"],
        "action": "accept_suggestion",
        "diagnostic_index": 0,
        "characteristic_name": "Ширина",
        "raw_value": "1000",
        "raw_unit": "мм",
        "kind": "number",
    }
    url = f"/api/v1/sessions/{sid}/facts/{old['id']}"
    accepted = facts_api.patch(url, json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["candidate_counts"]["compatible"] == 2
    assert accepted.json()["fact_history"][-1]["action"] == "accept_suggestion"
    assert facts_api.patch(url, json=body).status_code == 409


def test_conflict_resolution_split_and_delete(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1000 мм", "ширина 1300 мм")
    assert state["status"] == "conflict"
    assert state["candidate_counts"]["compatible"] == 2
    facts = [f for f in state["facts"] if f["status"] == "ambiguous"]
    body = {
        "expected_revision": state["revision"],
        "action": "split",
        "related_ids": [facts[1]["id"]],
        "bindings": [
            {
                "characteristic_name": "Ширина",
                "raw_value": f["raw_value"],
                "raw_unit": "мм",
                "kind": "number",
                "component": component,
            }
            for f, component in zip(facts, ["столешница", "основание"], strict=True)
        ],
    }
    url = f"/api/v1/sessions/{sid}"
    split = facts_api.patch(f"{url}/facts/{facts[0]['id']}", json=body)
    assert split.status_code == 200, split.text
    current = [f for f in split.json()["facts"] if f["status"] == "confirmed_by_user"]
    assert len(current) == 2
    assert {f["component"] for f in current} == {"столешница", "основание"}
    assert (
        split.json()["next_question"] is None or split.json()["next_question"]["kind"] != "conflict"
    )
    deleted = facts_api.patch(
        f"{url}/facts/{current[0]['id']}",
        json={
            "expected_revision": split.json()["revision"],
            "action": "delete",
            "related_ids": [current[1]["id"]],
        },
    ).json()
    assert deleted["candidate_counts"]["compatible"] == 2
    assert facts_api.patch(f"{url}/facts/{facts[0]['id']}", json=body).status_code == 409


def test_equivalent_units_do_not_conflict(facts_api: TestClient) -> None:
    _, state = start(facts_api, "ширина 1000 мм", "ширина 100 см")
    assert state["status"] != "conflict"
    assert not any(f["status"] == "ambiguous" for f in state["facts"])


def test_unbound_suggestion_requires_binding(group_api: Any, table_group: Any) -> None:
    from app.domain.diagnostics import SpellingSuggestion
    from app.domain.facts import FactSource
    from app.domain.sessions import Message

    class Spelling:
        def suggest(self, message: Message) -> tuple[SpellingSuggestion, ...]:
            return (SpellingSuggestion(FactSource(message.id, "лдпс", 12, 16), "лдсп"),)

    client = group_api(table_group, spelling=Spelling())
    sid, state = start(client, "столешница: лдпс")
    diagnostic = next(e for e in state["errors"] if e.get("kind") == "typo")
    assert diagnostic["fact_id"] is None
    url = f"/api/v1/sessions/{sid}"
    body = {
        "expected_revision": state["revision"],
        "action": "accept_suggestion",
        "diagnostic_index": 0,
    }
    assert client.post(f"{url}/facts", json=body).status_code == 422
    body.update(
        {
            "characteristic_name": "Вид материала столешницы",
            "raw_value": "лдсп",
            "component": "столешница",
        }
    )
    accepted = client.post(f"{url}/facts", json=body)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["candidate_counts"]["compatible"] == 1
    assert accepted.json()["fact_history"][-1]["action"] == "accept_suggestion"
    assert client.get(url).json() == accepted.json()
    assert client.post(f"{url}/facts", json=body).status_code == 409


def test_edit_survives_analysis_failure_and_retry(group_api: Any, table_group: Any) -> None:
    from collections.abc import Sequence

    from app.adapter.facts import DeterministicFactExtractor
    from app.domain.catalog import Group
    from app.domain.errors import ModelFailure
    from app.domain.facts import Fact
    from app.domain.sessions import Message

    class Extractor:
        failing = False

        def extract(
            self, messages: Sequence[Message], group: Group
        ) -> tuple[tuple[Fact, ...], tuple[str, ...]]:
            if self.failing:
                raise ModelFailure()
            return DeterministicFactExtractor().extract(messages, group)

    extractor = Extractor()
    client = group_api(table_group, fact_extractor=extractor)
    sid, state = start(client, "ширина 1300 мм")
    old = next(f for f in state["facts"] if f["origin"] == "parser")
    url = f"/api/v1/sessions/{sid}"
    extractor.failing = True
    response = client.patch(
        f"{url}/facts/{old['id']}",
        json={
            "expected_revision": state["revision"],
            "action": "edit",
            "characteristic_name": "Ширина",
            "raw_value": "1000",
            "raw_unit": "мм",
            "kind": "number",
        },
    )
    assert response.status_code == 200
    failed = response.json()
    assert failed["status"] == "technical_error" and failed["results_stale"]
    assert failed["card_complete"] is False
    assert failed["analysis_revision"] < failed["revision"]
    assert failed["fact_history"][-1]["after"][0]["raw_value"] == "1000"
    assert client.get(url).json() == failed
    extractor.failing = False
    retried = client.post(
        f"{url}/recalculate", json={"expected_revision": failed["revision"]}
    ).json()
    assert retried["results_stale"] is False
    assert retried["analysis_revision"] == retried["revision"]
    assert retried["candidate_counts"]["compatible"] == 2
    assert retried["fact_history"] == failed["fact_history"]


def test_components_and_multiple_values_do_not_conflict(group_api: Any, table_group: Any) -> None:
    from dataclasses import replace

    from app.domain.catalog import CharacteristicKind, Value

    leaf = table_group.leaves[0]
    material = replace(
        leaf.characteristics[1],
        name="Материал",
        values=(Value("wood", text="деревянный"), Value("metal", text="металлический")),
    )
    group = replace(table_group, leaves=(replace(leaf, characteristics=(material,)),))
    client = group_api(group)
    _, state = start(client, "металлический каркас, деревянный столешница")
    assert state["status"] != "conflict"
    assert not any(f["status"] == "ambiguous" for f in state["facts"])
    multiple = replace(material, kind=CharacteristicKind.multiple)
    client = group_api(replace(group, leaves=(replace(leaf, characteristics=(multiple,)),)))
    _, state = start(client, "деревянный и металлический")
    assert state["status"] != "conflict"


def test_restore_follows_rebound_chain(group_api: Any, table_group: Any) -> None:
    from dataclasses import replace

    group = replace(
        table_group,
        leaves=tuple(
            replace(
                p,
                characteristics=(
                    *p.characteristics,
                    replace(p.characteristics[0], code="height", name="Высота"),
                ),
            )
            for p in table_group.leaves
        ),
    )
    client = group_api(group)
    sid, state = start(client, "ширина 1300 мм")
    old = next(f for f in state["facts"] if f["origin"] == "parser")
    url = f"/api/v1/sessions/{sid}"
    changed = client.patch(
        f"{url}/facts/{old['id']}",
        json={
            "expected_revision": state["revision"],
            "action": "edit",
            "characteristic_name": "Высота",
            "component": "основание",
            "raw_value": "1000",
            "raw_unit": "мм",
            "kind": "number",
        },
    ).json()
    restored = client.patch(
        f"{url}/facts/{old['id']}",
        json={"expected_revision": changed["revision"], "action": "restore"},
    ).json()
    assert restored["fact_history"][-1]["restored_from"] == old["id"]
    user = [
        f for f in restored["facts"] if f["origin"] == "user" and f["status"] == "confirmed_by_user"
    ]
    assert (
        len(user) == 1
        and user[0]["characteristic_name"] == "Ширина"
        and user[0]["raw_value"] == "1300"
    )


def test_ambiguous_text_correction_requires_component(group_api: Any, table_group: Any) -> None:
    from dataclasses import replace

    from app.domain.catalog import Value

    leaf = table_group.leaves[0]
    material = replace(
        leaf.characteristics[1],
        name="Материал",
        values=(Value("wood", text="деревянный"), Value("metal", text="металлический")),
    )
    client = group_api(replace(table_group, leaves=(replace(leaf, characteristics=(material,)),)))
    sid, state = start(client, "деревянный каркас, металлический основание")
    state = client.post(
        f"/api/v1/sessions/{sid}/messages", json={"text": "исправь материал на деревянный"}
    ).json()
    assert state["status"] == "conflict"
    assert state["next_question"] is not None
    assert any(f["status"] == "ambiguous" for f in state["facts"])


def test_all_stale_mutations_leave_snapshot_unchanged(facts_api: TestClient) -> None:
    sid, state = start(facts_api, "ширина 1300 мм")
    url = f"/api/v1/sessions/{sid}"
    fact = next(f for f in state["facts"] if f["origin"] == "parser")
    for action in ("edit", "confirm", "delete", "restore", "split", "accept_suggestion"):
        response = facts_api.patch(
            f"{url}/facts/{fact['id']}", json={"expected_revision": 0, "action": action}
        )
        assert response.status_code == 409 and response.json()["code"] == "stale_revision"
        assert facts_api.get(url).json() == state


def test_explicit_negation_replaces_single_fact(group_api: Any, table_group: Any) -> None:
    from dataclasses import replace

    from app.domain.catalog import Value

    leaf = table_group.leaves[0]
    material = replace(
        leaf.characteristics[1],
        name="Материал",
        values=(Value("wood", text="деревянный"), Value("metal", text="металлический")),
    )
    client = group_api(replace(table_group, leaves=(replace(leaf, characteristics=(material,)),)))
    sid, state = start(client, "деревянный")
    state = client.post(
        f"/api/v1/sessions/{sid}/messages", json={"text": "нет, не деревянный, металлический"}
    ).json()
    assert state["status"] == "resolved"
    assert state["fact_history"][-1]["action"] == "text_correction"
    assert [f["value"] for f in state["facts"] if f["status"] == "confirmed_by_user"] == [
        "металлический"
    ]


def test_catalog_interval_can_change_binding_without_losing_bounds(facts_api: TestClient) -> None:
    from tests.test_answers import choose

    sid, state = start(facts_api, "стол")
    state = choose(facts_api, sid, state, "ЛДСП")
    fact = next(f for f in state["facts"] if f["kind"] == "interval")
    body = {
        "action": "edit",
        "expected_revision": state["revision"],
        "characteristic_name": fact["characteristic_name"],
        "raw_value": fact["raw_value"],
        "raw_unit": fact["raw_unit"],
        "kind": "interval",
        "component": "столешница",
    }
    response = facts_api.patch(f"/api/v1/sessions/{sid}/facts/{fact['id']}", json=body)
    assert response.status_code == 200, response.text
    edited = response.json()["fact_history"][-1]["after"][0]
    assert edited["bounds"] == fact["bounds"] and edited["component"] == "столешница"


def test_product_type_change_searches_new_group_without_reviving_deleted_fact(
    settings: Any, table_group: Any
) -> None:
    from dataclasses import replace

    from app.adapter.facts import DeterministicFactExtractor
    from app.domain.catalog import Group, Position
    from app.domain.search import MethodContribution, SearchHit, SearchResult
    from composition import build_usecases
    from main import create_app, sql_repositories, sync_catalog

    chairs = Group(
        replace(table_group.position, code="chairs", name="Стул"),
        tuple(
            replace(p, code=p.code.replace("table", "chair"), parent="chairs", name="Стул")
            for p in table_group.leaves
        ),
    )

    class Source:
        def load(self) -> list[Position]:
            return [table_group.position, *table_group.leaves, chairs.position, *chairs.leaves]

    class Search:
        def run(
            self, description: str, category: str | None = None, limit: int = 10
        ) -> SearchResult:
            selected = chairs if "стул" in description else table_group
            return SearchResult(
                description,
                (
                    SearchHit(
                        selected.position,
                        MethodContribution.of(1),
                        MethodContribution.of(None),
                        MethodContribution.of(None),
                    ),
                ),
            )

    source = Source()
    sync_catalog(settings, source)
    app = create_app(settings, source)
    app.state.usecases = build_usecases(
        sql_repositories(),
        catalog_source=source,
        searcher=Search(),
        group_decision=ConfirmedGroup(lambda text: "chairs" if "стул" in text else "tables"),
        fact_extractor=DeterministicFactExtractor(),
    )
    with TestClient(app) as client:
        sid, state = start(client, "стол ширина 1300 мм")
        old = next(f for f in state["facts"] if f["origin"] == "parser")
        url = f"/api/v1/sessions/{sid}"
        client.patch(
            f"{url}/facts/{old['id']}",
            json={"expected_revision": state["revision"], "action": "delete"},
        ).raise_for_status()
        changed = client.post(f"{url}/messages", json={"text": "теперь стул"}).json()
        assert changed["path"]["group"]["code"] == "chairs"
        assert changed["candidate_counts"]["compatible"] == 2
        assert all(c["returned_reason"] is None for c in changed["candidates"])
        assert next(f for f in changed["facts"] if f["id"] == old["id"])["status"] == "deleted"
