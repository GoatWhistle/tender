---
name: jury-route
description: Map deliverables to jury criteria — docs/for-jury.md and docs/requirements-map.md built from context/requirements.md, an e2e test that mirrors the route, "code exists" kept apart from "verified on the stand", dated re-alignment with the task. Use when writing the jury route or requirements map, checking criteria coverage, re-reading the task against the code, or the user says "маршрут для жюри", "критерии оценки", "сверка с ТЗ", "что покажем жюри".
---

# Jury route

The jury scores criteria, not features. This skill turns `context/requirements.md` into two pages a
judge can verify, and keeps them honest as the code moves:

- `docs/requirements-map.md`: every requirement of the task → implementation → check → status.
- `docs/for-jury.md`: a click-by-click route on the stand, then every criterion → where it is answered.

Both pages exist as templates with their guidance in `{{…}}`. Write them in the product language and by
the `docs-writing` standard.

## Two statuses that never merge

| Status | Means | Allowed evidence |
| --- | --- | --- |
| **стенд** | Walked on the running stand at the submitted commit | A route step, an e2e run, a dated manual run with its inputs |
| **код** | Code and tests exist; not walked end to end on the stand | Unit or integration tests, a reviewed module |

**частично** names the missing part; **нет** names the reason and what replaces it. A row is never
promoted to «стенд» because its tests pass.

## 1. Read the sources

Read `context/requirements.md` (requirements R#, criteria and weights, documentation items),
`context/TASK.md` for the exact wording of anything ambiguous, `context/QA.md` for overrides, and the
routes and tests in the code.

Done: you can list every R#, every criterion with its weight and sub-items, and the demo scenario the
task prescribes, if any.

## 2. Build the requirements map

One row per mandatory requirement, in the task's order: Требование ТЗ with its page · Реализация (paths)
· Проверка (test paths, route step) · Статус и границы. Then optional items and bonuses, then the
assumptions taken instead of organizer answers (from `context/open-questions.md`).

Done: every R# from `requirements.md` has a row, every «стенд» row names a step or test, every
«частично» and «нет» row states its boundary in one sentence.

## 3. Design the route

- Follow the task's demo scenario when it prescribes one; otherwise order by criterion weight, the
  heaviest proven first.
- 5–20 steps. Each: exact action (URL, button, input), observable result (text, number, state), and
  what it proves (R# or criterion).
- Include one step where the system refuses or catches something: it shows the main rule working.
- The first steps need no install, no keys and no registration when a live stand exists.
- Demo accounts and seeded data are named in the page; demo data is labelled synthetic.

Done: every criterion with a weight is proven by at least one step or answered in step 4 with a reason
why it cannot be clicked.

## 4. Map every criterion

Under «Где ответ на каждый критерий?» one subsection per criterion, `### N. <criterion> — <weight> %`,
sub-items in the task's words, each answered by the mechanism in one phrase plus a link with an anchor
and the route step. Weights come only from the source; with no published weights, say so and quote
the criteria verbatim. Never compute an expected score.

Then «Чего в этом checkout нет?»: weights, keys, private data, services that exist only on the stand,
and how a judge can check without them.

Done: every criterion and sub-item from `requirements.md` has a row, and
`node .claude/skills/docs-writing/check-links.mjs docs` prints nothing.

## 5. Mirror the route in an e2e test

`frontend/e2e/jury-route.spec.ts` is the route as code: one `test.step` per table row, the same
number and the same action in the title, asserting the «Что увидеть» observable on seeded demo data.
The route and the test change in the same PR; a route step without a test step is a claim nobody checks.

Done: the test passes against the running stand, and its step titles match the table row by row.

## 6. Sync the README

The README «Посмотреть за две минуты» is the first 3–6 steps of the route; «Критерии ТЗ» condenses the
map with the same statuses. Hand over to the `readme` skill when the README is in its product phase.

## 7. Re-align with the task

At least once a day and once more before submission:

1. Re-read `context/TASK.md` (the PDF where wording matters) against the map, row by row.
2. Update statuses from what is true at the current commit; demote anything not re-walked.
3. Gaps become tickets ordered by criterion weight.
4. Add or rewrite the dated entry in `context/README.md` «Quick entry»:
   `**Task alignment — YYYY-MM-DD [verified]:** N of M mandatory on the stand, K code only, open: … → docs/requirements-map.md`.

Done: the dated entry exists for today, and every status in the map matches the current commit.

## Rules

- Product pages never link into `context/`: it is scrubbed at submission. Cite «ТЗ, раздел X, с. N».
- Our design choices are never presented as task requirements; they are marked as ours.
- A step that works only on one machine or only with a paid key says so in the step.
