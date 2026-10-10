"""Проверка каждой найденной группы через существующий decision-порт."""

from app.domain.catalog import Group
from app.domain.errors import ModelFailure
from app.domain.group_validation import GroupCheck, GroupPolicy
from app.domain.inference import ChoiceOption, ChoiceQuestion
from app.usecase.interface import DecisionBackend
from app.usecase.model_checks import CheckedDecisionBackend

OPTIONS = (
    ChoiceOption("supported", "Назначение товара соответствует группе"),
    ChoiceOption("contradicted", "Назначение товара противоречит группе"),
    ChoiceOption("not_stated", "Для определения соответствия недостаточно информации"),
)


def question(group: Group) -> ChoiceQuestion:
    p = group.position
    # Коды значений, повторяющиеся поля и null не помогают проверке назначения.
    # Передаём качественные поля первыми; ограниченный обзор явно помечен.
    fields: dict[str, list[str]] = {}
    for position in (p, *group.leaves):
        for c in sorted(position.characteristics, key=lambda c: c.quantitative):
            values = fields.setdefault(c.name, [])
            values.extend(v.label() for v in c.values if v.label() not in values)
    lines = []
    size = 0
    for name, values in fields.items():
        line = name + ": " + "; ".join(values[:6])
        if len(values) > 6:
            line += f" (показано 6 из {len(values)})"
        if size + len(line) > 3000:
            lines.append("Остальные характеристики опущены из обзора назначения")
            break
        lines.append(line)
        size += len(line)
    text = (
        "Проверь соответствие назначения товара группе КТРУ. Исходный текст и уточнения "
        "пользователя — в контексте в хронологическом порядке; позднее явное исправление "
        "назначения заменяет прежнее. Отсутствие характеристики не означает противоречия. "
        "Не выбирай группу только потому, что она похожа на запрос.\n"
        f"Группа/шаблон: {p.code}; {p.name}. Категория: {p.category}. "
        f"ОКПД2: {p.okpd2} {p.okpd2_name}. Рубрики: {', '.join(p.rubrics)}.\n"
        "Характеристики группы и конечных позиций: " + "\n".join(lines)
    )
    return ChoiceQuestion(f"group:{p.code}", text, OPTIONS)


def verify_groups(
    decision: DecisionBackend | None,
    context: str,
    groups: tuple[Group, ...],
    revision: int,
    policy: GroupPolicy,
) -> tuple[GroupCheck, ...]:
    if decision is None:
        raise ModelFailure("Для проверки назначения настройте DECISION_URL")
    questions = tuple(question(g) for g in groups)
    batch = CheckedDecisionBackend(decision).choose(context, questions)
    if not batch.revision:
        raise ModelFailure("Модель не сообщила ревизию проверки назначения")
    answers = {a.question_id: a for a in batch.answers}
    return tuple(
        GroupCheck(
            g.position.code,
            g.position.name,
            policy.verdict(
                answers[q.question_id].probabilities,
                answers[q.question_id].selected,
                answers[q.question_id].support_scores,
            ),
            answers[q.question_id].probabilities,
            answers[q.question_id].support_scores,
            batch.revision,
            q.text,
            revision,
        )
        for g, q in zip(groups, questions, strict=True)
    )
