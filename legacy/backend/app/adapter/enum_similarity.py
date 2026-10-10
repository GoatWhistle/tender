"""Полный поиск enum: Damerau–Левенштейн, без top-k для доказательства отсутствия."""

from collections.abc import Sequence

from app.domain.facts import normalized


class DamerauMatcher:
    def rank(self, value: str, allowed: Sequence[str]) -> tuple[tuple[str, int], ...]:
        return tuple(
            sorted(
                ((v, _distance(normalized(value), normalized(v))) for v in allowed),
                key=lambda pair: (pair[1], pair[0]),
            )
        )


def _distance(a: str, b: str) -> int:
    # Неограниченный Damerau–Levenshtein (включая повторные перестановки).
    ceiling = len(a) + len(b)
    d = [[0] * (len(b) + 2) for _ in range(len(a) + 2)]
    d[0][0] = ceiling
    for i in range(len(a) + 1):
        d[i + 1][0], d[i + 1][1] = ceiling, i
    for j in range(len(b) + 1):
        d[0][j + 1], d[1][j + 1] = ceiling, j
    last: dict[str, int] = {}
    for i, ca in enumerate(a, 1):
        match = 0
        for j, cb in enumerate(b, 1):
            i1, j1 = last.get(cb, 0), match
            cost = int(ca != cb)
            if cost == 0:
                match = j
            d[i + 1][j + 1] = min(
                d[i][j] + cost,
                d[i + 1][j] + 1,
                d[i][j + 1] + 1,
                d[i1][j1] + i - i1 - 1 + 1 + j - j1 - 1,
            )
        last[ca] = i
    return d[-1][-1]
