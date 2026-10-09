"""Мок-данные витрины: позиции КТРУ из var/ktru.json и названия СТЕ из var/ste_samples.json.

Запуск из корня репозитория (после `backend/build_var.py`):
    uvx python -I frontend/scripts/build_mock.py var frontend/mock-api/fixtures.json

Значения характеристик товаров выбираются из допустимых значений позиции, поэтому витрина
показывает уже унифицированные карточки. Цены, поставщики и пропуски полей — выдуманные,
детерминированно от seed.
"""

import json
import random
import re
import sys
from pathlib import Path

PER_CATEGORY = 9  # позиций КТРУ на категорию
PER_POSITION = 9  # товаров на позицию
SUPPLIERS = [
    "ООО «Техснаб»",
    "АО «Мосмебельторг»",
    "ООО «Профинструмент»",
    "ИП Гарипов Р. Р.",
    "ООО «Спецодежда-Центр»",
    "ООО «Казаньснаб»",
    "АО «Промресурс»",
    "ООО «Офис-Комплект»",
]


def stem(word: str) -> str:
    w = word.lower()
    return w[: max(5, len(w) - 2)]


def first_word(name: str) -> str:
    m = re.search(r"[А-Яа-яЁё]{4,}", name)
    return m.group(0) if m else ""


def fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def pick_value(rng: random.Random, ch: dict) -> dict | None:
    values = ch["values"]
    if not values:
        return None
    v = rng.choice(values)
    if v["text"] is not None:
        return {"value_code": v["code"], "label": v["text"], "unit": None, "number": None}
    if v["concrete"] is not None:
        x = v["concrete"]
    else:
        lo = v["min"] if v["min"] is not None else (v["max"] or 10) / 2
        hi = v["max"] if v["max"] is not None else lo * 2 + 10
        x = round(rng.uniform(lo, lo + (hi - lo) * 0.4), 0 if hi - lo > 5 else 1)
    unit = v["unit"]
    return {
        "value_code": v["code"],
        "label": f"{fmt(x)} {unit}" if unit else fmt(x),
        "unit": unit,
        "number": x,
    }


def main(var: Path, out: Path) -> None:
    rng = random.Random(20261009)
    positions = json.loads((var / "ktru.json").read_text())
    ste = json.loads((var / "ste_samples.json").read_text())

    chosen, products = [], []
    used: set[str] = set()
    for category, names in ste.items():
        names = list(dict.fromkeys(n.strip() for n in names if n.strip()))
        scored = []
        for p in positions:
            if p["category"] != category or p["is_template"] or len(p["characteristics"]) < 3:
                continue
            key = stem(first_word(p["name"]))
            if not key:
                continue
            rest = [stem(w) for w in re.findall(r"[А-Яа-яЁё]{4,}", p["name"])[1:]]
            matched = [
                n
                for n in names
                if key in n.lower()
                and n not in used
                and (not rest or any(r in n.lower() for r in rest))
            ]
            if len(matched) >= 3:
                scored.append((len(matched), p, matched))
        scored.sort(key=lambda t: -t[0])
        seen_names: set[str] = set()
        taken = 0
        for _, p, matched in scored:
            if taken == PER_CATEGORY or p["name"] in seen_names:
                continue
            seen_names.add(p["name"])
            matched = [n for n in matched if n not in used][:PER_POSITION]
            if len(matched) < 3:
                continue
            used.update(matched)
            taken += 1
            chosen.append(p)
            for title in matched:
                values = {}
                for ch in p["characteristics"]:
                    if not ch["required"] and rng.random() < 0.3:
                        continue
                    if v := pick_value(rng, ch):
                        values[ch["code"]] = v
                price = rng.choice([1, 1, 2, 5, 10]) * rng.randint(180, 4800)
                products.append(
                    {
                        "id": f"ste-{len(products) + 1:04d}",
                        "title": re.sub(r"\s+", " ", title),
                        "position_code": p["code"],
                        "category": category,
                        "price": price,
                        "offers": rng.randint(1, 14),
                        "supplier": rng.choice(SUPPLIERS),
                        "values": values,
                    }
                )

    slim = [
        {k: p[k] for k in ("code", "name", "category", "okpd2", "okpd2_name", "units")}
        | {
            "characteristics": [
                {k: c[k] for k in ("code", "name", "quantitative", "required", "multi")}
                | {
                    "values": [
                        {"code": v["code"], "label": v["text"] or label(v), "unit": v["unit"]}
                        for v in c["values"]
                    ]
                }
                for c in p["characteristics"]
            ]
        }
        for p in chosen
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"positions": slim, "products": products}, ensure_ascii=False, indent=1) + "\n"
    )
    print(f"{len(slim)} позиций, {len(products)} товаров → {out}")


def label(v: dict) -> str:
    u = f" {v['unit']}" if v["unit"] else ""
    if v["concrete"] is not None:
        return f"{fmt(v['concrete'])}{u}"
    parts = []
    if v["min"] is not None:
        parts.append(("≥ " if v["min_op"] != "greater" else "> ") + fmt(v["min"]))
    if v["max"] is not None:
        parts.append(("≤ " if v["max_op"] != "less" else "< ") + fmt(v["max"]))
    return " и ".join(parts) + u


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
