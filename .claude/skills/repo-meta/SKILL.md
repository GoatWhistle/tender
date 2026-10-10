---
name: repo-meta
description: Write the GitHub repository description, homepage and topics for this project — a two-part description (the rule the product guarantees, then what it is) without AI patterns, and 10–20 topics people actually search, mixing event, domain, mechanism and the real stack found in the code; checked by `meta.mjs check`, applied with the printed `gh repo edit` commands. Use when the repo needs a description, "about", tags or topics, or before submission — «описание репозитория», «описание репо», «теги», «топики», «about на гитхабе», "repo description", "GitHub topics".
---

# Repository description and topics

The "About" box is the first text a judge reads, in the org list, in search and on the repo page.
It is one rule and one definition, not a slogan. Topics make the repo findable and show the stack
at a glance.

## 1. Inputs

The README promise and main rule, `docs/for-jury.md`, `context/PLATFORM.md` (required tags, the
event and sponsor names), the stand URL, and the real stack:

```bash
node .claude/skills/repo-meta/meta.mjs scan
```

prints every technology found in `package.json`, `pyproject.toml`, requirements, `Cargo.toml`,
`go.mod`, `Gemfile`, Dockerfiles and compose files, marked `stack` (worth a topic) or `lib`
(usually not).

## 2. Description

English, 140–300 characters (GitHub allows 350, lists cut earlier), no trailing period at the
very end. Two parts:

1. **The rule.** What the product guarantees or refuses, as a falsifiable sentence about behaviour.
   Name who decides what: the model, the code, the human. Often a contrast: what everyone else
   trusts and what this product trusts instead.
2. **What it is.** A noun phrase: category, for whom or which domain, and the one constraint that
   matters (offline, local models, no paid API, a regulation it follows).

Patterns that work:

| Pattern | Shape |
| --- | --- |
| Guarantee + definition | "Every {{output}} comes with {{proof}}. {{What it refuses instead of guessing}}. {{Category}} for {{domain}} on {{constraint}}" |
| Division of labour | "The LLM only {{proposes}}; the code {{checks/decides}}. {{Second guarantee}}. {{Category}} for {{domain}}" |
| Reframe | "{{Common belief}} don't {{X}}, they {{Y}}. {{Product}} {{catches Y}}, {{fixes it}} and {{proves it}}" |
| Refusal | "{{Category}} that {{does the job}} and says what it could not {{do}}: {{concrete list}}" |

Rules:

- Concrete nouns and verbs from the domain; a number only if it is in `docs/evidence.md`.
- No product name at the start (GitHub shows it), no "this project", "a tool that", "a platform
  that", "solution", "AI-powered", "innovative", "seamless", "robust", "leverage", "empower",
  "next-generation", "designed to", "aims to", "helps you", "built with".
- No em or en dashes, no spaced hyphens, no arrows, no middle dots, no emoji: use a period, a
  colon, a semicolon or a comma. Chains are written in words ("from the crude unit to diesel
  blending"), never with arrows.
- Not a feature list, not the hackathon name (that is a topic), not the team.
- Pass it through the `humanizer` skill, then read it aloud: if it sounds like a landing page,
  rewrite the rule.

Bad and better:

| Bad | Better |
| --- | --- |
| "AI-powered copilot web application that helps small businesses solve legal and financial tasks" | "Every answer cites the law or the bank rule it relies on, or says it has none. Assistant for small business owners on legal and financial questions" |
| "Smart platform for supplier search using cutting-edge ML" | "Each recommended supplier comes with proof: a past bid, a catalogue offer or a registry record. Supplier search for public procurement on local models" |
| "Advisor — given, derived or measured → recommendation" | "Every number carries its origin, and a calculation that needs an unknown returns unknown instead of a constant. Process advisor for a refinery unit chain" |

## 3. Topics

10–20 topics (GitHub allows 20), lowercase, digits and hyphens, at most 50 characters each. Build
them in this order and stop at 20:

| Group | Count | What |
| --- | --- | --- |
| Event | 1–3 | `hackathon`, plus the sponsor or platform tag when the rules ask for it |
| Domain | 2–4 | Where it lives: `public-procurement`, `healthcare`, `oil-and-gas`, `robotics` |
| Mechanism | 3–6 | What makes it different: `explainable-ai`, `deterministic`, `hybrid-search`, `human-in-the-loop`, `knowledge-graph`, `provenance` |
| Problem | 1–3 | What someone would search for: `supplier-search`, `pii-detection`, `medication-safety` |
| Stack | 4–7 | Only `stack` entries from `scan`: language, framework, datastore, ML engine, `docker` |

- Prefer the established spelling GitHub already uses (`llm`, `rag`, `nextjs`, `postgresql`,
  `react`, `typescript`, `llm-agents`) over invented ones.
- Never `css`, `html`, `js`, `ai`, `app`, `project`, `web`, `tool`: noise that matches everything.
- No technology that is not in the code; `scan` and `check` catch both directions.
- Keep the same mechanism tags across the team's projects when they are true: a consistent org
  looks deliberate.

## 4. Check and apply

Write the proposal to `context/repo.json`:

```json
{
  "repo": "{{owner}}/{{repo}}",
  "name": "{{repo}}",
  "description": "{{rule}}. {{definition}}",
  "homepage": "https://{{DOMAIN}}",
  "topics": ["hackathon", "{{domain}}", "{{mechanism}}", "{{stack}}"]
}
```

```bash
node .claude/skills/repo-meta/meta.mjs check context/repo.json
```

It fails on length over 350, dashes, arrows, emoji, banned phrases, noise topics, invalid or
duplicate topics and more than 20 of them; it warns on a long or short description, a trailing
period, stack topics missing from the code and headline stack missing from topics. Then it prints
the `gh repo edit` commands. Changing the public repo is an outward action: show the description,
the topics and the commands to the user and run them only when asked.

Done when `check` has 0 errors, the description was read aloud once, and the user has the commands
or confirmed they were applied.
