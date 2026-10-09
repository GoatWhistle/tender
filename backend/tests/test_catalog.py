from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapter.ktru_json import JsonKtruSource, dump_json
from app.adapter.ktru_xml import XmlKtruSource
from app.domain.catalog import Bound, CharacteristicKind, Value
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from main import sync_catalog
from settings import Settings
from tests.conftest import (
    AXE_CODE,
    CABINET_CHILDREN,
    CABINET_CODE,
    HAMMER_CODE,
    ROBE_CODE,
    TABLE_CODE,
    memory_usecases,
)


def test_xml_keeps_actual_characteristics_and_bounds(ktru_dir: Path) -> None:
    positions = {p.code: p for p in XmlKtruSource(ktru_dir).load()}

    table = positions[TABLE_CODE]
    assert table.category == "Мебель"
    assert [c.name for c in table.characteristics] == ["Материал столешницы", "Длина"]
    length = table.char("Длина")
    assert length is not None and length.quantitative
    (value,) = length.values
    assert (value.min, value.min_op, value.max, value.max_op) == (
        1,
        Bound.greater_or_equal,
        2,
        Bound.less,
    )
    assert value.label() == "≥ 1 и < 2 Метр"


def test_kind_decides_multiple_choice_not_choice_type(ktru_dir: Path) -> None:
    positions = {p.code: p for p in XmlKtruSource(ktru_dir).load()}

    material = positions[TABLE_CODE].char("Материал столешницы")
    assert material is not None
    assert (material.kind, material.multi) == (CharacteristicKind.single, False)
    cabinet = positions[CABINET_CODE].char("Материал")
    assert cabinet is not None and cabinet.multi
    # Без `kind` — по `choiceType`.
    size = positions[ROBE_CODE].char("Размер")
    assert size is not None and size.kind == CharacteristicKind.multiple


def test_range_bounds_are_open_or_closed() -> None:
    value = Value(code="v", min=1, min_op=Bound.greater, max=2)

    assert [value.contains(x) for x in (1, 1.5, 2, 2.5)] == [False, True, True, False]


def test_json_snapshot_round_trips(ktru_dir: Path, tmp_path: Path) -> None:
    positions = XmlKtruSource(ktru_dir).load()
    dump_json(positions, tmp_path / "ktru.json")

    assert JsonKtruSource(tmp_path / "ktru.json").load() == positions


def test_sync_is_idempotent_in_memory(ktru_dir: Path) -> None:
    usecases = memory_usecases(ktru_dir)
    uow = MemoryUnitOfWork(MemoryStore())

    assert usecases.catalog_sync(uow).run().positions == 7
    assert usecases.catalog_sync(uow).run().positions == 7
    assert usecases.catalog_queries(uow).ready() == 7


def test_group_leaves_in_memory(ktru_dir: Path) -> None:
    usecases = memory_usecases(ktru_dir)
    uow = MemoryUnitOfWork(MemoryStore())
    usecases.catalog_sync(uow).run()
    queries = usecases.catalog_queries(uow)

    assert [p.code for p in queries.groups("Мебель")] == [TABLE_CODE, CABINET_CODE]
    assert [p.code for p in queries.group(CABINET_CODE).leaves] == CABINET_CHILDREN
    assert [p.code for p in queries.group(ROBE_CODE).leaves] == [ROBE_CODE]


def test_not_ready_before_sync(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["code"] == "catalog_empty"


def test_position_round_trips_through_database(settings: Settings, client: TestClient) -> None:
    sync_catalog(settings)
    sync_catalog(settings)

    assert client.get("/health/ready").json() == {"positions": 7}
    listed = client.get("/api/v1/positions", params={"category": "Мебель"}).json()
    assert [p["code"] for p in listed] == [TABLE_CODE, CABINET_CODE, *CABINET_CHILDREN]
    body = client.get(f"/api/v1/positions/{TABLE_CODE}").json()
    length = body["characteristics"][1]["values"][0]
    assert (length["min_inclusive"], length["max_inclusive"]) == (True, False)
    material = body["characteristics"][0]
    assert (material["kind"], material["multi"]) == ("single", False)
    assert material["values"][1]["label"] == "Массив дерева"


def test_unknown_position_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/positions/00.00")

    assert response.status_code == 404
    assert response.json()["code"] == "position_not_found"


def test_groups_of_category_are_templates_and_positions_without_parent(
    synced: Settings, client: TestClient
) -> None:
    furniture = client.get("/api/v1/groups", params={"category": "Мебель"}).json()
    tools = client.get("/api/v1/groups", params={"category": "Инструменты"}).json()

    assert [(g["code"], g["group"]) for g in furniture] == [
        (TABLE_CODE, TABLE_CODE),
        (CABINET_CODE, CABINET_CODE),
    ]
    assert [g["code"] for g in tools] == [AXE_CODE]


def test_template_with_children_is_not_a_leaf(synced: Settings, client: TestClient) -> None:
    body = client.get(f"/api/v1/groups/{CABINET_CODE}").json()

    assert body["position"]["code"] == CABINET_CODE
    assert [p["code"] for p in body["leaves"]] == CABINET_CHILDREN
    assert {p["group"] for p in body["leaves"]} == {CABINET_CODE}


@pytest.mark.parametrize("code", [ROBE_CODE, TABLE_CODE])
def test_group_without_children_is_its_own_leaf(
    code: str, synced: Settings, client: TestClient
) -> None:
    body = client.get(f"/api/v1/groups/{code}").json()

    assert [p["code"] for p in body["leaves"]] == [code]


def test_position_links_to_its_group(synced: Settings, client: TestClient) -> None:
    child = client.get(f"/api/v1/positions/{CABINET_CHILDREN[0]}").json()
    table = client.get(f"/api/v1/positions/{TABLE_CODE}").json()

    assert (child["group"], child["parent"]) == (CABINET_CODE, CABINET_CODE)
    assert table["group"] == TABLE_CODE


@pytest.mark.parametrize("code", [CABINET_CHILDREN[0], "00.00"])
def test_leaf_or_unknown_code_is_not_a_group(
    code: str, synced: Settings, client: TestClient
) -> None:
    response = client.get(f"/api/v1/groups/{code}")

    assert response.status_code == 404
    assert response.json()["code"] == "group_not_found"


def test_broken_parent_link_is_reported_by_sync(
    settings: Settings, client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    report = sync_catalog(settings)

    assert [p.code for p in report.outside_tree] == [HAMMER_CODE]
    assert HAMMER_CODE in caplog.text
    hammer = client.get(f"/api/v1/positions/{HAMMER_CODE}").json()
    assert hammer["group"] == "25.73.30.120-00000000"
    assert client.get("/api/v1/groups/25.73.30.120-00000000").status_code == 404
