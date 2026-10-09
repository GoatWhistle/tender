from pathlib import Path

from fastapi.testclient import TestClient

from app.adapter.ktru_json import JsonKtruSource, dump_json
from app.adapter.ktru_xml import XmlKtruSource
from app.domain.catalog import Bound, Value
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from composition import Repositories, build_usecases
from main import sync_catalog
from settings import Settings
from tests.conftest import TABLE_CODE


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


def test_range_bounds_are_open_or_closed() -> None:
    value = Value(code="v", min=1, min_op=Bound.greater, max=2)

    assert [value.contains(x) for x in (1, 1.5, 2, 2.5)] == [False, True, True, False]


def test_json_snapshot_round_trips(ktru_dir: Path, tmp_path: Path) -> None:
    positions = XmlKtruSource(ktru_dir).load()
    dump_json(positions, tmp_path / "ktru.json")

    assert JsonKtruSource(tmp_path / "ktru.json").load() == positions


def test_sync_is_idempotent_in_memory(ktru_dir: Path) -> None:
    store = MemoryStore()
    usecases = build_usecases(
        Repositories[MemoryUnitOfWork](catalog=lambda uow: MemoryCatalog(uow.store)),
        catalog_source=XmlKtruSource(ktru_dir),
    )
    uow = MemoryUnitOfWork(store)

    assert usecases.catalog_sync(uow).run() == 2
    assert usecases.catalog_sync(uow).run() == 2
    assert usecases.catalog_queries(uow).ready() == 2


def test_not_ready_before_sync(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["code"] == "catalog_empty"


def test_position_round_trips_through_database(settings: Settings, client: TestClient) -> None:
    sync_catalog(settings)
    sync_catalog(settings)

    assert client.get("/health/ready").json() == {"positions": 2}
    listed = client.get("/api/v1/positions", params={"category": "Мебель"}).json()
    assert [p["code"] for p in listed] == [TABLE_CODE]
    body = client.get(f"/api/v1/positions/{TABLE_CODE}").json()
    length = body["characteristics"][1]["values"][0]
    assert (length["min_inclusive"], length["max_inclusive"]) == (True, False)
    assert body["characteristics"][0]["values"][1]["label"] == "Массив дерева"


def test_unknown_position_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/positions/00.00")

    assert response.status_code == 404
    assert response.json()["code"] == "position_not_found"
