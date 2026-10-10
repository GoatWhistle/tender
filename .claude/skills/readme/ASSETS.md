# README assets

Everything visual in the README header is rendered by the browser from the product's own tokens,
fonts and mark, in light and dark variants that GitHub switches by theme. No shields.io, no
hand-made images.

| Source | What it defines |
| --- | --- |
| `presentation/readme/readme.json` | Buttons, status badges, stack badges, navigation badges: texts, links, tones |
| `presentation/readme/assets.html` | The banner (mark, wordmark, promise), the footer mark, the styles of buttons and badges, the icon set |
| `presentation/src/shell.html` | The mark (`brand-mark` template), shared with the deck |
| `frontend` tokens via `npm run tokens:export` | Colors, fonts, radii |

`cd presentation && npm run readme` renders `docs/readme/*.{light,dark}.png` at 2x, deletes images
of buttons and badges that no longer exist, rewrites the rows between the markers in `README.md`,
sets exact `width`/`height` on every image and colors every mermaid block with the tokens.
`npm run readme:preview` shows the header as GitHub renders it, in both themes, in `shots/`.

## readme.json

```json
{
  "buttons": [{ "name": "live", "label": "Открыть стенд", "icon": "external-link", "href": "https://…", "primary": true }],
  "status": [{ "label": "M1", "value": "0,87 на 1 200", "href": "#результаты", "tone": "accent" }],
  "stack": [{ "label": "API", "value": "FastAPI" }],
  "nav": [{ "value": "Ограничения", "href": "#ограничения", "tone": "warning" }]
}
```

| Row | Default content | Rule |
| --- | --- | --- |
| `buttons` | Открыть стенд (primary), Запустить локально, Документация | Three at most; drop one whose target does not exist |
| `status` | Key metric (accent), офлайн без ключей, тесты, интерфейс RU и EN, лицензия | Facts with a source one click away; a number equals «Результаты» and `docs/evidence.md` |
| `stack` | Фронтенд, API, хранилище, модель, запуск | Only what is in the code; 4–7 badges |
| `nav` | One badge per `##` section, Ограничения in the warning tone | The `href` equals the GitHub slug of the heading |

Icons for buttons: `external-link`, `terminal`, `book-open`, `play`, `file-text` in `#icons` of
`assets.html`; add a lucide path there for a new one. Tones: `accent` (filled value), `warning`
(warning text), none (neutral).

## Markers in README.md

```html
<!-- readme:buttons --> … <!-- /readme:buttons -->
<!-- readme:status --> … <!-- /readme:status -->
<!-- readme:stack --> … <!-- /readme:stack -->
<!-- readme:nav --> … <!-- /readme:nav -->
```

Everything between a pair is regenerated; edit `readme.json`, never the rows. Each group sits in its own
`<p align="center">`, so status, stack and navigation are visibly separate. The generator breaks a
group into balanced lines with `<br>` (at most 660 px per line, the README column on a laptop with
the sidebar), so GitHub never wraps a lone badge onto its own line. `npm run readme:preview`
renders that 700 px column.

## Text centering

Badge and button text is optically centered: the text box is trimmed to cap height and baseline
(`text-box: trim-both cap alphabetic`), and a badge whose text has no capitals or tall letters is
moved up by half the difference, the same shift for label and value so they share a baseline.
Descenders hang below, as in any typeset label. Do not center with `line-height` or padding tweaks.

## Anchors

A navigation badge links to the GitHub slug of its heading: lower case, punctuation dropped except
`-` and `_`, spaces become `-`, Cyrillic kept. «Попробовать за две минуты» →
`#попробовать-за-две-минуты`. Rename a heading and its `nav` entry in the same edit.

## Rules

- Short texts; the `alt` repeats the text of the image in plain words (generated from the JSON).
- One accent, from the tokens. No gradients, glows, emoji, arrow or check characters.
- No em dashes or middle dots inside badges.
