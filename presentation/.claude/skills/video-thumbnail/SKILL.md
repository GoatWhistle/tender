---
name: video-thumbnail
description: Make the YouTube thumbnail and title for the demo or submission video in the product's design system — four 1280×720 variants (real screenshot with a zoomed detail, one big number, before and after, the mark with a hook) rendered from the product tokens, fonts and mark, checked at the sizes the feed shows them, plus 8–10 honest clickable title proposals with the top three picked. Use for a video preview, cover, thumbnail or the video's name — «превью для видео», «обложка видео», «превью для ютуба», «название для видео», «заголовок ролика», "thumbnail", "video cover", "YouTube title".
---

# Video thumbnail and title

The thumbnail and the title are one ad for the video. Most viewers see them at 168 to 360 pixels
wide next to a dozen others and decide in under a second. The thumbnail makes them look, the title
makes them click, and the video keeps the promise of both. A promise the video does not keep costs
more than the click: the judge stops trusting everything after it.

Sources: `thumbnail/thumbnail.html` (four layouts in the product tokens), `thumbnail/thumbnail.json`
(texts, screenshot, titles), `npm run thumbnail` (render, checks, feed preview).

## 1. Material

- The promise and the strongest result: the video script (`video/script.<lang>.md`, skill
  `video-script`), the deck plan, `evidence.md`. Every number on the thumbnail is in `evidence.md`.
- A real screenshot of the product at the moment of the result, 1920×1080 or larger, saved as
  `thumbnail/shot.png`. A frame from `npm run video:shots` or from the recording works. Never a
  mockup or a screen the product does not show.
- The product tokens, fonts and mark are already in the deck (`cd frontend && npm run tokens:export
  -- --fonts`).
- The video language: the thumbnail text and the titles use it.

## 2. What makes a thumbnail work at 168 px

- **One focal point.** One big thing the eye lands on: a word, a number, the zoomed detail. Three
  elements at most: the text, the visual, the mark.
- **Two to four words**, never the title repeated. The thumbnail says the emotion or the result,
  the title says what the video is.
- **Contrast before beauty.** Text at least 90 px at full size, the accent color on one word only,
  dark and light variants both readable on YouTube's white and dark feeds.
- **Real product, zoomed.** A screenshot is unreadable at feed size; the zoom circle on the one
  value that matters is what reads.
- **Tension.** Before and after, a crossed-out old number, a refusal, a surprising result. A
  question the title answers.
- **A human face with a clear emotion** raises clicks. Use it only when the team provides a cut-out
  photo; never a stock face.
- **Bottom right stays empty**: YouTube puts the duration label there. The check warns.
- **The same look as the product**: tokens, fonts, radii and mark exported from the site (`npm run
  thumbnail` fails when a token differs from the site), so the stand, the deck, the README
  and the video read as one product. No gradients, glows, emoji, arrow or check characters, em
  dashes or middle dots; icons come from the `#icons` set.

## 3. The four layouts

| Layout | When | Fields in `thumbnail.json` |
| --- | --- | --- |
| `shot` | The product's screen is the story; the zoom shows the key value | `hook`, `accent`, `focus: {x, y, scale}` (point of the screenshot from 0 to 1, magnification) |
| `number` | One measured result carries the video | `value` (as short as "20 из 20"), `caption` (two or three words) |
| `versus` | The change is the story: time, cost, errors before and after | `before: {label, value}`, `after: {label, value}` |
| `mark` | Brand first: a series, a teaser, a channel with several videos | `hook`, `accent` |

Shared fields: `product`, `theme` (`dark` or `light`, per variant too), `shot`, `badge`
(`{icon, text}`, icons `play`, `radio`, `code`, `clock`, `shield-check`; empty text hides it).
`accent` is the part of the hook painted in the accent color. Text that does not fit shrinks to
60% of its size, then fails.

Fill all four, render, and pick by the feed preview, not by the full-size picture. A new layout is a
new `<template id="layout-…">` in `thumbnail.html` using the same tokens.

## 4. Titles

Write 8–10 titles into `titles` of `thumbnail.json`, best first. The first title is shown under each
variant in the preview, the others in turn.

Patterns, at least one of each that fits the evidence:

| Pattern | Russian | English |
| --- | --- | --- |
| Result first | «20 ошибок из 20: как мы ловим неверно услышанные лекарства» | "20 of 20 mishearings caught before they reach a prescription" |
| Question the video answers | «Почему распознавание речи путает морфин и гидроморфон» | "Why speech recognition confuses morphine and hydromorphone" |
| Before and after | «Было 2 часа, стало 40 секунд: проверка рецепта голосом» | "From 2 hours to 40 seconds: checking a prescription by voice" |
| Contrarian rule | «Голосовой агент, который не верит слову «да»» | "A voice agent that does not trust a yes" |
| How we built it | «Как мы проверяем каждое поле без доверия к модели» | "How we check every field without trusting the model" |
| Live demo | «Ридбэк за 5 минут: живой звонок и проверка рецепта» | "Readback in 5 minutes: a live call, end to end" |

Rules, checked by `npm run thumbnail`:

- At most 60 characters, so nothing is cut in search and suggestions; never over 100.
- The words people would search come first; the product name at the end or not at all, unless the
  platform demands it (hackathon name and track go where the rules say).
- Digits are welcome in titles; the number is the one in `evidence.md`.
- No caps-lock words, emoji, em dashes, middle dots, arrows or "!!!".
- Curiosity, never deception: every title is answered in the first minute of the video. No "шок",
  "вы не поверите", "this changes everything", no claims the video does not show.
- The title and the thumbnail complement each other: if the thumbnail says «2 часа» crossed out and «40 секунд», the
  title says what was checked, not the numbers again.

Pick three: for each, the thumbnail variant it pairs with and one sentence why. YouTube "Test &
compare" can test up to three thumbnails on one video; upload the three paired variants when the
channel has it.

## 5. Render and check

```bash
cd presentation && npm run thumbnail
```

Writes `thumbnail/out/<name>.jpg` (1280×720, under 2 MB) and `shots/thumbnail-preview.png`: every
variant at 360 and 168 px on white and dark feeds, with a duration label and a title, the way
YouTube shows it. It fails on text that does not fit or sits under the screenshot, an accent not in
the hook, em dashes, glyphs or emoji, titles over 100 characters, duplicate titles; it warns on
hooks over four words, titles over 60 characters, caps lock, placeholders and the duration corner.

Look at the preview at 168 px: if the hook is not readable there, it is too long or too thin.
Text on the thumbnail and the titles pass the `humanizer` skill.

## 6. Hand-off

Report the three picks (title, variant, why), the paths of the JPGs and the preview. The upload
itself is in `pitch-video`.

Done when `npm run thumbnail` has 0 errors and 0 placeholders, the preview was looked at, every
number is in `evidence.md`, and three title and thumbnail pairs are picked.
