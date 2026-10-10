# Demo runbook: Карточка по КТРУ

Not shown to the audience. Stage 1: the demo runs in parallel with the whole 5:00 talk; the operator
follows the speaker (`SPEECH.md`). Facts: [evidence.md](evidence.md). Run commands:
`../docs/running.md`.

Mode: live on our laptop. Version: `5711546`. Operator: second team member. Timer: a teammate who is
not speaking.

## Prep: 20 minutes before

1. [ ] Version fixed: `git rev-parse --short HEAD` matches, `git status --short` is empty.
2. [ ] Stand up per `../docs/running.md`: backend with models, `cd frontend && npm run dev`.
3. [ ] Health: `http://127.0.0.1:<backend port>/api/v1/sessions/drafts` returns 200.
4. [ ] Warm-up run of the main scenario: the cabinet reaches «Карточка заполнена».
5. [ ] Theme light, language RU, browser zoom 100%, clean profile, notifications off.
6. [ ] Nothing private on screen: no terminal, no `.env`, no tokens, no local paths, no extra tabs.
7. [ ] Backup recording open and paused; the deck PDF open in a background tab.
8. [ ] Network fallback: the stand is local, no network needed.

## Main scenario

| Time | Action | What is visible | What to say |
| --- | --- | --- | --- |
| 0:12 | Open `/sell` | Step 1 «Описание», examples | nothing, the speaker talks |
| 0:37 | Click the example «Шкаф для одежды металлический, глубина 0,55 м», then «Подобрать позицию» | Step «Позиция КТРУ», path «Мебель › Шкаф для одежды металлический» | — |
| 1:03 | Answer «Шкаф» if asked | «Подходит позиций: 1 из 2», the second position «Исключена» with the reason | — |
| 1:29 | «Продолжить», answer «Тип шкафа: Секционный» | «Заполнено обязательных: 2 из 2» | — |
| 1:57 | «Продолжить» | «Карточка заполнена», code `31.01.11.121-00000003` | — |
| 2:47 | «Новая карточка», type «Перчатки», submit | Question «Для какого назначения нужен товар?» | — |
| 3:15 | Open `/catalog/mebel` | Catalog with KTRU filters in the Portal design | — |

If running late: skip the catalog; it is not in the speech.

## Plan B

| Situation | What we do | What we say |
| --- | --- | --- |
| The stand does not start | Play the backup recording «ЗАПИСЬ <дата>» | «Это запись репетиции, не живой прогон» |
| No network | nothing changes, the stand is local | — |
| A model service is down | the product shows «технический сбой»; switch to the recording | «Модель недоступна, показываем запись» |
| A different question appears | answer it, the narrowing still ends at one position | — |
| Laptop or projector fails | PDF from USB on the organizer laptop | «Покажем по слайдам» |

## Backup recording

- File: not recorded yet. Record the main scenario on the GPU stand with the label «ЗАПИСЬ <дата>» in the frame.
- [ ] Plays offline on the defense machine.

## Rehearsals

| # | Date | Kind | Result | Fixes |
| ---: | --- | --- | --- | --- |
| 1 | | Read-through, the operator clicks along | | |
| 2 | | Full run with timer and presenter window | | |
| 3 | | Demo switched off, plan B from the recording | | |

## Ready: 15 minutes before

- [ ] The main path checked once more by a second person.
- [ ] The deck open at slide 1 in fullscreen; presenter window on the second screen.
- [ ] Each speaker has only their own text and their questions open.
- [ ] The timer is started by a teammate who is not speaking.

## After the show

1. Record the version and what the jury saw: live or recording.
2. Save screenshots and exported results into `../artifacts/defense/<date>/`.
3. Every failure seen on stage becomes an `evidence.md` row with its date, and a `QA.md` answer if
   a juror noticed it.
