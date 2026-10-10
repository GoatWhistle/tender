import asyncio
import json
import sys

from rag import session as ss
from rag.clarify import FIXED, Question
from rag.ktru import value_text
from rag.models import Position
from rag.search import Index
from rag.session import InputError, Session, Stage
from rag.spec import Extra


def ask(q: Question, none: str = "не знаю") -> str:
    mark = "обязательная" if q.required else "необязательная"
    many = ", можно несколько через запятую" if q.multiple else ""
    print(f"\n{q.name} ({mark}{many}):")
    for j, o in enumerate(q.options, 1):
        print(f"  {j}. {o}  [{q.counts[j - 1]}]" if q.counts else f"  {j}. {o}")
    print(f"  0. {none}")
    return input("номер или ответ текстом> ").strip()


def show(p: Position) -> None:
    print(f"{p.code} {p.name}")
    print(f"  ОКПД2 {p.okpd2} {p.okpd2_name}")
    for c in p.characteristics:
        values = "; ".join(t for t in (value_text(v) for v in c.values) if t)
        mark = "*" if c.required else "-"
        kind = "" if c.kind == FIXED else " (выбирает заказчик)"
        print(f"  {mark} {c.name}{kind}: {values}")


def numbers(reply: str, q: Question) -> list[str] | None:
    parts = reply.replace(",", " ").split()
    if not parts or not all(x.isdigit() for x in parts):
        return None
    if not all(1 <= int(x) <= len(q.options) for x in parts):
        raise InputError("нет таких номеров в списке")
    return list(dict.fromkeys(q.options[int(x) - 1] for x in parts))


def show_spec(s: Session) -> None:
    print("\nхарактеристики, которые выбирает заказчик:")
    qs = s.characteristics
    for n, q in enumerate(qs, 1):
        mark = "*" if q.required else "-"
        value = "; ".join(s.chosen[q.name]) if q.name in s.chosen else "— не выбрано"
        print(f"  {n:2}. {mark} {q.name}: {value}")
    for n, e in enumerate(s.extras, len(qs) + 1):
        print(f"  {n:2}. + {e.name}: {e.value} (обоснование: {e.reason})")


async def add_extra(s: Session) -> None:
    name = input("название> ").strip()
    value = input("значение с единицей измерения> ").strip()
    reason = input("обоснование необходимости> ").strip()
    new = Extra(name, value, reason)
    while True:
        verdict = await ss.add_extra(s, new)
        if verdict.ok:
            print("  добавлено")
            for warning in verdict.warnings:
                print(f"   ~ {warning}")
            return
        print("  отклонено:")
        for problem in verdict.problems:
            print(f"   - {problem}")
        if verdict.fixed is None:
            return
        print(f"  предложено: {verdict.fixed.name}: {verdict.fixed.value}")
        if input("  проверить предложенный вариант? (y/n)> ").strip().lower() not in ("y", "д"):
            return
        new = verdict.fixed


async def step_clarify(s: Session, index: Index) -> None:
    q = s.question
    reply = ask(q)
    if reply.isdigit() and int(reply) <= len(q.options):
        await ss.choose(s, index, int(reply) or None)
    else:
        await ss.reply(s, index, reply)


async def step_pick(s: Session, index: Index) -> None:
    print(f"\nосталось позиций: {len(s.leaves)}, различить нечем или ответов нет:")
    for n, p in enumerate(s.leaves, 1):
        print(f"  {n}. {p.code} {p.name}")
    reply = input("номер позиции> ").strip()
    if not (reply.isdigit() and 1 <= int(reply) <= len(s.leaves)):
        raise InputError("нет такого номера")
    await ss.pick(s, index, s.leaves[int(reply) - 1].code)


async def step_spec(s: Session) -> bool:
    show_spec(s)
    qs = s.characteristics
    hint = "номер или текст — изменить" + (", + — своя характеристика" if s.extras_allowed else "")
    reply = input(f"{hint}, пусто — готово> ").strip()
    if not reply:
        print(json.dumps(ss.finish(s), ensure_ascii=False, indent=2))
        return True
    if reply == "+":
        await add_extra(s)
    elif reply.isdigit() and 1 <= int(reply) <= len(qs):
        q = qs[int(reply) - 1]
        value = ask(q, none="сбросить")
        if value == "0":
            ss.set_values(s, {q.name: []})
        elif (picked := numbers(value, q)) is not None:
            ss.set_values(s, {q.name: picked})
        else:
            await ss.describe(s, value, q.name)
    elif reply.isdigit() and len(qs) < int(reply) <= len(qs) + len(s.extras):
        ss.remove_extra(s, int(reply) - len(qs) - 1)
    elif reply.isdigit():
        raise InputError("нет такого номера")
    else:
        await ss.describe(s, reply)
    return False


async def main(text: str) -> None:
    index = Index()
    s = await ss.start(index, text)
    if s.fixes:
        print(f"исправлено: {s.corrected}")
    for issue in s.issues:
        print(f"  ! {issue}")
    top = s.ranked[0]
    print(f"\nгруппа: {top.hit.position.name} ({top.relevance})")
    for rk in s.ranked[1:3]:
        print(f"  ещё: {rk.hit.position.name} ({rk.relevance})")
    for name, label in s.from_description.items():
        print(f"  из описания: {name} = {label}")
    shown = False
    while s.stage not in (Stage.DONE, Stage.FAILED):
        try:
            if s.stage == Stage.CLARIFY:
                await step_clarify(s, index)
            elif s.stage == Stage.PICK:
                await step_pick(s, index)
            else:
                if not shown:
                    print("\nпозиция определена:")
                    show(s.position)
                    shown = True
                if await step_spec(s):
                    return
        except InputError as e:
            print(f"  ! {e}")
            continue
        if s.message:
            print(f"  → {s.message}")
            s.message = None
    if s.stage == Stage.FAILED:
        print(s.message)


def run() -> None:
    asyncio.run(main(" ".join(sys.argv[1:]) or "струбцина винтовая"))
