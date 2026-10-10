---
name: docs-writing
description: The documentation standard for docs/ (page header, question-shaped headings, tables and mermaid, evidence statuses, no development story) plus a pre-submission audit pass one file at a time. Use when writing or editing any file in docs/, grading a claim as measured or assumed, auditing docs before submission, or the user says "документация", "допиши docs", "аудит документации", "docs audit".
---

# Docs writing

The reader is a judge or an engineer deciding whether the product is real. Every page must be worth
their time and true on the commit being submitted. Each page in `docs/` already exists as a template
whose `{{…}}` placeholders carry the guidance: fill it, keep its headings unless one is wrong for the
product, delete what stays empty.

## Page form

```markdown
# Title in sentence case

> Two to four sentences: what this page answers and the single most important takeaway.

**Читайте, если** <who needs it and why> · **Связано:** [a](a.md) · [b](b.md)

---

## Question or claim heading

---

<sub>[Оглавление документации](README.md) · [README проекта](../README.md)</sub>
```

English docs use `**Read this if** … · **Related:** …` and `[Documentation index] · [Project README]`.
Pages one folder down point the footer at `../README.md` and `../../README.md`. ADRs keep the
`domain-modeling` ADR format (title is the decision, then one paragraph, optional "Рассмотренные
варианты" and "Следствия").

## Writing rules

- **Headings are questions or claims**: «Как проходит основной сценарий?», «Пара проверяется до
  порога уверенности». Never «Обзор», «Введение», «Общие сведения».
- **Tables** for anything comparable: claims, checks, commands, routes, fields, variables. A cell
  over ~30 words means the prose moves under the table; more than ~5 columns only for data.
- **Mermaid** where a flow, sequence or dependency is easier seen than read: required in
  `architecture.md`, elsewhere only when it earns its place. Quote every label (`A["…"]`), keep a
  diagram under ~12 nodes, show the refusal path, not only the happy one.
- **Plain and exact.** Numbers instead of adjectives, the mechanism instead of the benefit, weaknesses
  at full strength. No emoji, no «уникальный», «инновационный», «мощный», «высокая точность»,
  «масштабируется», «Добро пожаловать», no hedging filler.
- **Owner's rule: the system as it is.** No development story: no «сначала мы», «после аудита»,
  «в ранней версии», «исправили», no dates of when something was found or who found it. State the
  rule, why it exists, what enforces it, where it stops. Two exceptions: the change log of
  `validation-plan.md` (pre-registration needs it) and dates that are part of a fact (a measured run,
  a source read on a date).
- **Code has no comments**, so the non-obvious lives in `design-decisions.md` as a row:
  Правило · Какой сбой предотвращает · Чем закреплено · Остаточный предел.
- **Internal pages stay internal.** `design-decisions.md`, `audits/`, `screens/`, `research/` are
  team working docs listed in `.claude/scrub-paths`: never linked from README or product pages,
  removed before the defense.
- **Diagrams in product colors.** Every mermaid block gets its `%%{init…}%%` line from
  `cd presentation && npm run readme`; never hand-pick colors.
- **One fact, one page.** Others link to it with an anchor; a repeated fact goes stale in one place.
- **Links**: relative between docs, repo-relative paths to code from docs (`../backend/…`). Never into
  `context/`, `.claude/`, `AGENTS.md`, `CLAUDE.md`, issues or PRs: all vanish at submission. The
  task is cited as «ТЗ, раздел X, с. N».
- **Terms** come verbatim from `docs/glossary.md`; new or changed terms go through `domain-modeling`.
- **Images** follow `docs/images/README.md`: real run, one window width, `<sub>` caption with the data.
- **No AI-tool names** as author or source anywhere in `docs/`.

## Evidence statuses

Every graded claim in `evidence.md` and every entry in `limitations.md` carries one status. When two
fit, use the lower. "Code exists" is not a status.

| Status | In Russian docs | Meaning |
| --- | --- | --- |
| Measured | **Измерено** | A command in the repo prints the number; command and sample size are next to it |
| Enforced | **Закреплено** | A named machine check fails when the property stops holding, and it runs in verify or CI |
| Verified by hand | **Проверено вручную** | Executed on specific named inputs, no general measurement |
| Observed | **Наблюдалось** | Seen live, possibly once; not generalised |
| Cited | **Из источника** | A third party's number or rule with a link; not re-measured |
| Assumption, not result | **Допущение, не результат** | Reasoned, unmeasured, labelled so nobody believes it by accident |
| False, and stated as false | **Неверно, и это сказано** | A property a reader might expect that the system does not have |

`requirements-map.md` uses its own scale (стенд · код · частично · нет), defined on that page.

A measured claim gets four lines: the hypothesis, the command, the sample, and what that sample
cannot show. A negative result is published next to the positive ones; a metric that failed its
threshold says so in the same table.

## Audit before submission

Run the audit in [AUDIT.md](AUDIT.md), one file at a time, then the whole-set checks at its end.

Done: every file in `docs/` passed all seven checks or was deleted, `grep -rn "{{" docs/` is empty, and
`node .claude/skills/docs-writing/check-links.mjs README.md docs` prints nothing.
