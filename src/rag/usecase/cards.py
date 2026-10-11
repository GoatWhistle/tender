from rag.domain.catalog import Position, value_text
from rag.domain.search import Hit
from rag.domain.spec import Extra

KINDS = {
    "1": "неизменяемая",
    "2": "выбор одного значения",
    "3": "выбор нескольких значений",
}

MAX_CHARS = 12
MAX_VALUES = 8


def card(p: Position, chosen: dict[str, tuple[str, ...]], extras: list[Extra]) -> str:
    lines = [
        f"Позиция КТРУ: {p.code} {p.name}",
        f"ОКПД2: {p.okpd2} {p.okpd2_name}",
        "Характеристики КТРУ:",
    ]
    for c in p.characteristics:
        values = "; ".join(t for t in (value_text(v) for v in c.values) if t)
        picked = chosen.get(c.name)
        now = f"; выбрано: {'; '.join(picked)}" if picked else ""
        lines.append(f"- {c.name} ({KINDS.get(c.kind, c.kind)}): {values}{now}")
    if not p.characteristics:
        lines.append("- нет")
    if extras:
        lines.append("Уже добавлены заказчиком:")
        lines.extend(f"- {e.name}: {e.value} (обоснование: {e.reason})" for e in extras)
    return "\n".join(lines)


def candidate_card(n: int, hit: Hit) -> str:
    p = hit.position
    lines = [
        f"[{n}] {p.name}",
        f"ОКПД2: {p.okpd2} {p.okpd2_name}",
        f"вариантов в группе: {hit.siblings}",
    ]
    for c in p.characteristics[:MAX_CHARS]:
        values = [t for t in (value_text(v) for v in c.values[:MAX_VALUES]) if t]
        more = " …" if len(c.values) > MAX_VALUES else ""
        lines.append(f"- {c.name}: {'; '.join(values)}{more}")
    if len(p.characteristics) > MAX_CHARS:
        lines.append(f"- … ещё {len(p.characteristics) - MAX_CHARS} характеристик")
    return "\n".join(lines)
