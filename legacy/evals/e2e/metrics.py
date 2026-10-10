"""Метрики сквозного замера по строкам прогона (только stdlib).

Строка — словарь, который собирает `run.py` из ответов API продукта:

- `id`, `set` (`dev` / `holdout`), `category`, `tags`;
- `gold_groups`, `gold_codes` — разметка; пустые `gold_groups` — «вне КТРУ»;
- `gold_facts`, `facts` — ключи фактов `[характеристика, значение]` в общей нормализации;
- `search` — коды групп из `POST /api/v1/search` по порядку;
- `status`, `group`, `compatible` — из `SessionState`: статус, выбранная группа, коды
  неисключённых позиций.

Пустой знаменатель — `None`, не 100%. Метрику, которую продукт ещё не поддерживает, вызывающий
помечает пропущенной, а не нулевой.
"""

from collections import Counter
from typing import Any

KS = (1, 5, 10)


def ratio(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "n": numerator,
        "of": denominator,
        "share": numerator / denominator if denominator else None,
    }


def positive(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["gold_groups"]]


def recall(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """R@K групп: правильная группа среди первых K результатов поиска."""
    rows = positive(rows)
    return {
        f"R@{k}": ratio(
            sum(bool(set(r["search"][:k]) & set(r["gold_groups"])) for r in rows),
            len(rows),
        )
        for k in KS
    }


def out_of_scope(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Товар вне КТРУ распознан: статус `out_of_scope` у кейсов без групп."""
    rows = [r for r in rows if not r["gold_groups"]]
    return ratio(sum(r["status"] == "out_of_scope" for r in rows), len(rows))


def codes(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Точность среди всех выданных кодов и доля выдачи среди всех кейсов.

    Выдача кода товару вне КТРУ — ошибка и входит в знаменатель точности.
    """
    issued = [r for r in rows if r["status"] == "resolved"]
    correct = sum(
        len(r["compatible"]) == 1 and r["compatible"][0] in r["gold_codes"]
        for r in issued
    )
    return {
        "accuracy": ratio(correct, len(issued)),
        "coverage": ratio(len(issued), len(rows)),
    }


def gold_kept(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Выбрана правильная группа и хотя бы один правильный код не исключён."""
    rows = positive(rows)
    kept = sum(
        r["group"] in r["gold_groups"]
        and bool(set(r["compatible"]) & set(r["gold_codes"]))
        for r in rows
    )
    return ratio(kept, len(rows))


def ambiguity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Неоднозначность сохранена: все допустимые коды остались, код не выдан."""
    rows = [r for r in positive(rows) if len(r["gold_codes"]) > 1]
    kept = sum(
        r["group"] in r["gold_groups"]
        and set(r["gold_codes"]) <= set(r["compatible"])
        and r["status"] != "resolved"
        for r in rows
    )
    return ratio(kept, len(rows))


def facts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Точность и полнота принятых фактов по ключу «характеристика + нормализованное значение»."""
    tp = fp = fn = 0
    for r in rows:
        gold = Counter(tuple(f) for f in r["gold_facts"])
        got = Counter(tuple(f) for f in r["facts"])
        tp += sum((gold & got).values())
        fp += sum((got - gold).values())
        fn += sum((gold - got).values())
    return {"precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn)}


def statuses(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(r["status"] for r in rows).items()))


def by_tag(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """По тегу кейса: R@1 и сохранён ли правильный код — где именно продукт проседает."""
    result = {}
    for tag in sorted({t for r in rows for t in r["tags"]}):
        tagged = [r for r in rows if tag in r["tags"]]
        result[tag] = {
            "cases": len(tagged),
            "R@1": recall(tagged)["R@1"],
            "gold_kept": gold_kept(tagged),
        }
    return result


def summarize(
    rows: list[dict[str, Any]], *, supports_out_of_scope: bool = False
) -> dict[str, Any]:
    """Отказ от классификации пока отсутствует в сценарии сессии.

    После его реализации вызывающий явно включает метрику; отсутствие найденных
    отказов само по себе не позволяет отличить неподдержанный сценарий от нулевого качества.
    """
    dev = [r for r in rows if r["set"] == "dev"]
    holdout = [r for r in rows if r["set"] == "holdout"]
    return {
        "dev": {
            "cases": len(dev),
            "recall": recall(dev),
            "out_of_scope": out_of_scope(dev) if supports_out_of_scope else "пропущено",
            "codes": codes(dev),
            "gold_kept": gold_kept(dev),
            "ambiguity": ambiguity(dev),
            "facts": facts(dev),
            "statuses": statuses(dev),
            "by_tag": by_tag(dev),
        },
        "holdout": {
            "cases": len(holdout),
            "recall": recall(holdout),
            "out_of_scope": out_of_scope(holdout)
            if supports_out_of_scope
            else "пропущено",
            "statuses": statuses(holdout),
        },
    }
