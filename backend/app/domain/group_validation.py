"""Результат проверки назначения. Scores модели не являются калиброванной вероятностью."""

from dataclasses import dataclass

from app.domain.inference import Verdict


@dataclass(frozen=True)
class GroupCheck:
    code: str
    name: str
    verdict: Verdict
    scores: dict[str, float]
    support_scores: dict[str, float] | None
    model_revision: str
    # Контракт choice не возвращает объяснение; сохраняем проверенный критерий, не выдумываем его.
    criterion: str
    analysis_revision: int
    role: str = "group_template"


@dataclass(frozen=True)
class GroupPolicy:
    # Фиксируется до замера; применяется независимо к каждой группе, не к рангу среди групп.
    threshold: float = 0.90

    def verdict(
        self, scores: dict[str, float], selected: str | None, support: dict[str, float] | None
    ) -> Verdict:
        if support is None:
            return Verdict.not_stated
        if (
            selected == "supported"
            and scores["supported"] >= self.threshold
            and support["supported"] >= self.threshold
        ):
            return Verdict.supported
        if (
            selected == "contradicted"
            and scores["contradicted"] >= self.threshold
            and support["contradicted"] >= self.threshold
        ):
            return Verdict.contradicted
        return Verdict.not_stated

    def select(
        self, checks: tuple[GroupCheck, ...], clarified_code: str | None = None
    ) -> str | None:
        # Явный ответ пользователя снимает неоднозначность, но не заменяет проверку модели.
        if any(c.code == clarified_code and c.verdict == Verdict.supported for c in checks):
            return clarified_code
        possible = [c for c in checks if c.verdict != Verdict.contradicted]
        if len(possible) == 1 and possible[0].verdict == Verdict.supported:
            return possible[0].code
        return None
