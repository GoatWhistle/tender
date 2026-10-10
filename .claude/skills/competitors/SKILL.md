---
name: competitors
description: Competitive analysis for a hackathon pitch — existing products, open-source tools and visible rival submissions, threat tiers, criterion-by-criterion "they vs us" scores and an honest "where they beat us". Use when preparing differentiation, the business slide or Q&A, or when the user says "конкуренты", "аналоги", "чем мы лучше", "competitors", "alternatives".
---

The jury will ask "how is this different from X". The answer must exist before the question, and it must be honest: a team that names where a rival wins is believed on everything else.

## 1. Collect

Use web search (or the `research` skill for a background pass). Look for:

- products already sold for this job, including the boring incumbent (spreadsheets, manual process, the organizer's current tool);
- open-source projects and papers that do the core mechanism;
- other teams' public submissions, if the platform shows them.

For each: name, link, who uses it, what it does for the same user, price or licence, the date you looked. Quote claims from their own pages; do not guess features.

## 2. Score

A table per competitor against the jury criteria from `context/requirements.md`: criterion, them 1–10, us 1–10, evidence for both scores. Then assign a threat tier:

- **S** — solves the same P0 scenario for the same user;
- **A** — solves part of it or for a neighbouring user;
- **B** — same domain, different job.

## 3. Write it down

`context/competitors.md` (internal, scrubbed at submission):

- the tier list with one line per competitor;
- **where they beat us** — specific, with evidence; this feeds `jury-qa`;
- **our difference in one sentence per S/A competitor**, phrased as a mechanism, not an adjective ("we measure X before Y", never "we are faster and smarter");
- what we deliberately do not compete on.

Done: every S and A competitor has a one-sentence difference and a prepared answer in `presentation/QA.md`.
