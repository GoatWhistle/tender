# Deck plan: Карточка по КТРУ

Status: draft. Updated 2026-10-10.
Rules: [AGENTS.md](AGENTS.md). Proofs: [evidence.md](evidence.md).

## 1. Regulation

| Item | Value | Source |
| --- | --- | --- |
| Talk | 5:00 on stage 1, 7:00 on stage 2 (top 5) | `../docs/Презентация_Задачи_Хакатон_Казань_20261009_1900.md`, слайд 8 |
| Q&A | stage 2 only, up to 10:00 | same |
| Format | on site | same |
| Demo | in parallel: the second team member shows real cases while the speaker talks | same |
| Who switches slides | speaker | team decision |
| Screen | projector, 1920×1080 assumed | open question |
| Deck language | ru | task language |
| Mandatory content | BPMN scheme of the implementation | slide 8 of the memo |
| Deck file required by organizers | not stated; PDF from `npm run final` | open question |

The deck is built for the 5:00 slot. The 7:00 slot adds appendices, not new main slides.

## 2. Criteria and slides

| Criterion | Weight | Slides | Seconds | Proof shown on the slide |
| --- | ---: | --- | ---: | --- |
| Понимание проблематики | 7 | 2 | 25 | `catalog_positions`, `ste_rows`, the cabinet example |
| Функциональность и качество | 40 | 3, 4, 5, 7, 8 | 132 | real product screen, narrowing with reasons, `r5_*`, `code_*`, `wrong_autoselect` |
| Распознавание ошибок | 12 | 6 | 26 | real product diagnostics, `diag_*` |
| Интерфейс и оформление | 10 | 4, whole deck | 26 | product screen; the deck uses the product tokens and font |
| Техническая реализация и масштабируемость | 16 | 9, 10 | 52 | BPMN, `vram_*`, ports, scale limit |
| Презентация и защита | 15 | 1, 11, 12 | 36 | BPMN present, status, QR to the code |

## 3. End-to-end example

- **Input:** «Шкаф для одежды металлический, глубина 0,55 м», the first example in the product.
- **Product output:** group «Мебель › Шкаф для одежды металлический», 2 positions; after the
  answer «Шкаф» position `31.01.11.121-00000003`, the other one excluded with «вид товара: секция
  шкафа; указано шкаф»; card with «Вид товара», «Тип шкафа», «Глубина 0,55 м».
- **Checked by hand:** 2026-10-10 on the dev stand (stub models): the question about «Вид товара»
  appears because the extractor is not running; on the full stand the type is taken from the text
  (`../docs/evidence.md`).
- **On slides:** 2 the gap, 3 the trace, 4 the real screen, 5 the narrowing and the reason.
- **On the demo stand:** the same scenario, `../docs/for-jury.md` step 1.

## 4. Slide list

| # | id | Title (thesis) | Criterion | Time | Cumulative |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | cover | Описание своими словами становится карточкой, а код только при одной позиции | — | 0:12 | 0:12 |
| 2 | problem | Поставщик пишет своими словами, а Портал ждёт код и характеристики | Понимание | 0:25 | 0:37 |
| 3 | solution | Четыре шага до карточки, код только на последнем | Функциональность | 0:26 | 1:03 |
| 4 | product | Поставщик видит сужение позиций и причину каждого исключения | Функциональность, интерфейс | 0:26 | 1:29 |
| 5 | narrowing | Правила справочника сужают позиции до одной с объяснением | Функциональность | 0:28 | 1:57 |
| 6 | errors | Ошибка видна в ячейке рядом с допустимым | Ошибки | 0:26 | 2:23 |
| 7 | trust | Модель проверяет группу, при сомнении вопрос | Функциональность | 0:24 | 2:47 |
| 8 | measured | Что измерено и где проигрываем | Функциональность | 0:28 | 3:15 |
| 9 | bpmn | Процесс в BPMN, код выдаёт шлюз «одна позиция» | Техника, обязательный пункт | 0:28 | 3:43 |
| 10 | value | Выигрывают поставщик, заказчик и Портал | Понимание, бизнес | 0:26 | 3:57 |
| 11 | roadmap | От прототипа к пилоту в форме создания СТЕ | Защита, бизнес | 0:22 | 4:19 |
| 12 | final | Готовы к вашим вопросам, сквозной пример и QR | — | 0:08 | 4:27 |

Reserve: 0:33. No in-slide steps: one key press is always the next slide. Appendices for the 7:00 slot: none yet.

## 5. Slide cards

Speaker text lives in [SPEECH.md](SPEECH.md); cards keep what the speech does not.

| # | Key sentence | What to prove | TODO |
| ---: | --- | --- | --- |
| 2 | Код выбирается по характеристикам, которых в описании нет | `catalog_positions`, `ste_rows` | — |
| 3 | Код выдаёт правило, а не модель | `test_indistinct_positions_are_ambiguous_in_catalog` | — |
| 4 | Причина исключения видна словами справочника | `src/img/sell-position.png`, dev stand 2026-10-10 | `[HONEST]` dev stand asks the type, the full stand extracts it |
| 5 | Неизвестное не исключает позицию | `test_dimensionless_rules_and_missing_characteristic` | — |
| 6 | Ошибка показана с тем, что допустимо | `evals/reports/2026-10-10-diagnostics-fixture.jsonl` | `[HONEST]` synthetic cases only |
| 7 | При сомнении вопрос, а не догадка | `wrong_autoselect`, `autoselect_sample` | `[HONEST]` 10 descriptions, one group |
| 8 | На реальных строках СТЕ поиск слабее | `r5_*`, `code_*`, `enum_*` | `[HONEST]` code accuracy below the 95 % goal |
| 9 | Решения принимают шлюзы системы | the process in `../docs/architecture.md` | `[NEED TO CHECK]` a `.bpmn` file for the repository, if the jury asks for the source |
| 10 | Всем нужен один правильный код | `portal_items` (РГ, 08.10.2026) | `[HONEST]` time to fill a card not measured |

## 6. Organizer memo coverage

| Requirement (quote) | Where | Status |
| --- | --- | --- |
| «презентация до 5 минут со схемой реализации в нотации BPMN» | deck 4:31, slide 9 | done |
| «Параллельно второй участник команды демонстрирует реальные кейсы» | `demo-runbook.md`, slide 4 says it aloud | runbook to fill |
| «презентация до 7 минут … затем до 10 минут на вопросы жюри» | `QA.md` | to prepare if in top 5 |

## 7. Open markers

| Marker | Slide | What exactly | Owner | Due |
| --- | --- | --- | --- | --- |
| `[NEED TO CHECK]` | 9 | `.bpmn` source of the scheme in the repository | team | before stage 2 |
| — | 1, 12 | product name and logo are working ones: «Карточка по КТРУ» and the Portal mark | team | when the name is chosen |
| — | 12 | QR has the repository only; add the stand URL when there is one | team | before the defense |

## 8. Audit

Not run yet: skill `deck-audit` before the first rehearsal.
