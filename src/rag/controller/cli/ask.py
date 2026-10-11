import json
from dataclasses import asdict

from rag.domain.catalog import FIXED, Position, value_text
from rag.domain.clarify import Question
from rag.domain.errors import InputError
from rag.domain.sessions import Session, Stage
from rag.domain.spec import Extra
from rag.usecase.sessions import Sessions


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


class Dialog:
    def __init__(self, sessions: Sessions) -> None:
        self._sessions = sessions

    async def add_extra(self, s: Session) -> None:
        name = input("название> ").strip()
        value = input("значение с единицей измерения> ").strip()
        reason = input("обоснование необходимости> ").strip()
        new = Extra(name, value, reason)
        while True:
            verdict, _ = await self._sessions.add_extra(s.id, new)
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
            if input(
                "  проверить предложенный вариант? (y/n)> "
            ).strip().lower() not in ("y", "д"):
                return
            new = verdict.fixed

    async def clarify(self, s: Session) -> Session:
        q = s.question
        assert q is not None
        reply = ask(q)
        if reply.isdigit() and int(reply) <= len(q.options):
            return await self._sessions.answer(s.id, int(reply), None)
        return await self._sessions.answer(s.id, None, reply)

    async def pick(self, s: Session) -> Session:
        print(f"\nосталось позиций: {len(s.leaves)}, различить нечем или ответов нет:")
        for n, p in enumerate(s.leaves, 1):
            print(f"  {n}. {p.code} {p.name}")
        reply = input("номер позиции> ").strip()
        if not (reply.isdigit() and 1 <= int(reply) <= len(s.leaves)):
            raise InputError("нет такого номера")
        return await self._sessions.pick(s.id, s.leaves[int(reply) - 1].code)

    async def spec(self, s: Session) -> bool:
        show_spec(s)
        qs = s.characteristics
        hint = "номер или текст — изменить" + (
            ", + — своя характеристика" if s.extras_allowed else ""
        )
        reply = input(f"{hint}, пусто — готово> ").strip()
        if not reply:
            outcome = await self._sessions.finish(s.id)
            print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))
            return True
        if reply == "+":
            await self.add_extra(s)
        elif reply.isdigit() and 1 <= int(reply) <= len(qs):
            q = qs[int(reply) - 1]
            value = ask(q, none="сбросить")
            if value == "0":
                await self._sessions.set_values(s.id, {q.name: []})
            elif (picked := numbers(value, q)) is not None:
                await self._sessions.set_values(s.id, {q.name: picked})
            else:
                await self._sessions.describe(s.id, value, q.name)
        elif reply.isdigit() and len(qs) < int(reply) <= len(qs) + len(s.extras):
            await self._sessions.remove_extra(s.id, int(reply) - len(qs) - 1)
        elif reply.isdigit():
            raise InputError("нет такого номера")
        else:
            await self._sessions.describe(s.id, reply, None)
        return False

    async def run(self, text: str) -> None:
        s = await self._sessions.start(text)
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
                    await self.clarify(s)
                elif s.stage == Stage.PICK:
                    await self.pick(s)
                else:
                    if not shown and s.position:
                        print("\nпозиция определена:")
                        show(s.position)
                        shown = True
                    if await self.spec(s):
                        return
            except InputError as e:
                print(f"  ! {e}")
                continue
            s = self._sessions.read(s.id)
            if s.message:
                print(f"  → {s.message}")
                s.message = None
        if s.stage == Stage.FAILED:
            print(s.message)
