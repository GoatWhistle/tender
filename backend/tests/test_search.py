"""Поиск групп КТРУ по описанию: TF-IDF, векторный поиск и словарь синонимов, слитые RRF.

Тесты идут через HTTP API на заглушке эмбеддингов: модель подключается только в точке сборки.
Справочник — маленькая выгрузка из `conftest`, синонимы — `ALIASES` оттуда же.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.adapter.aliases_csv import CsvAliasSource
from app.adapter.stub import StubEmbeddings
from app.adapter.tfidf import TfidfLexicalIndex
from app.adapter.vector_numpy import NumpyVectorIndex
from app.domain.errors import ModelFailure
from app.domain.search import Alias, Method, contains_phrase, find_ktru_codes, normalize
from app.repository.memory.aliases import MemoryAliases
from app.repository.memory.catalog import MemoryCatalog
from app.repository.memory.unit_of_work import MemoryStore, MemoryUnitOfWork
from app.usecase.search import RETRY_AFTER, RRF_K, WEIGHTS, GroupIndex, GroupSearch, SearchQuery
from composition import checked_embeddings
from main import create_app, sync_catalog
from settings import Settings
from tests.conftest import (
    AXE_CODE,
    CABINET_CHILDREN,
    CABINET_CODE,
    ROBE_CODE,
    TABLE_CODE,
    memory_usecases,
    write_aliases,
)


@pytest.fixture
def search(synced: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(synced, embeddings=StubEmbeddings())) as client:
        yield client


def post(client: TestClient, text: str, **params: Any) -> dict[str, Any]:
    response = client.post("/api/v1/search", json={"text": text, **params})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def codes(body: dict[str, Any]) -> list[str]:
    return [g["code"] for g in body["groups"]]


def method(group: dict[str, Any], name: str) -> dict[str, Any]:
    found: dict[str, Any] = group["methods"][name]
    return found


# --- нормализация и правила совпадения


def test_normalize_folds_case_spaces_and_yo() -> None:
    assert normalize("  Ёлка\tЗЕЛЁНАЯ \n ") == "елка зеленая"


@pytest.mark.parametrize(
    ("text", "phrase", "found"),
    [
        ("болгарка makita 125 мм", "болгарка", True),
        ("болгарка makita 125 мм", "makita 125", True),
        ("столешница дубовая", "стол", False),
        ("стол-трансформер", "стол", True),
        ("мини-болгарка", "болгарка", True),
        ("болгарки", "болгарка", False),
    ],
)
def test_alias_matches_whole_words_only(text: str, phrase: str, found: bool) -> None:
    assert contains_phrase(text, phrase) is found


def test_ktru_codes_are_found_but_okpd2_codes_are_not() -> None:
    text = f"нужен {TABLE_CODE}, ОКПД2 31.01.11.150, и ещё 25.73.30.110-00000002."

    assert find_ktru_codes(text) == [TABLE_CODE, AXE_CODE]


# --- ответ и слияние RRF


def test_search_returns_groups_with_category_score_and_method_contributions(
    search: TestClient,
) -> None:
    body = post(search, "Стол письменный деревянный")

    top = body["groups"][0]
    assert (top["code"], top["name"], top["category"]) == (TABLE_CODE, "Стол письменный", "Мебель")
    assert top["found_by"] == "description"
    assert set(top["methods"]) == {"lexical", "vector", "alias"}
    lexical = method(top, "lexical")
    assert lexical["rank"] == 1
    assert lexical["score"] == pytest.approx(1 / (RRF_K + 1))
    assert method(top, "alias") == {"rank": None, "score": 0.0}
    for group in body["groups"]:
        total = sum(m["score"] for m in group["methods"].values())
        assert group["score"] == pytest.approx(total)
    scores = [g["score"] for g in body["groups"]]
    assert scores == sorted(scores, reverse=True)
    assert body["messages"] == []


def test_only_groups_are_returned(search: TestClient) -> None:
    found = codes(post(search, "Шкаф для одежды металлический"))

    assert set(found) <= {TABLE_CODE, CABINET_CODE, ROBE_CODE, AXE_CODE}
    assert not set(found) & set(CABINET_CHILDREN)
    assert found[0] == CABINET_CODE


def test_search_is_deterministic(search: TestClient) -> None:
    assert post(search, "халат синий") == post(search, "халат синий")


def test_source_text_is_returned_unchanged(search: TestClient) -> None:
    assert post(search, "  Халат  РАБОЧИЙ ё ")["text"] == "  Халат  РАБОЧИЙ ё "


# --- синонимы


def test_alias_leads_to_group_lexical_search_misses(search: TestClient) -> None:
    """«Колун» не делит с «Топор» ни одной символьной n-граммы — находит только словарь."""
    body = post(search, "Колун 2 кг")

    top = body["groups"][0]
    assert top["code"] == AXE_CODE
    assert method(top, "lexical")["rank"] is None
    assert method(top, "alias") == {
        "rank": 1,
        "score": pytest.approx(WEIGHTS[Method.alias] / (RRF_K + 1)),
    }


def test_alias_outweighs_group_found_by_both_other_methods(search: TestClient) -> None:
    """Синоним — курируемое знание: он ставит группу выше той, что первой нашли и TF-IDF,
    и вектор."""
    body = post(search, "Стол колун")

    table = next(g for g in body["groups"] if g["code"] == TABLE_CODE)
    assert (method(table, "lexical")["rank"], method(table, "vector")["rank"]) == (1, 1)
    assert body["groups"][0]["code"] == AXE_CODE


def test_unreviewed_alias_is_ignored(search: TestClient) -> None:
    body = post(search, "секач для мяса")

    for group in body["groups"]:
        assert method(group, "alias")["rank"] is None


def test_longer_alias_ranks_higher(search: TestClient) -> None:
    """«рабочий халат» (13 знаков) длиннее «колун» (5): халат — первый в списке синонимов."""
    body = post(search, "колун и рабочий халат")

    by_code = {g["code"]: g for g in body["groups"]}
    assert method(by_code[ROBE_CODE], "alias")["rank"] == 1
    assert method(by_code[AXE_CODE], "alias")["rank"] == 2


def test_alias_on_missing_group_is_reported_by_sync(settings: Settings) -> None:
    report = sync_catalog(settings)

    assert [(a.group_code, a.alias) for a in report.orphan_aliases] == [
        ("00.00.00.000-00000000", "призрак")
    ]
    assert report.aliases == 4


# --- код КТРУ в тексте


def test_exact_code_puts_its_group_first(search: TestClient) -> None:
    body = post(search, f"Стол письменный, код {AXE_CODE}")

    top = body["groups"][0]
    assert (top["code"], top["found_by"]) == (AXE_CODE, "code")
    assert body["groups"][1]["code"] == TABLE_CODE
    assert body["groups"][1]["found_by"] == "description"
    assert body["messages"] == []


def test_code_of_leaf_position_puts_its_group_first(search: TestClient) -> None:
    body = post(search, f"по КТРУ {CABINET_CHILDREN[1]}")

    assert (body["groups"][0]["code"], body["groups"][0]["found_by"]) == (CABINET_CODE, "code")


def test_unknown_code_gives_message_and_searches_by_description(search: TestClient) -> None:
    unknown = "31.01.11.150-99999999"
    body = post(search, f"Стол письменный {unknown}")

    assert body["groups"][0]["code"] == TABLE_CODE
    assert body["groups"][0]["found_by"] == "description"
    (message,) = body["messages"]
    assert message["code"] == "ktru_code_not_found"
    assert unknown in message["text"]


# --- категория и лимит


def test_category_filters_groups(search: TestClient) -> None:
    body = post(search, "Стол письменный", category="Одежда")

    assert codes(body) == [ROBE_CODE]
    assert body["groups"][0]["category"] == "Одежда"


def test_limit_cuts_result_and_is_capped(search: TestClient) -> None:
    assert len(post(search, "Стол", limit=2)["groups"]) == 2
    assert len(post(search, "Стол")["groups"]) == 4

    response = search.post("/api/v1/search", json={"text": "Стол", "limit": 51})
    assert response.status_code == 422


def test_unknown_category_is_rejected(search: TestClient) -> None:
    response = search.post("/api/v1/search", json={"text": "Стол", "category": "Еда"})

    assert response.status_code == 422


# --- готовность


def test_without_embeddings_url_search_is_503_and_rest_works(
    synced: Settings, client: TestClient
) -> None:
    assert synced.embeddings_url is None
    response = client.post("/api/v1/search", json={"text": "Стол"})

    assert response.status_code == 503
    assert response.json()["code"] == "model_not_configured"
    assert client.get("/health/ready").status_code == 200
    assert client.get(f"/api/v1/groups/{TABLE_CODE}").status_code == 200


def test_search_before_sync_is_catalog_empty(settings: Settings) -> None:
    with TestClient(create_app(settings, embeddings=StubEmbeddings())) as client:
        response = client.post("/api/v1/search", json={"text": "Стол"})

    assert response.status_code == 503
    assert response.json()["code"] == "catalog_empty"


def test_model_failure_during_search_is_503(synced: Settings) -> None:
    stub = StubEmbeddings()
    with TestClient(create_app(synced, embeddings=stub)) as client:
        stub.fail()
        response = client.post("/api/v1/search", json={"text": "Стол"})

    assert response.status_code == 503
    assert response.json()["code"] == "technical_error"


# --- сценарий на in-memory хранилищах


def test_search_in_memory(ktru_dir: Path) -> None:
    usecases = memory_usecases(ktru_dir)
    uow = MemoryUnitOfWork(MemoryStore())
    usecases.catalog_sync(uow).run()

    result = usecases.group_search(uow).search(SearchQuery("колун"))

    assert result.groups[0].group.code == AXE_CODE
    assert result.groups[0].score == pytest.approx(sum(c.score for c in result.groups[0].methods))


def test_csv_alias_source_reads_reviewed_flag(tmp_path: Path) -> None:
    aliases = CsvAliasSource(write_aliases(tmp_path / "aliases.csv")).load()

    assert Alias(AXE_CODE, "колун", "manual", True) in aliases
    assert Alias(AXE_CODE, "секач", "manual", False) in aliases


def test_csv_alias_source_rejects_bad_flag(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    path.write_text("group_code,alias,source,reviewed\nX,колун,manual,да\n", encoding="utf-8")

    with pytest.raises(ValueError, match="строка 2"):
        CsvAliasSource(path).load()


def test_csv_alias_source_accepts_bom(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    path.write_text("﻿group_code,alias,source,reviewed\nX,колун,manual,true\n", encoding="utf-8")

    assert CsvAliasSource(path).load() == [Alias("X", "колун", "manual", True)]


def test_blank_text_is_rejected(search: TestClient) -> None:
    assert search.post("/api/v1/search", json={"text": "   "}).status_code == 422


def test_failed_build_is_not_retried_until_cooldown(ktru_dir: Path) -> None:
    """Лежащая модель: следующая попытка сборки — не раньше `RETRY_AFTER`, до неё сразу ошибка."""
    usecases = memory_usecases(ktru_dir)
    uow = MemoryUnitOfWork(MemoryStore())
    usecases.catalog_sync(uow).run()
    stub = StubEmbeddings()
    now = [0.0]
    embeddings = checked_embeddings(stub)
    index = GroupIndex(TfidfLexicalIndex(), NumpyVectorIndex(), embeddings, lambda: now[0])
    search = GroupSearch(uow, MemoryCatalog(uow.store), MemoryAliases(uow.store), index)

    stub.fail()
    with pytest.raises(ModelFailure):
        search.warm()
    stub.fault = None
    now[0] = RETRY_AFTER - 1
    with pytest.raises(ModelFailure):
        search.warm()
    assert not index.built

    now[0] = RETRY_AFTER
    search.warm()
    assert index.built


def test_vector_index_on_empty_documents_finds_nothing() -> None:
    index = NumpyVectorIndex()
    index.build([])

    assert index.search((1.0, 0.0)) == []
