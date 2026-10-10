"""Головы наименований СТЕ, таблица разметки и строки словаря (`evals/ste/ste_heads.py`).

Без сети и без выгрузок организаторов: выгрузки — маленькие синтетические xlsx, поиск групп —
подстановка, которая запоминает запросы.
"""

from collections.abc import Sequence
from pathlib import Path

import openpyxl
import pytest
from evals.ste import ste_heads as sh

from app.adapter.aliases import CsvAliasesSource
from app.domain.aliases import Alias

HEADER = ("ID СТЕ", "Наименование СТЕ", "Модель", "Производитель", "Страна", "Характеристики")


def export(path: Path, rows: Sequence[tuple[int, str, str]]) -> Path:
    """Выгрузка в формате организаторов: Лист1, заголовок, строки `(ID, наименование, бренд)`."""
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.title = "Лист1"
    sheet.append(HEADER)
    for ste_id, name, producer in rows:
        sheet.append((ste_id, name, "-", producer, "РОССИЯ", ""))
    book.create_sheet("Лист2")
    book.save(path)
    return path


class FakeSearch:
    """Top-5 по первому слову запроса; каждый запрос запоминается."""

    def __init__(self, groups: dict[str, list[tuple[str, str]]] | None = None) -> None:
        self.queries: list[str] = []
        self._groups = groups or {}

    def __call__(self, description: str) -> list[sh.Found]:
        self.queries.append(description)
        found = self._groups.get(description.split()[0].lower(), [("00.00.00.000-00000001", "X")])
        return [sh.Found(code, name) for code, name in found]


@pytest.mark.parametrize(
    ("name", "producer", "head"),
    [
        ('Дрель-шуруповерт аккумуляторная Ставр "ДА-10,8/2"', "Ставр", "дрель-шуруповерт"),
        ("Угловая шлифовальная машина Makita GA5030", "Makita", "угловая шлифовальная машина"),
        ("УШМ Bosch GWS 750", "Robert Bosch Gmbh", "ушм"),
        ("Шкаф-купе, 2 двери", "Неизвестен", "шкаф-купе"),
        ("Стойка для рекламных материалов напольная", "Неизвестен", "стойка"),
        ("Ёлка  искусственная 150 см", "", "елка"),
        ("Детский рюкзак", "", "детский рюкзак"),
        ("Приспособление для резки плитки", "", "приспособление"),
        ("Покрытие напольное резиновое", "", "покрытие"),
        ("Кресло офисное", 'ООО "Кресло-Сервис"', "кресло"),
        ("Шкаф мебельный", "Мебельная фабрика", "шкаф"),
        ("Металлический складной стеллажный шкаф", "", None),
        ("Угловая Makita 125", "Makita", None),
        ("Угловая, шлифовальная", "", None),
        ("Ставр дрель ударная", "Ставр", None),
        ("Makita HR2450 перфоратор", "", None),
        ('"Ромашка" платье', "", None),
        ("125 мм диск отрезной", "", None),
        ("(комплект) перчатки", "", None),
        ("", "", None),
    ],
)
def test_head_is_leading_words_before_brand_digit_quote_or_latin(
    name: str, producer: str, head: str | None
) -> None:
    assert sh.head_of(name, producer) == head


def tools(path: Path) -> Path:
    return export(
        path / "Инструменты.xlsx",
        [
            *((100 + i, f"Болгарка Makita {i}", "Makita") for i in range(6)),
            *((200 + i, f"Перфоратор Bosch {i}", "Bosch") for i in range(4)),
            (300, "Ножовка по дереву 500 мм", "Зубр"),
            (301, "Ножовка по металлу 300 мм", "Зубр"),
            (400, "Makita HR2450", "Makita"),
        ],
    )


def test_table_counts_heads_and_takes_seeded_examples(tmp_path: Path) -> None:
    search = FakeSearch({"болгарка": [("28.24.11.000-00000042", "Машина шлифовальная")]})

    mining = sh.mine([tools(tmp_path)], frozenset(), search, seed=1)

    assert [(r.category, r.head, r.n_ste) for r in mining.rows] == [
        ("Инструменты", "болгарка", 6),
        ("Инструменты", "перфоратор", 4),
        ("Инструменты", "ножовка", 2),
    ]
    first = mining.rows[0]
    assert len(first.examples.split(" | ")) == 3
    assert first.example_rows.startswith("Инструменты.xlsx#")
    assert first.top5 == "28.24.11.000-00000042 Машина шлифовальная [top1 3/3, top5 3/3]"
    assert (first.label, first.note) == ("", "")
    stats = mining.categories["Инструменты"]
    assert (stats.rows, stats.no_head, stats.heads, stats.selected_rows) == (13, 1, 3, 12)
    assert len(search.queries) == 3 + 3 + 2

    again = sh.mine([tools(tmp_path)], frozenset(), FakeSearch(), seed=1)
    assert [r.example_rows for r in again.rows] == [r.example_rows for r in mining.rows]


def test_threshold_stops_at_coverage_and_head_limit(tmp_path: Path) -> None:
    path = tools(tmp_path)

    assert [r.head for r in sh.mine([path], frozenset(), FakeSearch(), coverage=0.4).rows] == [
        "болгарка"
    ]
    assert [r.head for r in sh.mine([path], frozenset(), FakeSearch(), max_heads=2).rows] == [
        "болгарка",
        "перфоратор",
    ]
    assert [r.head for r in sh.mine([path], frozenset(), FakeSearch(), min_count=3).rows] == [
        "болгарка",
        "перфоратор",
    ]


def test_holdout_rows_are_neither_heads_nor_examples(tmp_path: Path) -> None:
    path = tools(tmp_path)
    holdout = tmp_path / "holdout.txt"
    holdout.write_text("# holdout #14\n100\n101\n300\n301\n\n", encoding="utf-8")
    ids = sh.read_holdout(holdout)
    assert ids == frozenset({"100", "101", "300", "301"})
    search = FakeSearch()

    mining = sh.mine([path], ids or frozenset(), search)

    assert [(r.head, r.n_ste) for r in mining.rows] == [("болгарка", 4), ("перфоратор", 4)]
    assert not {"Болгарка Makita 0", "Болгарка Makita 1"} & set(search.queries)
    assert not any("Ножовка" in q for q in search.queries)
    lines = {int(ref.split("#")[1]) for r in mining.rows for ref in r.example_rows.split("; ")}
    assert not lines & {2, 3, 12, 13}
    assert mining.categories["Инструменты"].holdout == 4


def test_missing_holdout_file_excludes_nothing(tmp_path: Path) -> None:
    assert sh.read_holdout(tmp_path / "нет.txt") is None


def test_table_is_byte_identical_and_keeps_labels(tmp_path: Path) -> None:
    path = tools(tmp_path)
    table = tmp_path / "heads.csv"
    sh.write_table(table, sh.mine([path], frozenset(), FakeSearch()).rows)
    first = table.read_bytes()
    sh.write_table(table, sh.mine([path], frozenset(), FakeSearch()).rows)
    assert table.read_bytes() == first

    rows = sh.read_table(table)
    labeled = [
        sh.TableRow(**{**vars(r), "label": "group:28.24.11.000-00000042", "note": "ушм тоже"})
        if r.head == "болгарка"
        else r
        for r in rows
    ]
    orphan = sh.TableRow("лобзик", "Инструменты", 1, "Инструменты.xlsx#9", "Лобзик", "", "none", "")
    sh.write_table(table, [*labeled, orphan])

    merged = sh.merge_labels(sh.mine([path], frozenset(), FakeSearch()).rows, sh.read_table(table))
    sh.write_table(table, merged)

    by_head = {r.head: r for r in sh.read_table(table)}
    assert (by_head["болгарка"].label, by_head["болгарка"].note) == (
        "group:28.24.11.000-00000042",
        "ушм тоже",
    )
    assert by_head["перфоратор"].label == ""
    assert by_head["лобзик"].label == "none"


GRINDER = "28.24.11.000-00000042"
STOOL = "31.09.10.000-00000019"


def row(head: str, label: str, category: str = "Инструменты", line: int = 7) -> sh.TableRow:
    return sh.TableRow(
        head, category, 5, f"{category}.xlsx#{line}; {category}.xlsx#9", head, "", label, ""
    )


def test_group_labels_become_reviewed_aliases_with_ste_source() -> None:
    plan = sh.plan_aliases(
        [
            row("ушм", f"group:{GRINDER}"),
            row("пшм", f"group:{GRINDER}", line=12),
            row("табурет", f"group:{STOOL}", "Мебель", 3),
            row("сверло", "none"),
            row("набор", "generic"),
            row("ключ", "skip"),
            row("зубило", ""),
            row("шкаф-купе", "group:31.01.12.160-99999999", "Мебель"),
        ],
        existing=[Alias(GRINDER, "ушм", "manual", True)],
        groups={GRINDER, STOOL},
    )

    assert plan.added == [
        Alias(GRINDER, "пшм", "ste:Инструменты.xlsx#12", True),
        Alias(STOOL, "табурет", "ste:Мебель.xlsx#3", True),
    ]
    assert [s.head for s in plan.skipped] == ["ушм", "шкаф-купе"]
    assert "не группа справочника" in plan.skipped[1].reason
    assert plan.by_label == {"group": 4, "none": 1, "generic": 1, "skip": 1, "": 1}
    assert [r.head for r in plan.none] == ["сверло"]


def test_same_head_with_different_groups_is_an_error() -> None:
    with pytest.raises(sh.AliasConflict, match="ушм"):
        sh.plan_aliases(
            [row("ушм", f"group:{GRINDER}"), row("ушм", f"group:{STOOL}", "Мебель")],
            existing=[],
            groups={GRINDER, STOOL},
        )


@pytest.mark.parametrize("label", ["группа", "group:28.24", "none:нет в КТРУ", "skip:x"])
def test_unknown_label_is_an_error(label: str) -> None:
    with pytest.raises(ValueError, match="Неизвестные пометки"):
        sh.plan_aliases([row("ушм", label)], existing=[], groups={GRINDER})


def test_appended_aliases_keep_existing_rows_and_pass_validation(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    head = f"group_code,alias,source,reviewed\n{GRINDER},болгарка,manual,true\n"
    path.write_text(head, encoding="utf-8")

    sh.append_aliases(path, [Alias(STOOL, "табурет", "ste:Мебель.xlsx#3", True)])

    text = path.read_text(encoding="utf-8")
    assert text.startswith(head)
    assert text.endswith(f"{STOOL},табурет,ste:Мебель.xlsx#3,true\n")
    assert Alias(STOOL, "табурет", "ste:Мебель.xlsx#3", True) in CsvAliasesSource(path).load()


def test_aliases_go_to_a_new_dictionary_with_header(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"

    sh.append_aliases(path, [Alias(STOOL, "табурет", "ste:Мебель.xlsx#3", True)])

    assert CsvAliasesSource(path).load() == [Alias(STOOL, "табурет", "ste:Мебель.xlsx#3", True)]


def test_invalid_aliases_leave_the_dictionary_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "aliases.csv"
    text = f"group_code,alias,source,reviewed\n{GRINDER},болгарка,manual,true\n"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="Повтор"):
        sh.append_aliases(path, [Alias(GRINDER, "Болгарка", "ste:x#2", True)])

    assert path.read_text(encoding="utf-8") == text
    assert [p.name for p in tmp_path.iterdir()] == ["aliases.csv"]
