---
language: {{lang}}
target: {{target}}
limit: {{limit}}
wpm: {{wpm}}
site: {{stand URL, the one the jury opens}}
theme: light
---

# {{PRODUCT}}: video script

Platform limits: `../context/PLATFORM.md`. Every number: `src/data/numbers.json` and `evidence.md`.
UI labels in «» are copied from `frontend/src/shared/i18n/locales/{{lang}}/` and checked on the live
page by `npm run video:shots`. Skill `video-script`.

## 0. Teaser [8]

**Screen:** {{the strongest real moment, cut from the recording of section 5: the result appearing on `/path`}}

**Overlay:** `{{live | replay | synthetic data}}`, {{recording date}}

**Say:** {{none, the product sound only; or one line of at most eight words}}

## 1. Title [12]

**Screen:** `{{/}}`, {{starting state; the cursor rests, nothing is clicked}}

**Overlay:** {{product name and the promise, in the product fonts and colors}}

**Say:**
> {{Name, then what it does for whom, in one sentence.}}

## 2. Problem [35]

**Screen:** `{{/path}}` or deck slide {{N}}, {{what the viewer looks at while the case is told}}

**Overlay:** {{the source of the number, small, bottom left}}

**Say:**
> {{One person, one concrete case, how it fails today.}}
> {{One number with its source, said as words.}}
> {{What that costs the person.}}

## 3. Rule [30]

**Screen:** `{{/path}}`, {{the screen or the deck diagram where the mechanism is visible}}

**Overlay:** {{none, or the rule in five words}}

**Say:**
> {{The one idea that makes the product work, as a rule a viewer could test.}}
> {{How the code enforces it, in plain words.}}

## 4. Demo: the main path [45]

**Screen:** `{{/path}}`, {{starting state}}. {{Cursor path: field «Label», type "exact input", button «Label»}}. {{What appears, where; hold one second on it.}}

**Overlay:** `{{live}}`, {{seeded synthetic data}}

**Say:**
> {{Why the user does this step, not what the cursor does.}}
> {{The meaning of the result that just appeared.}}

## 5. Demo: the result [45]

**Screen:** `{{/path}}`, {{the result screen; zoom on the key value if it is small}}

**Overlay:** `{{live}}`

**Say:**
> {{What changed for the person, on the same example as the problem.}}
> [pause]
> {{The number on screen, said as words, and what it is measured on.}}

## 6. Demo: the hard case [35]

**Screen:** `{{/path}}`, {{the edge case: a refusal, a conflict, bad input, no network}}. {{Cursor path and what the product answers.}}

**Overlay:** `{{live}}`

**Say:**
> {{The case where a naive solution breaks.}}
> {{What the product does instead and why that is safe.}}

## 7. Proof [35]

**Screen:** `{{/path}}` or deck slide {{N}}, {{the metrics screen: method, sample, date visible}}

**Overlay:** {{command and sample size of the measurement}}

**Say:**
> {{The measured result against the baseline, as words.}}
> {{What it was measured on and the cost or limit next to it.}}

## 8. Under the hood [25]

**Screen:** {{architecture from the deck or docs, or DevTools showing what really runs}}

**Overlay:** {{none}}

**Say:**
> {{What runs where, what works offline, what is replaceable.}}

## 9. Limits and next [15]

**Screen:** `{{/path}}` or deck slide {{N}}

**Overlay:** {{none}}

**Say:**
> {{The strongest limitation, said plainly.}}
> {{The next step, one sentence.}}

## 10. Close [15]

**Screen:** `{{/}}`, {{the logo and the stand URL large on screen}}

**Overlay:** {{stand URL, repository URL, team name}}

**Say:**
> {{Name, promise, where to try it, the address said as words.}}

## Pronunciation

| Term | Say it as |
| --- | --- |
| {{term}} | {{how to say it}} |
