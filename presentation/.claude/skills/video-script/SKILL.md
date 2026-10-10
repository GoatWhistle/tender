---
name: video-script
description: Write the script of a demo or submission video for this exact product, about 5 minutes, in Russian or English. Covers timecodes, exact screens, URLs, cursor paths and UI labels taken from the running site, overlay labels, and what to say and how to say it. Produces a separate plain-text voice-over with only the words to say plus captions, all checked by `npm run video:check` and walked on the live site by `npm run video:shots`. Use when the user needs a video script, voice-over or narration — «сценарий видео», «видео для сабмита», «что говорить в видео», «текст для озвучки», «закадровый текст», «демо-видео», "video script", "voice-over", "narration".
---

# Video script

A video is judged later, alone, often at 1.5× speed and sometimes muted. Nobody can ask a question,
so the video carries the claim, the proof and the limits on its own. The first 15 seconds decide
whether the judge keeps watching. The screen shows **what** happens, the voice says **why** it
matters; the voice never describes the screen.

The video tells the same story as the deck with the same numbers (`src/data/numbers.json`,
`evidence.md`). It never claims anything the deck does not. Recording, assembly and upload:
skill `pitch-video`. The words themselves: [SPEAKING.md](SPEAKING.md).

## Files

| File | Who writes it | What it is |
| --- | --- | --- |
| `video/script.<lang>.md` | the agent | The source: front matter, sections with timecodes, Screen, Overlay, Say |
| `video/voice-over.<lang>.md` | `video:check` | Only the words to say, by section with timecodes, for the speaker or TTS |
| `video/captions.<lang>.srt` | `video:check` | Captions timed at the script pace, to burn in or upload |
| `video/live-dialogue.<lang>.md` | the agent | Only when a part is interactive: exact inputs, expected answers, what to do when it goes differently |
| `shots/video/<lang>/NN.png` | `video:shots` | Storyboard: the live screen of each section |

Never edit the generated files by hand: change the script and run `video:check`.

## 1. Constraints

From `../context/PLATFORM.md`: maximum duration, language, whether a live run, a voice or the
team's faces are required, resolution, where it is uploaded. From `../context/requirements.md`: the
criteria and weights; the demo time follows them. Unknowns go to `../context/open-questions.md`.

Defaults when nothing is stated: 5:00, the language the user asked for, voice-over on screen
recording, no faces. With a hard limit the total stays at least 5 s under it.

## 2. Walk the site before writing a word

The script describes this product as it runs today, not as planned.

1. Open the stand in the video language (an EN video records the UI switched to EN) and theme.
2. List the screens from the router in `frontend/src/app/` and pick the ones the story needs.
3. For each screen write down: the exact URL, the starting state, the exact labels of everything
   the cursor touches (copy them from `frontend/src/shared/i18n/locales/<lang>/`), what appears
   after the action, and how long it really takes (stopwatch or the Network panel).
4. Pick the demo case: seeded synthetic data, one case that runs through the whole story, whose
   result is visible on one screen. The same case as the deck's end-to-end example.
5. Run the main path and the hard case once by hand. What fails is fixed or left out. Behaviour not
   yet seen on the stand is either cut or marked `[after: <condition>]` in Say; `--strict` fails
   until the mark is removed.

The product runs on its real backend and data (no mocks, root `AGENTS.md`). Nothing is staged for
the camera that the product does not do.

## 3. Structure

```bash
npm run video:init -- --lang ru --target 5:00 --limit 5:00
```

writes `video/script.ru.md` from `video/template.md` with these parts scaled to the target:

| # | Part | At 5:00 | Job |
| --- | --- | --- | --- |
| 0 | Teaser | 8 s | The strongest real moment, cut from the demo take; product sound or one short line |
| 1 | Title | 12 s | Name and promise in one sentence over the live home screen |
| 2 | Problem | 35 s | One person, one case, how it fails today, one sourced number |
| 3 | Rule | 30 s | The one idea that makes it work, as a rule a viewer could test |
| 4 | Demo: main path | 45 s | The case through the product in real time |
| 5 | Demo: result | 45 s | What changed on the same case, the number on screen |
| 6 | Demo: hard case | 35 s | Where a naive solution breaks and what the product does instead |
| 7 | Proof | 35 s | Measured result against the baseline, method, sample, the cost beside it |
| 8 | Under the hood | 25 s | What runs where, offline, replaceable parts; only if technology is judged |
| 9 | Limits and next | 15 s | The strongest limitation said plainly, the next step |
| 10 | Close | 15 s | Name, promise, address spoken and on screen |

Adapt it to the criteria: merge, drop or add parts (a mandatory team or business slot), keep the
order logic. Then `npm run video:check -- --retime` makes the timecodes contiguous again.

Rules that hold for any structure:

- The product is on screen within the first 20 s. No logo animation longer than 3 s, no team intro
  at the start.
- The demo parts take at least 40% of the runtime.
- One claim per demo scene. A scene is: action, visible result, why it matters.
- One failure path is shown on purpose: a refusal, a conflict, bad input. It earns trust.
- Proof comes after the demo, never before it; limits are said aloud before the close.
- The close has no thanks: name, promise, where to try it.

## 4. Screen and Overlay

```markdown
## 4. Demo: the main path, 1:25–2:10

**Screen:** `/requests/new`, empty form. Field «Номер договора», type "Д-2024/118", button
«Проверить». The verdict card slides in on the right; hold one second on it, zoom to the reason line.

**Overlay:** `live`, синтетические данные, 09.10.2026

**Say:**
> ...
```

- **Screen** starts with the path in backticks (`/path` or a full URL), then the starting state,
  the cursor path, what appears, where to hold or zoom. Anyone on the team can record it from this.
  Write it in the team's language.
- UI labels in «» are copied exactly; `video:shots` fails when a label is not on that page.
  Typed inputs go in "straight quotes".
- **Overlay** is the label burned into the frame, and it must match what the product really is:
  `live` for a real-time run, `replay` or `запись` for a recording, `синтетические данные` /
  `synthetic data` for generated data, `×2, real time 0:48` for sped-up footage, the recording date
  on demo parts. A synthesized replay is never called recorded, a recording is never called live.
- Small text is zoomed in assembly, not left unreadable; the cursor moves slowly and rests.

## 5. Say

Lines in `> ` blocks, one line per screen event, in the order the events happen: the editor aligns
the start of each line to its event, and each line becomes a caption group. A section may have two
Say blocks (before and after a live part); a silent section says why on the `**Say:**` line.
`[pause]` (or `[пауза]`) is a 1.5 s beat after a key result.

How to write the words, with examples in both languages: [SPEAKING.md](SPEAKING.md); for beats,
word budgets and de-slopping a stiff draft, `pitch-craft`. The short
version: for the ear, one thought per sentence, numbers as spoken words, no reading the screen, no
"как вы видите", no thanks at the end.

Interactive parts (voice, chat, typing) get `video/live-dialogue.<lang>.md`: every input exactly as
said or typed, the expected answer, what to do if the product answers differently, a backup input
that works the same way, and which parts are cut in assembly.

## 6. Check

```bash
npm run video:check
npm run video:shots -- --site http://localhost:8080
```

`video:check` prints per section the slot, words and seconds needed at the script pace, and fails
on: broken or overlapping timecodes, a total over the limit, a section that does not fit its slot,
a missing Screen, em dashes, middle dots or glyphs in Say, opener, screen-narration and thanks
phrases from `src/locales/<lang>/video.json`, Cyrillic in an English script. It warns on digits,
addresses and long sentences in Say, fillers and hype words, placeholders, a section filled above
90%. `--strict` turns placeholders and `[after:]` marks into errors. It always rewrites
`voice-over.<lang>.md` and `captions.<lang>.srt`.

`video:shots` opens every section's path on the running site in the script language and theme at
1920×1080, checks the status and every «label», and saves the storyboard. Look at it: each picture
must match its Say.

Then:

1. Read two sections aloud with a stopwatch. If the real pace differs from `wpm` in the front
   matter by more than 10%, set the real one and run the check again.
2. Pass the Say text through the `humanizer` skill.
3. Every number equals `evidence.md`; every claim is visible on screen at the moment it is said.

## 7. Two languages

Two scripts, `script.ru.md` and `script.en.md`, same sections and screens, each recorded with the UI
in its own language. Translate the meaning, not the words, then re-fit: English runs faster in
words per minute but takes more words for the same idea. Never mix languages in one Say line;
English product terms in a Russian script only where the UI shows them.

## 8. Hand-off

Report in one message: the total against the limit, the sections with their timecodes, open
`{{placeholders}}` and `[after:]` marks with what closes them, and where the files are. Recording
and assembly continue in `pitch-video`.

Done when `npm run video:check -- --strict` passes, `video:shots` passes on the stand, the
storyboard was looked at, and the voice-over was read aloud once within the slots.
