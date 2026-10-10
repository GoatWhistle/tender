"""Головы наименований СТЕ → продуктовый поиск групп → таблица для ручной разметки (#38);
из размеченной таблицы — строки словаря синонимов (#31).

`table`: читает выгрузки организаторов (Лист1), исключает строки holdout #14, выделяет головы
наименований, частые головы прогоняет через `POST /api/v1/search` готовой базы (limit 5, без
категории; векторизация документов запрещена) и пишет `evals/datasets/ste_heads_v1.csv`, отчёт —
`evals/reports/<дата>-ste-heads.md` и `.json`. Уже заполненные `label`/`note` сохраняются.

`aliases`: строки `group:<код>` размеченной таблицы дописывает в `data/aliases.csv`.

Правило головы, параметры и команды — `docs/search.md`, «Словарь».
"""

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import random
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Collection, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.adapter.aliases import CsvAliasesSource  # noqa: E402
from app.domain.aliases import Alias  # noqa: E402
from app.domain.search import normalize  # noqa: E402

EXPORTS = REPO / "data" / "yandex_disk" / "Примеры выгрузок"
CATEGORIES = ("Инструменты", "Мебель", "Одежда")
TABLE = REPO / "evals" / "datasets" / "ste_heads_v1.csv"
HOLDOUT = REPO / "evals" / "datasets" / "ste_holdout_v1_ids.txt"
DATABASE = REPO / "artifacts" / "ktru-search.sqlite3"
ALIASES = REPO / "data" / "aliases.csv"
REPORTS = REPO / "evals" / "reports"

SHEET = "Лист1"
ID, NAME, PRODUCER = "ID СТЕ", "Наименование СТЕ", "Производитель"
HEAD_WORDS = 3
WORD = re.compile(r"[а-я]+(?:-[а-я]+)*")
# Прилагательное в начале наименования не голова само по себе: «угловая шлифовальная машина».
ADJECTIVE = re.compile(r"(?:ый|ий|ой|ая|яя|ое|ее|ые|ие)$")
# Существительные с окончанием прилагательного: «приспособление», «покрытие», «средство».
NOUN = re.compile(r"(?:ение|ание|тие|ствие|ство)$")
_PREPOSITIONS = "без в во для до за и из или к ко на над о об от по под при про с со у"
PREPOSITIONS = frozenset(_PREPOSITIONS.split())
# Слова `Производителя`, которые не бренд: форма собственности, «фабрика», «мебельная».
_NOT_BRAND = """ооо оао зао пао нпо тов ип общество ограниченной ответственностью акционерное
публичное закрытое открытое компания фабрика завод группа торговый дом предприятие
производственная производственное производственный мебельная мебельный швейная швейное швейный
неизвестен россия"""
NOT_BRAND = frozenset(_NOT_BRAND.split())
CODE = re.compile(r"\d{2}\.\d{2}\.\d{2}\.\d{3}-\d{8}")
LABELS = ("group", "none", "generic", "skip")
# Промах поиска — размеченная группа не первая хотя бы в 2 примерах из 3: сессия берёт первую.
MISSES = 2
TOP1 = re.compile(r"\[top1 (?P<first>\d+)/(?P<of>\d+), top5 \d+/\d+\]$")
SEPARATOR = " | "
REF_SEPARATOR = "; "


@dataclass(frozen=True)
class SteRow:
    file: str
    line: int
    ste_id: str
    name: str
    producer: str

    @property
    def ref(self) -> str:
        return f"{self.file}#{self.line}"


@dataclass(frozen=True)
class Found:
    code: str
    name: str


Search = Callable[[str], Sequence[Found]]


@dataclass(frozen=True)
class TableRow:
    head: str
    category: str
    n_ste: int
    example_rows: str
    examples: str
    top5: str
    label: str
    note: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.category, self.head)


COLUMNS = tuple(f.name for f in fields(TableRow))


@dataclass
class CategoryStats:
    rows: int = 0
    holdout: int = 0
    no_head: int = 0
    heads: int = 0
    selected: int = 0
    selected_rows: int = 0
    top1_disagree: int = 0


@dataclass
class Mining:
    rows: list[TableRow]
    categories: dict[str, CategoryStats]
    top1: dict[tuple[str, str], list[str | None]] = field(default_factory=dict)


def head_of(name: str, producer: str = "") -> str | None:
    """1–3 начальных слова до бренда, цифры, кавычек, латиницы, знака препинания или предлога:
    прилагательные в начале и первое слово после них. Нет такого слова — головы нет."""
    brand = set(re.findall(r"[\w-]{3,}", normalize(producer))) - NOT_BRAND
    words: list[str] = []
    for token in normalize(name).split():
        word = token.rstrip(",.;:")
        if not WORD.fullmatch(word) or word in brand or word in PREPOSITIONS:
            break
        words.append(word)
        last = word.rsplit("-", 1)[-1]
        if not ADJECTIVE.search(last) or NOUN.search(last):
            return " ".join(words)
        if word != token or len(words) == HEAD_WORDS:
            break
    return None


def read_export(path: Path) -> list[SteRow]:
    """Строки Лист1 выгрузки; `line` — номер строки Excel. Строки без наименования пропущены."""
    import openpyxl

    book = openpyxl.load_workbook(path, read_only=True)
    try:
        rows = book[SHEET].iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(rows)]
        try:
            columns = [header.index(c) for c in (ID, NAME, PRODUCER)]
        except ValueError:
            raise ValueError(f"{path.name}: нет столбцов {ID}, {NAME}, {PRODUCER}") from None
        found = []
        for line, values in enumerate(rows, 2):
            ste_id, name, producer = (_cell(values, i) for i in columns)
            if name:
                found.append(SteRow(path.name, line, ste_id, name, producer))
        return found
    finally:
        book.close()


def _cell(values: tuple[Any, ...], i: int) -> str:
    value = values[i] if i < len(values) else None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return "" if value is None else str(value).strip()


def read_holdout(path: Path) -> frozenset[str] | None:
    """`ID СТЕ` holdout #14 — по одному в строке, `#` — комментарий. Нет файла — `None`."""
    if not path.is_file():
        return None
    lines = (line.split("#", 1)[0].strip() for line in path.read_text("utf-8").splitlines())
    return frozenset(line for line in lines if line)


def mine(
    exports: Sequence[Path],
    holdout: frozenset[str],
    search: Search,
    *,
    coverage: float = 0.9,
    max_heads: int = 300,
    min_count: int = 2,
    examples: int = 3,
    seed: int = 38,
) -> Mining:
    """Головы каждой выгрузки по убыванию частоты, пока не покрыта доля `coverage` строк
    категории (не больше `max_heads`, не реже `min_count`); по `examples` примеров — в поиск."""
    table: list[TableRow] = []
    categories: dict[str, CategoryStats] = {}
    top1: dict[tuple[str, str], list[str | None]] = {}
    for path in exports:
        category = path.stem
        stats = categories[category] = CategoryStats()
        by_head: dict[str, list[SteRow]] = defaultdict(list)
        for ste in read_export(path):
            if ste.ste_id in holdout:
                stats.holdout += 1
                continue
            stats.rows += 1
            head = head_of(ste.name, ste.producer)
            if head is None:
                stats.no_head += 1
            else:
                by_head[head].append(ste)
        stats.heads = len(by_head)
        for head, rows in sorted(by_head.items(), key=lambda item: (-len(item[1]), item[0])):
            if (
                stats.selected_rows >= coverage * stats.rows
                or stats.selected >= max_heads
                or len(rows) < min_count
            ):
                break
            stats.selected += 1
            stats.selected_rows += len(rows)
            picked = sorted(
                random.Random(f"{seed}|{category}|{head}").sample(rows, min(examples, len(rows))),
                key=lambda s: s.line,
            )
            results = [list(search(s.name))[:5] for s in picked]
            firsts = [r[0].code if r else None for r in results]
            top1[(category, head)] = firsts
            stats.top1_disagree += len(set(firsts)) > 1
            table.append(
                TableRow(
                    head=head,
                    category=category,
                    n_ste=len(rows),
                    example_rows=REF_SEPARATOR.join(s.ref for s in picked),
                    examples=SEPARATOR.join(" ".join(s.name.split()) for s in picked),
                    top5=_top5(results),
                    label="",
                    note="",
                )
            )
    return Mining(_sorted(table), categories, top1)


def _top5(results: Sequence[Sequence[Found]]) -> str:
    """Объединённый top-5 примеров: группа, сколько примеров дали её top-1 и в top-5."""
    names: dict[str, str] = {}
    first: Counter[str] = Counter()
    seen: Counter[str] = Counter()
    best: dict[str, int] = {}
    for found in results:
        for rank, group in enumerate(found, 1):
            names[group.code] = group.name
            seen[group.code] += 1
            first[group.code] += rank == 1
            best[group.code] = min(rank, best.get(group.code, rank))
    n = len(results)
    order = sorted(names, key=lambda c: (-first[c], -seen[c], best[c], c))
    return SEPARATOR.join(
        f"{c} {names[c]} [top1 {first[c]}/{n}, top5 {seen[c]}/{n}]" for c in order
    )


def _sorted(rows: Sequence[TableRow]) -> list[TableRow]:
    return sorted(rows, key=lambda r: (-r.n_ste, r.category, r.head))


def merge_labels(new: Sequence[TableRow], old: Sequence[TableRow]) -> list[TableRow]:
    """Новая таблица с `label`/`note` прежней по `(category, head)`. Размеченная строка, чьей
    головы больше нет среди частых, остаётся как была."""
    marks = {r.key: r for r in old if r.label or r.note}
    merged = [
        TableRow(**{**vars(r), "label": marks[r.key].label, "note": marks[r.key].note})
        if r.key in marks
        else r
        for r in new
    ]
    keys = {r.key for r in new}
    return _sorted([*merged, *(r for r in marks.values() if r.key not in keys)])


def write_table(path: Path, rows: Sequence[TableRow]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows([getattr(r, c) for c in COLUMNS] for r in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(buffer.getvalue(), encoding="utf-8")


def read_table(path: Path) -> list[TableRow]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"{path}: ожидались столбцы {','.join(COLUMNS)}")
        rows = []
        for row in reader:
            text = {c: (row[c] or "").strip() for c in COLUMNS}
            rows.append(
                TableRow(
                    head=text["head"],
                    category=text["category"],
                    n_ste=int(text["n_ste"]),
                    example_rows=text["example_rows"],
                    examples=text["examples"],
                    top5=text["top5"],
                    label=text["label"],
                    note=text["note"],
                )
            )
        return rows


class AliasConflict(ValueError):
    pass


@dataclass(frozen=True)
class Skipped:
    head: str
    reason: str


@dataclass
class AliasPlan:
    added: list[Alias] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    by_label: Counter[str] = field(default_factory=Counter)
    none: list[TableRow] = field(default_factory=list)


def top1_count(top5: str, code: str) -> tuple[int, int]:
    """Сколько примеров головы дали группу `code` первой и сколько примеров всего — из `top5`.
    Группы нет в `top5` — `(0, число примеров)`; пустой `top5` — `(0, 0)`, фильтр не
    применяется."""
    examples = 0
    for part in top5.split(SEPARATOR) if top5 else ():
        match = TOP1.search(part)
        if match is None:
            continue
        examples = int(match["of"])
        if part.startswith(code + " "):
            return int(match["first"]), examples
    return 0, examples


def plan_aliases(
    rows: Sequence[TableRow], existing: Sequence[Alias], groups: Collection[str]
) -> AliasPlan:
    """Строки словаря из пометок `group:<код>`: проверенные, источник — первый пример головы.
    Синоним нужен только там, где поиск промахивается: группа не первая хотя бы в `MISSES`
    примерах, иначе пропуск. Код не группа справочника или голова уже в словаре — пропуск;
    голова на разные группы —
    `AliasConflict`; пометка вне `group:<код>`/`none`/`generic`/`skip`/пусто — `ValueError`."""
    plan = AliasPlan()
    labeled: list[tuple[TableRow, str]] = []
    invalid = []
    for row in rows:
        kind, _, code = row.label.partition(":")
        if row.label and not (
            (kind == "group" and CODE.fullmatch(code)) or row.label in LABELS[1:]
        ):
            invalid.append(f"{row.category}/{row.head}: {row.label!r}")
            continue
        plan.by_label[kind] += 1
        if kind == "group":
            labeled.append((row, code))
        elif kind == "none":
            plan.none.append(row)
    if invalid:
        raise ValueError("Неизвестные пометки: " + "; ".join(invalid))

    codes: dict[str, set[str]] = defaultdict(set)
    for row, code in labeled:
        codes[normalize(row.head)].add(code)
    conflicts = sorted(f"{h} → {', '.join(sorted(c))}" for h, c in codes.items() if len(c) > 1)
    if conflicts:
        raise AliasConflict("Голова размечена разными группами: " + "; ".join(conflicts))

    known = {normalize(a.alias) for a in existing}
    for row, code in labeled:
        alias = normalize(row.head)
        first, examples = top1_count(row.top5, code)
        if code not in groups:
            plan.skipped.append(Skipped(row.head, f"код {code} не группа справочника"))
        elif examples and examples - first < MISSES:
            reason = f"поиск уже ставит группу первой: {first}/{examples} примеров"
            plan.skipped.append(Skipped(row.head, reason))
        elif alias in known:
            plan.skipped.append(Skipped(row.head, "голова уже в словаре"))
        else:
            known.add(alias)
            source = "ste:" + row.example_rows.split(REF_SEPARATOR)[0]
            plan.added.append(Alias(code, alias, source, True))
    return plan


def append_aliases(path: Path, aliases: Sequence[Alias]) -> None:
    """Дописывает строки в конец словаря; результат должен пройти загрузку продукта, иначе
    файл не меняется."""
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if not text.strip():
        text = "group_code,alias,source,reviewed\n"
    if text and not text.endswith("\n"):
        text += "\n"
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(
        (a.group_code, a.alias, a.source, "true" if a.reviewed else "false") for a in aliases
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, suffix=".csv", delete=False
    ) as stream:
        stream.write(text + buffer.getvalue())
    try:
        CsvAliasesSource(Path(stream.name)).load()
        if path.is_file():
            shutil.copymode(path, stream.name)
        else:
            os.chmod(stream.name, 0o644)
        os.replace(stream.name, path)
    finally:
        Path(stream.name).unlink(missing_ok=True)


# Проводка продукта: та же, что у `evals/smoke/bench_search.py`.


@contextmanager
def database_copy(database: Path) -> Iterator[Path]:
    """Приложение работает с копией: готовый артефакт в git не меняется."""
    with tempfile.TemporaryDirectory() as directory:
        copy = Path(directory) / database.name
        shutil.copyfile(database, copy)
        yield copy


def product_settings(database: Path, embeddings_url: str | None, model: str) -> Any:
    from settings import Settings

    return Settings(
        database_url=f"sqlite:///{database.resolve()}",
        embeddings_url=embeddings_url,
        embeddings_model=model,
    )


@contextmanager
def product_search(database: Path, embeddings_url: str, model: str) -> Iterator[Search]:
    from fastapi.testclient import TestClient

    from main import configured_embeddings, create_app

    settings = product_settings(database, embeddings_url, model)
    configured = configured_embeddings(settings)
    if configured is None:
        raise ValueError("нет адреса сервиса эмбеддингов")
    embeddings = configured

    class QueryOnly:
        """Запросы — реальному сервису; векторизация документов ломает прогон."""

        dimension = embeddings.dimension

        def embed_documents(self, texts: Sequence[str]) -> Any:
            raise RuntimeError("Готовая база не должна векторизовать документы")

        def embed_queries(self, texts: Sequence[str]) -> Any:
            return embeddings.embed_queries(texts)

        def health(self) -> Any:
            return embeddings.health()

    with TestClient(create_app(settings, embeddings=QueryOnly())) as client:

        def search(description: str) -> list[Found]:
            response = client.post("/api/v1/search", json={"description": description, "limit": 5})
            response.raise_for_status()
            return [Found(g["code"], g["name"]) for g in response.json()["groups"]]

        yield search


def product_groups(database: Path) -> set[str]:
    from sqlalchemy.orm import Session

    from app.repository.database import create_db_engine
    from app.repository.unit_of_work import SqlUnitOfWork
    from main import production_usecases

    settings = product_settings(database, None, "")
    engine = create_db_engine(settings.database_url)
    try:
        with closing(SqlUnitOfWork(Session(engine))) as uow:
            return {p.code for p in production_usecases(settings).catalog_queries(uow).groups()}
    finally:
        engine.dispose()


def _relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def run_table(args: argparse.Namespace) -> None:
    from settings import Settings

    holdout = read_holdout(args.holdout)
    old = read_table(args.output) if args.output.is_file() else []
    exports = [args.exports / f"{c}.xlsx" for c in CATEGORIES]
    with (
        database_copy(args.database) as copy,
        product_search(copy, args.embeddings_url, args.model) as search,
    ):
        mining = mine(
            exports,
            holdout or frozenset(),
            search,
            coverage=args.coverage,
            max_heads=args.max_heads,
            min_count=args.min_count,
            seed=args.seed,
        )
    rows = merge_labels(mining.rows, old)
    write_table(args.output, rows)

    stats = mining.categories
    total = CategoryStats(
        **{f.name: sum(getattr(s, f.name) for s in stats.values()) for f in fields(CategoryStats)}
    )
    report = {
        "date": args.date,
        "model": args.model,
        "revision": Settings().embeddings_revision,
        "database": _relative(args.database),
        "database_sha256": hashlib.sha256(args.database.read_bytes()).hexdigest(),
        "exports": [_relative(p) for p in exports],
        "holdout": {
            "path": _relative(args.holdout),
            "found": holdout is not None,
            "ids": len(holdout or ()),
            "excluded_rows": total.holdout,
        },
        "parameters": {
            "coverage": args.coverage,
            "max_heads": args.max_heads,
            "min_count": args.min_count,
            "examples": 3,
            "seed": args.seed,
            "limit": 5,
            "category_filter": None,
        },
        "table": _relative(args.output),
        "table_rows": len(rows),
        "kept_labels": sum(bool(r.label or r.note) for r in rows),
        "categories": {c: vars(s) for c, s in [*stats.items(), ("Всего", total)]},
        "top1": [
            {"category": c, "head": h, "examples": codes}
            for (c, h), codes in sorted(mining.top1.items())
        ],
    }
    path = args.reports / f"{args.date}-ste-heads"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    path.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


def markdown(report: dict[str, Any]) -> str:
    holdout = report["holdout"]
    holdout_text = (
        f"Holdout #14 — `{holdout['path']}`: {holdout['ids']} ID, исключено "
        f"{holdout['excluded_rows']} строк."
        if holdout["found"]
        else f"Holdout #14: файла `{holdout['path']}` нет — исключать нечего."
    )
    p = report["parameters"]
    lines = [
        "# Головы наименований СТЕ и продуктовый поиск групп",
        "",
        f"Таблица для разметки — `{report['table']}`, {report['table_rows']} строк "
        f"(с заполненными `label`/`note`: {report['kept_labels']}).",
        "",
        "| Категория | Строк | Без головы | Голов | В таблице | Покрыто строк | Top-1 разный |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category, s in report["categories"].items():
        share = s["selected_rows"] / s["rows"] if s["rows"] else 0
        lines.append(
            f"| {category} | {s['rows']} | {s['no_head']} | {s['heads']} | {s['selected']} "
            f"| {s['selected_rows']} ({share:.0%}) | {s['top1_disagree']}/{s['selected']} |"
        )
    lines += [
        "",
        "«Строк» — без holdout; «Покрыто строк» — строки голов таблицы; «Top-1 разный» — головы, "
        "у примеров которых первая группа поиска не одна и та же.",
        "",
        holdout_text,
        "",
        f"Отбор голов: по убыванию частоты, пока не покрыто {p['coverage']:.0%} строк категории, "
        f"не больше {p['max_heads']} голов, не реже {p['min_count']} строк. Примеров на голову — "
        f"{p['examples']}, выбор детерминирован (seed {p['seed']}). Каждый пример — "
        f"`POST /api/v1/search`, limit {p['limit']}, без фильтра категории; векторизация "
        "документов запрещена, запросы векторизует реальный сервис.",
        "",
        f"Модель: `{report['model']}`, ревизия `{report['revision']}`. "
        f"База `{report['database']}`, SHA256 `{report['database_sha256']}`.",
        "",
        "Повторный запуск с теми же входами даёт ту же таблицу, кроме столбца `top5`: "
        "побитовая идентичность ответов GPU-сервиса не обещается. Top-1 по примерам — "
        "в соседнем JSON.",
        "",
    ]
    return "\n".join(lines)


def run_aliases(args: argparse.Namespace) -> None:
    rows = read_table(args.table)
    with database_copy(args.database) as copy:
        groups = product_groups(copy)
    plan = plan_aliases(rows, CsvAliasesSource(args.aliases).load(), groups)
    if plan.added:
        append_aliases(args.aliases, plan.added)
    labels = ", ".join(f"{k or 'пусто'} {plan.by_label[k]}" for k in (*LABELS, ""))
    print(f"Добавлено в {_relative(args.aliases)}: {len(plan.added)}")
    for alias in plan.added:
        print(f"  + {alias.alias} → {alias.group_code} ({alias.source})")
    print(f"Пропущено: {len(plan.skipped)}")
    for skipped in plan.skipped:
        print(f"  - {skipped.head}: {skipped.reason}")
    print(f"Пометки: {labels}")
    print(f"none — кандидаты «вне КТРУ» для #14: {len(plan.none)}")
    for row in plan.none:
        print(f"  {row.category}: {row.head} ({row.n_ste} СТЕ; {row.example_rows})")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    modes = parser.add_subparsers(dest="mode", required=True)

    table = modes.add_parser("table", help="таблица голов для разметки и отчёт")
    table.add_argument("--embeddings-url", required=True, help="базовый URL с /v1")
    table.add_argument("--model", default="qwen-embedding")
    table.add_argument("--database", type=Path, default=DATABASE)
    table.add_argument("--exports", type=Path, default=EXPORTS)
    table.add_argument("--holdout", type=Path, default=HOLDOUT)
    table.add_argument("--output", type=Path, default=TABLE)
    table.add_argument("--reports", type=Path, default=REPORTS)
    table.add_argument("--date", default=datetime.date.today().isoformat())
    table.add_argument("--coverage", type=float, default=0.9)
    table.add_argument("--max-heads", type=int, default=300)
    table.add_argument("--min-count", type=int, default=2)
    table.add_argument("--seed", type=int, default=38)
    table.set_defaults(run=run_table)

    aliases = modes.add_parser("aliases", help="строки словаря из размеченной таблицы")
    aliases.add_argument("--table", type=Path, default=TABLE)
    aliases.add_argument("--aliases", type=Path, default=ALIASES)
    aliases.add_argument("--database", type=Path, default=DATABASE)
    aliases.set_defaults(run=run_aliases)

    args = parser.parse_args(argv)
    args.run(args)


if __name__ == "__main__":
    main()
