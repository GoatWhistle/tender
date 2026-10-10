# Defense evidence: Карточка по КТРУ

Every claim on a slide, in the speech, in the video or in an answer has a row here. No row, no
claim. Product-level proofs (reports, test runs, measurements) live in `../docs/evidence.md`;
link to them instead of copying.

Statuses:

- **Live, 2026-10-10**: checked on the running dev stand (stub embedding and decision services, no
  extractor), commit `5711546` plus the uncommitted deck.
- **Code + tests**: implemented and covered by automated tests; no live run for this claim.
- **Not ready**: absent, or present but not accepted live.

Version: `5711546`. Stand: local dev stand from `../docs/running.md`.

## Claims

| # | Claim | Status | Proof | Slide | On the demo |
| ---: | --- | --- | --- | --- | --- |
| 1 | The cabinet description becomes a card with code `31.01.11.121-00000003` | Live, 2026-10-10 | `src/img/sell-*.png`, session `bf4a80c4` | 3, 4 | main scenario |
| 2 | The excluded position shows the catalog reason | Live, 2026-10-10 | `src/img/sell-position.png` | 4, 5 | step «Позиция КТРУ» |
| 3 | A code is issued only with exactly one position left | Code + tests | `test_indistinct_positions_are_ambiguous_in_catalog` | 3, 5, 9 | not shown |
| 4 | A missing value does not exclude a position | Code + tests | `test_dimensionless_rules_and_missing_characteristic` | 5 | not shown |
| 5 | Four error classes with quote and allowed values | Code + tests | `../evals/reports/2026-10-10-diagnostics-fixture.md` | 6 | not shown |
| 6 | Unconfirmed purpose leads to a question | Code + tests | `../backend/tests/test_group_validation.py` | 7 | «Перчатки» in `../docs/for-jury.md` |
| 7 | The type is extracted from text on the full stand | Not ready on the dev stand | needs the extractor on GPU | 4 (caveat) | not shown |

## Numbers

One row per `src/data/numbers.json` key.

| Key | Value | Population and runs | How measured | Source | Date |
| --- | --- | --- | --- | --- | --- |
| `catalog_positions` | 1967 | позиции КТРУ трёх категорий хакатона в актуальном XML | see source | `../docs/requirements-map.md` | 2026-10-10 |
| `ste_rows` | 299926 | строки выгрузок СТЕ организаторов | see source | `../README.md#зачем-это` | 2026-10-10 |
| `ste_rows_sample` | 42 | строк выгрузки СТЕ с группой в справочнике | see source | `../docs/evidence.md#как-часто-поиск-находит-правильную-группу` | 2026-10-10 |
| `example_positions` | 2 | позиции группы «Шкаф для одежды металлический», ручная проверка 2026-10-10 | see source | `../docs/evidence.md` | 2026-10-10 |
| `example_left` | 1 | позиция осталась после ответа «Шкаф» | see source | `../docs/evidence.md` | 2026-10-10 |
| `r5_smoke_hits` | 42 | R@5, smoke_v0, 46 описаний | see source | `../docs/evidence.md#как-часто-поиск-находит-правильную-группу` | 2026-10-10 |
| `r5_smoke_total` | 46 | описаний в smoke_v0 | see source | `../docs/evidence.md#как-часто-поиск-находит-правильную-группу` | 2026-10-10 |
| `r5_ste_hits` | 27 | R@5 на реальных СТЕ | see source | `../docs/evidence.md#как-часто-поиск-находит-правильную-группу` | 2026-10-10 |
| `code_correct` | 21 | верных кодов среди выданных, dev_v1 | see source | `../docs/evidence.md#насколько-верен-выданный-код` | 2026-10-10 |
| `code_issued` | 24 | выдано кодов на 60 сценариях dev_v1 | see source | `../docs/evidence.md#насколько-верен-выданный-код` | 2026-10-10 |
| `code_goal_pct` | 95 | цель точности кода из технического плана, раздел 15.3 | see source | `../docs/validation-plan.md` | 2026-10-10 |
| `wrong_autoselect` | 0 | ошибочных автовыборов группы | see source | `../docs/evidence.md#выбирает-ли-модель-группу-без-оснований` | 2026-10-10 |
| `autoselect_sample` | 10 | описаний столов, размечены вручную | see source | `../docs/evidence.md#выбирает-ли-модель-группу-без-оснований` | 2026-10-10 |
| `threshold` | 0.9 | порог OpenJev, зафиксирован до вызовов модели | see source | `../docs/evidence.md#выбирает-ли-модель-группу-без-оснований` | 2026-10-10 |
| `enum_correct` | 20 | верных среди автопринятых перечислимых значений, контрольная выборка v2 | see source | `../docs/evidence.md#верны-ли-автоматически-принятые-значения` | 2026-10-10 |
| `enum_auto` | 20 | автопринятых значений | see source | `../docs/evidence.md#верны-ли-автоматически-принятые-значения` | 2026-10-10 |
| `diag_found` | 12 | найдено ошибок, синтетические случаи, четыре класса | see source | `../evals/reports/2026-10-10-diagnostics-fixture.md` | 2026-10-10 |
| `diag_total` | 12 | положительных синтетических случаев | see source | `../evals/reports/2026-10-10-diagnostics-fixture.md` | 2026-10-10 |
| `diag_false` | 0 | ложных срабатываний на 12 контрольных случаях | see source | `../evals/reports/2026-10-10-diagnostics-fixture.md` | 2026-10-10 |
| `vram_used` | 37126 | три модели одновременно на A100, nvidia-smi | see source | `../docs/evidence.md#хватает-ли-40-гб-видеопамяти` | 2026-10-10 |
| `vram_total` | 40960 | лимит ТЗ 40 ГБ | see source | `../docs/evidence.md#хватает-ли-40-гб-видеопамяти` | 2026-10-10 |
| `backend_tests` | 405 | тестов бэкенда на коммите | see source | `../docs/running.md` | 2026-10-10 |

## Done, in progress, next

| Done, live | Done, tests only | In progress or not started |
| --- | --- | --- |
| Description to card, narrowing with reasons, questions, Portal design | Error classes, enum auto-accept, accessibility | Real STE names, code accuracy to 95 %, live supplier stream |

## Organizer memo requirements

| Requirement | Status | Where shown |
| --- | --- | --- |
| BPMN scheme of the implementation | In the deck | slide 9 |
| Demonstrate real cases in parallel | Live, 2026-10-10 | `demo-runbook.md` |

## Outdated or conflicting material

- None known.
