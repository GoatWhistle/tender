---
name: readme
description: Write or upgrade the root README.md — a working README while building, the product README at submission — with visuals rendered in the product's own design system (banner, buttons, key numbers, stack, mermaid colors), one mention of each doc where it is needed, and honesty checks. Use when creating, filling or rewriting README.md, its banner, buttons or hero screenshot, or the user says "README", "ридми", "оформи README", "витрина репо".
---

# README

The README is the product's front page: a judge decides in two minutes whether the promise is real.
It looks like the product (same fonts, colors, radii, logo) and says each thing once. The template is
the root `README.md`; every `{{…}}` placeholder carries its guidance. Language: Russian for a Russian
jury, English for an international one; headings, anchors and asset texts are translated together.

## Structure

| Block | Content | Rule |
| --- | --- | --- |
| Banner | Rendered lockup and promise, `docs/readme/banner.*.png` | Alt text says the product name and the promise |
| One line | Who the user is and what changes for them | Never repeats the banner promise |
| Buttons | Rendered: Открыть стенд (primary), Запустить локально, Документация | Three at most; drop one whose target does not exist |
| Status badges | Rendered: the key metric (accent), офлайн без ключей, тесты, интерфейс RU и EN, лицензия | Facts with a source one click away; numbers equal «Результаты» |
| Stack badges | Rendered: фронтенд, API, хранилище, модель, запуск | Only what is in the code |
| Navigation badges | Rendered: one per `##` section, Ограничения in the warning tone | Anchors equal the heading slugs |
| Hero | One real screenshot, `width="880"`, `<sub>` caption about the run | Rules in `docs/images/README.md` |
| Main rule | `> **Rule.**` plus how code enforces it | Falsifiable: a reader could catch it broken |
| Зачем это | The case where today's way breaks, one sourced number, the change on the same example, the name origin | Problem before product |
| Как это работает | `flowchart LR` up to ~8 nodes including the refusal path, then three mechanisms in a 3-column table, each with how it is checked | Mechanisms, not features |
| Попробовать за две минуты | Stand, demo account, 3 steps: Что сделать, Что увидите | The first steps of `docs/for-jury.md`; the proof column lives there |
| Результаты | Method in one phrase, Метрика, Продукт, База, Порог, «Где проигрываем», reproduce command in `<details>` | Values copied from the report the command writes |
| Запуск | Two commands, the two addresses, dev, checks and variables in `<details>` | Works with no `.env` and no network |
| Устройство | Two sentences, a table of the docs not linked above | Only pages that exist |
| Ограничения | Three strongest, bold lead, numbers, link to `docs/limitations.md` | Never empty, same as the limitations page |
| Team block | Inside `<!-- scrub:start -->` … `<!-- scrub:end -->` | Removed at submission |
| Footer | Rendered mark, `<sub>Команда {{TEAM}}, {{HACKATHON}}, {{YEAR}}.</sub>` | Add licence attributions when a model licence requires them |

Each doc is linked once, where the reader needs it: evidence in «Зачем это», the jury route and the
requirements map in «Попробовать», the validation plan in «Результаты», running in «Запуск», the rest
in the «Устройство» table, limitations in «Ограничения». Internal pages (design decisions, audits,
screen specs) are never linked: they are removed before the defense.

## Visuals in the product's design system

No shields.io badges and no hand-made images. The visuals are rendered from
`presentation/readme/assets.html` with the product tokens, fonts and mark, in light and dark
variants that GitHub switches by theme: [ASSETS.md](ASSETS.md).

1. `cd frontend && npm run tokens:export -- --fonts` (tokens and fonts into the deck).
2. Edit `presentation/readme/readme.json` (buttons, status, stack and navigation badges) and the
   promise in `presentation/readme/assets.html`.
3. `cd presentation && npm run readme`: renders `docs/readme/*.{light,dark}.png` at 2x, rebuilds the
   rows between the `<!-- readme:… -->` markers, sets exact image sizes, colors every mermaid block.
4. `cd presentation && npm run readme:preview`: look at `shots/readme-light.png` and
   `shots/readme-dark.png` before committing.

## Honesty rules

- A number exists only with its command or source one click away. Unmeasured is not claimed.
- "стенд" means walked on the running stand; code with tests is "код". Never round one up.
- Describe the product as it is now: no development story, no "сначала", "после аудита".
- No marketing words: уникальный, инновационный, мощный, революционный, высокая точность,
  масштабируется, «Добро пожаловать»; no emoji. Name the mechanism or the number instead.
- The team is the author. No agent or AI-tool names anywhere outside the scrub block.
- No links into `context/`, `.claude/`, any `AGENTS.md`/`CLAUDE.md`, issues or PRs.

## Phase 1: working README (kickoff → T − 8h)

Fill only what is true on `main` today. Banner and buttons once the name and the stand exist; «Запуск»
with commands that work from a fresh clone; «Ограничения» with the known gaps. Update in the same PR
whenever commands, ports, the promise or a limitation change.

## Phase 2: product README (T − 8h, before `submission`)

Finish `docs/for-jury.md`, `docs/requirements-map.md`, `docs/evidence.md`, `docs/limitations.md`
first (`jury-route`, `docs-writing`); the README condenses them and never says more. Fill the blocks
top to bottom, render the visuals, take the hero shot, then run the final check. Delete a block
rather than leave it hollow, together with its button.

## Final check

1. `grep -rn "{{" README.md docs/ presentation/readme/` prints nothing.
2. `node .claude/skills/docs-writing/check-links.mjs README.md docs` prints nothing.
3. `cd presentation && npm run readme` was run after the last change of tokens, texts or numbers;
   the strip numbers equal «Результаты» and `docs/evidence.md`.
4. GitHub preview of the branch in light and dark themes: banner, buttons and mermaid switch with the
   theme and read well, `<details>` open, tables fit.
5. The two-minute steps pass on the live stand and match the start of `docs/for-jury.md`.
6. The `humanizer` skill pass over the prose; nothing outside the scrub block mentions agents.
