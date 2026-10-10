# Slide library

Layouts to build content slides from. The template's 12 slides in `src/slides/` are the default
deck; this folder holds the alternatives. Cover and final stay as in the template (skill
`deck-cover-final`); everything between them is picked here or built from the same blocks.

```bash
npm run library                          # dist/library.html (animated) + shots/library.png (sheet)
npm run slide:add -- hub 05-agents       # copies a layout into src/slides/05-agents, renames the id
```

Look at `shots/library.png` before choosing. Every layout is light, reads only `--deck-*` tokens,
animates every element and ends on a readable last step.

## Choosing

1. Write the slide card first (skill `pitch-deck`): one thesis, one visual, the number.
2. Pick the layout whose visual *is* that thesis. Two neighbouring slides never share a layout;
   a deck uses at least six different layouts across its ten content slides.
3. Nothing fits: build the slide from the blocks below, then, if it is good and generic, add it
   here as a new `NN-id` folder with placeholders, so the next hackathon has it.

## Catalog

| # | Layout | Use it for | Visual |
| --- | --- | --- | --- |
| 01 | `statement` | The thesis, a turning point, one claim the jury must remember | Huge sentence, proof line, source |
| 02 | `stats-visual` | Problem in numbers | Three stacked numbers, network around the object, root-cause callout |
| 03 | `three-cards` | Why today's ways fail | Three cards with icons, requirement callout |
| 04 | `journey` | One role's day and the point where it breaks | Stepper with a red break, cost card |
| 05 | `pipeline` | How data flows through the product | Five icon stages, fact chips |
| 06 | `two-tracks` | One engine, two scenarios | Two compact timelines with status badges |
| 07 | `flowchart` | Answer only after a check, otherwise a refusal | Node chain with a red refusal branch |
| 08 | `transform` | Messy input becomes structured data | Raw record, arrow, structured fields |
| 09 | `hub` | Multi-agent system, orchestrator | Core with four satellites |
| 10 | `boundary` | Closed loop, offline, on-prem | Dashed perimeter with components, side KPIs |
| 11 | `lanes` | Who does what: human, model, code | Swimlanes with steps |
| 12 | `cycle` | Iterative loop (hypothesis, action, observation, conclusion) | Circle with four stages, text column |
| 13 | `formula` | The math, step by step | Numbered formula rows, highlighted choice |
| 14 | `kpi-grid` | Results on the stand | 3 x 2 metric cards with sample notes |
| 15 | `kpi-bars` | How much data, from where | Three KPI cards, ranked distribution bars |
| 16 | `bars-table` | Classifier or source confidence | Labelled bars with values, live example card |
| 17 | `versus-bars` | Faster or cheaper by N times | Paired bars per task, big multiplier |
| 18 | `line-chart` | Forecast against fact over time | Line chart with zone and annotation, KPI row |
| 19 | `scatter` | Trade-off map, chosen option | Point cloud, violators, highlighted choice |
| 20 | `funnel-circles` | Selection: many options, few pass, one chosen | Shrinking circles, why cut, why chosen |
| 21 | `reasoning` | Recommendation with justification | Old to new value, reason card per change |
| 22 | `screenshot` | The real screen is the proof | Product screenshot with numbered pins, legend list |
| 23 | `chat` | Assistant or agent dialogue | Context card, user question, tool badges, answer |
| 24 | `before-after` | Same case today and with the product | Two cards, struck-out old number |
| 25 | `table` | Roles, inputs and outputs, any compact comparison | Table with a highlighted row, callout |
| 26 | `competitors` | Comparison with analogues | Criteria matrix with check, cross and minus icons |
| 27 | `matrix-2x2` | Positioning | Quadrant with analogues and our dot |
| 28 | `market` | Market size, who pays | Nested rings, three numbers with sources |
| 29 | `stack` | Technologies and why each | Two icon tables |
| 30 | `replaceable` | Ports and adapters, vendor independence | Port, current implementation, alternatives |
| 31 | `demo` | Live demo plan with plan B | Main scenario card, backup card |
| 32 | `evidence-levels` | What is proven where | Stand, tests, in progress columns |
| 33 | `team` | Team and roles | Four person cards |
| 34 | `roadmap` | From prototype to pilot | Four stages, current one highlighted |

## Blocks

Shared classes in `src/core/css/blocks.css`, already styled in the product tokens. A custom slide
uses them before writing its own CSS; its `style.css` only positions and sizes.

| Block | Classes |
| --- | --- |
| Content area | `.body` (below the title, above the callout), `.body.is-tall`, `.foot` (callout row) |
| Layout | `.grid.is-2 / is-3 / is-4 / is-split / is-split-r / is-rows-2`, `.stack`, `.stack.is-center` |
| Surfaces | `.card`, `.card.is-accent`, `.card.is-sunken`, `.eyebrow` |
| Numbers | `.kpi`, `.kpi-value`, `.kpi-label`, `.kpi-note`, `.kpi.is-accent`, `.kpi.is-lg`, `.strike` |
| Bars | `.meter`, `.meter-row` (`is-ours`, `is-danger`), `.meter-track`, `.meter-fill` with `--w` from 0 to 1 |
| Process | `.steps` (`--tile` sets the circle size), `.flow`, `.dg` + `.dg-node` (`--x`, `--y`, `--w`, `--anchor`) |
| Tables | `.tbl`, `.tbl-row` (`is-head`, `is-ours`), `--cols` for the grid |
| Marks | `.badge` (`is-accent`, `is-success`, `is-warning`, `is-danger`), `.tile` (`is-accent`, `is-danger`), `.n`, `.pin`, `.legend` |
| Lists | `.list`, `.list.is-icons` |
| Media | `.screen` (`is-empty` placeholder) with an `img` or `video` from `src/img/` |
| Charts | `svg.chart` with `.axis`, `.grid-line`, `.zone`, `.dot` (`is-accent`, `is-danger`), `text.is-strong` |
| Shared from `parts.css` | `.chips`, `.chip`, `.trace`, `.node`, `.ping`, `.runner`, `.limit`, `.proof` |

Icons: `<span class="ico" data-icon="name"></span>`, filled at runtime from `<template
id="deck-icons">` in `src/shell.html` (Lucide paths, ISC licence). Names: check, x, minus,
arrow-right, arrow-down, user, users, database, server, file, search, filter, sliders, shield,
lock, message, bot, cpu, layers, clock, zap, alert, target, trending, chart, refresh, globe, code,
play, monitor, flag, wallet, plug, eye, sparkle. A missing icon is added to the template with the
product's own path data (same set as the frontend `Icon`), never drawn as a glyph.

## Rules for every layout

- Light by default: the whole deck follows `<html data-theme>` in `src/shell.html`. No slide sets
  its own theme, no literal colors; the build fails on both.
- Motion classes from skill `deck-motion` on every element (`.a`, `.f`, `.s`, `.pop`, `.dr`,
  `.meter-fill` grows by itself); callouts appear on a key press (`data-s`).
- Placeholders stay in `{{…}}` until real text and numbers replace them; numbers on the final deck
  go through `data-num` (`npm run build:final` fails otherwise).
- Text is captions to the visual: title, at most about 25 words more, nothing under 20 px.
