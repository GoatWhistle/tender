"""Markdown из сохранённого замера, без повторного обращения к модели."""

import argparse
import json
import math
from pathlib import Path


def wilson(correct: int, n: int) -> str:
    if not n:
        return "не определён (0 наблюдений)"
    p, z = correct / n, 1.959963984540054
    center = p + z * z / (2 * n)
    delta = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    denominator = 1 + z * z / n
    return f"{100 * (center - delta) / denominator:.1f}–{100 * (center + delta) / denominator:.1f}%"


def ratio(correct: int, total: int) -> str:
    return (
        f"{correct}/{total} ({100 * correct / total:.1f}%)"
        if total
        else "0/0 — не определено"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--vram", type=Path, required=True)
    parser.add_argument("--openjev-pid", type=str, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text())
    dev, held = data["dev_summary"], data["holdout_summary"]
    hashes = "\n".join(
        f"- `{name}`: `{digest}`." for name, digest in data["dataset_sha256"].items()
    )
    errors = "\n".join(
        f"- `{r['id']}`: gold `{r['gold']}`, результат `{[(p['field'], p['value']) for p in r['predictions']]}`."
        for r in data["holdout"]
        if not r["exact"]
    )
    calibration = "\n".join(
        f"| {r['threshold']} | {r['accepted']} | {ratio(r['correct_accepted'], r['accepted'])} |"
        for r in data["calibration"]
    )
    vram_text = args.vram.read_text().strip()
    vram = next(
        line
        for line in vram_text.splitlines()
        if line.startswith(args.openjev_pid + ",")
    )
    memory = int(vram.split(",")[-1].strip().split()[0])
    text = f"""# Enum-сопоставление: профиль автопринятия 0,90

**Автопринятие включено с порогом {data["selected_threshold"]:.2f}** для OpenJev 4B v5 ревизии
`{data["model_revision"]}` и алгоритма `{data["algorithm"]}`.
Это заранее выбранный продуктовый порог сырой оценки модели, **не гарантия 90% или 99%
правильных ответов**. Неоднозначные части товара, недопустимые сочетания, низкие оценки,
другая ревизия модели и повторные сообщения требуют подтверждения.

## Метод и данные

Разработка: 60 сценариев `dev_v1.json`, из них {dev["cases"]} с допустимой группой вошли в прогон;
3 случая вне КТРУ пропущены. Разметка используется для диагностики, выбора правил привязки и
сравнения порогов. Порог 0,90 зафиксирован до новой независимой проверки.

Новая контрольная выборка `enum_holdout_v2.json`: {held["cases"]} синтетических сценариев,
{held["gold_values"]} положительных пар «поле — значение», включая отрицания, отсутствие сведений,
множественность и части товара. Файл зафиксирован до первого прогона v2. Предыдущая выборка v1
после первого просмотра больше не считалась независимой для изменённого алгоритма.
Результаты v2 не использовались для настройки порога, запросов или правил привязки.
Независимость здесь — от настройки, **не независимая человеческая разметка и не случайная
выборка реального потока СТЕ**. `ste_holdout_v1.csv` размечен для поиска групп; он не доказывает
точность привязки всех enum-фактов.

SHA-256 входов:

{hashes}

Каждый сценарий проходит через HTTP API продукта и временную SQLite со схемой из миграций,
общую проводку `build_usecases` и реальный HTTP-адаптер OpenJev. Поиск заранее возвращает первую
допустимую группу из разметки: измеряется enum-сопоставление, а не качество поиска групп.
Числовые факты сужают позиции обычным парсером до построения вопросов. Пользовательские
подтверждения в метрики не подмешиваются.

Метрика — уникальная пара `(характеристика, значение)` в последней ревизии, с нормализацией
регистра и ё/е. Правильность включает привязку: при описании нескольких частей и только общем
поле «Материал» gold пуст. Исследовательский запуск использует `AutoAcceptance(0, revision)`
для регистрации всех допустимых по привязке кандидатов, после чего к сохранённым оценкам
применяется порог. Для множественного поля все его значения должны пройти порог совместно.
`model_score` — минимум оценки choice и NLI для одиночного поля, NLI для множественного.
Этот режим регистрации кандидатов не включается в production.

Привязка v2: в отдельном фрагменте сообщения явно названо поле/его содержательное слово либо
найдено лексически близкое значение, относящееся только к одному полю. Упоминание другой части
товара блокирует автопринятие. Сопоставление словоформ — эвристика с отсечением окончаний;
части товара — явный ограниченный словарь, не универсальный синтаксический анализатор.
При нескольких сообщениях автоматическое принятие откладывается, чтобы не принять старое
значение перед исправлением. Подтверждённые пользователем факты сохраняются.

## Пороги на разработке

| Порог | Автопринятые значения | Верные среди них |
| --- | ---: | ---: |
{calibration}

Выбран 0,90 как более частое автопринятие при сохранении проверки привязки. Проверка v2 ниже
выполнена после фиксации этого порога. Архив строгого профиля с нулевым автопокрытием —
`2026-10-10-enum-baseline.json` и `2026-10-10-enum-baseline.md`.

## Результаты итогового профиля

| Метрика | Разработка | Независимая от настройки проверка |
| --- | ---: | ---: |
| Сценарии | {dev["cases"]} | {held["cases"]} |
| Технические ошибки | {dev["technical_errors"]} | {held["technical_errors"]} |
| Полное совпадение enum-фактов | {ratio(dev["exact_cases"], dev["cases"])} | {ratio(held["exact_cases"], held["cases"])} |
| Верные конкретные сопоставления | {ratio(dev["correct_predictions"], dev["predictions"])} | {ratio(held["correct_predictions"], held["predictions"])} |
| Верные предложения / эталонные значения | {ratio(dev["correct_predictions"], dev["gold_values"])} | {ratio(held["correct_predictions"], held["gold_values"])} |
| Доля автопринятых среди предложений | {ratio(dev["accepted"], dev["predictions"])} | {ratio(held["accepted"], held["predictions"])} |
| Верные среди автопринятых | {ratio(dev["correct_accepted"], dev["accepted"])} | {ratio(held["correct_accepted"], held["accepted"])} |
| Время сценария p50 | {dev["latency_p50_seconds"]:.3f} с | {held["latency_p50_seconds"]:.3f} с |
| Время сценария p95 | {dev["latency_p95_seconds"]:.3f} с | {held["latency_p95_seconds"]:.3f} с |

Номинальный 95%-интервал Wilson точности автопринятых значений на контрольной выборке:
**{wilson(held["correct_accepted"], held["accepted"])}**. Для всех конкретных предложений:
**{wilson(held["correct_predictions"], held["predictions"])}**, для полного совпадения сценариев:
**{wilson(held["exact_cases"], held["cases"])}**. Интервалы описательные: значения одного сценария
связаны, выборка синтетическая. Они не доказывают качество в реальном потоке.

Цель 99% из строгого профиля **не подтверждена**. Даже при независимых одинаково распределённых
наблюдениях и нуле ошибок для односторонней точной нижней границы 95% ≥99% нужно минимум
299 принятых значений (`0.05 ** (1/n)`). Текущее включение — продуктовый компромисс в пользу
частоты принятия. Для статистической гарантии нужна отдельная репрезентативная выборка
достаточного размера после фиксации алгоритма и порога. Минимальное покрытие не задаётся.

Несовпадения контрольной выборки (сохранены без настройки по ним):

{errors or "Полных несовпадений нет."}

## Стенд, задержка и VRAM

OpenJev 4B v5, CUDA, bfloat16, SDPA, FLA-only; GPU и память — в снимке ниже. Локальный HTTP-туннель,
один последовательный прогон, обычный включённый кэш контекста сервиса, без сброса и отдельного
прогрева. p50/p95 включают обработку сообщения, HTTP, модель и SQLite; подготовка базы и
загрузка каталога не включены. Стенд общий, это не замер холодного старта или SLA.

Снимок `nvidia-smi` во время прогона (не пик и не прирост относительно idle):

```text
{vram_text}
```

OpenJev, PID {args.openjev_pid}: **{memory} MiB ({memory / 1024:.2f} GiB)**.
Общая занятость GPU включает другие процессы; приписывать её одному OpenJev нельзя.
Запрос только считывал показатели, настройки стенда не менялись.

## Воспроизведение

Из корня репозитория после `cd backend && uv sync`, с работающим OpenJev и справочником КТРУ:

```bash
backend/.venv/bin/python evals/enum/run.py --url http://127.0.0.1:18080 --threshold 0.90 --holdout evals/datasets/enum_holdout_v2.json --out var/enum-mapping.json
python3 evals/enum/report.py var/enum-mapping.json --vram evals/reports/2026-10-10-enum-vram.txt --openjev-pid {args.openjev_pid} --out var/enum-mapping.md
```

Для нового GPU-прогона снимок VRAM и PID нужно обновить. Формат снимка: `date -u`, затем
`nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader` и
`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader`.
Сырые результаты — `{args.input.name}`. Настройки и API — `docs/sessions.md`.
Отключение автопринятия: `DECISION_AUTO_ACCEPT_ENABLED=false`; другой порог задаётся
`DECISION_AUTO_ACCEPT_THRESHOLD`, ожидаемая ревизия — `DECISION_REVISION`.
"""
    args.out.write_text(text)


if __name__ == "__main__":
    main()
