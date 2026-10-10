# Docs audit

Audit exactly one file per pass and fix what you find in that file only. Read `docs/README.md` and
skim the neighbouring pages first so duplicates are visible. In parallel, give each file its own agent
with this page as the brief; they must not touch each other's files.

## Seven checks, in order

1. **Needed.** Does the page earn its place in the submission? A section that repeats another page
   moves to one place and the other links to it. A page nobody needs is reported, not silently deleted.
2. **True now.** Every factual sentence is checked against the code, tests, configs, the validation
   report and the running stand. Run the offline commands the page names and compare the figures.
   Never run a paid command for an audit. A sentence that cannot be verified is deleted or marked
   **Допущение, не результат**.
3. **Process story.** Delete narrative about how the system came to be (owner's rule in
   [SKILL.md](SKILL.md)). Only dates that are part of a fact survive.
4. **Links alive.** `node .claude/skills/docs-writing/check-links.mjs docs/<file>.md` prints nothing.
   External URLs answer: `curl -sIL -o /dev/null -w "%{http_code}" --max-time 15 <url>`. No link into
   `context/`, `.claude/`, `AGENTS.md`, issues or PRs.
5. **Water.** Cut sentences that restate the heading, marketing adjectives, repeated admissions, and
   anything a reader cannot act on or verify.
6. **Tables readable.** No cell over ~30 words, no table wider than ~5 columns unless it is data,
   every row of a table is the same kind of thing.
7. **Form.** Title, blockquote answer, «Читайте, если · Связано» line, `---`, question or claim
   headings, footer. Mermaid labels quoted and balanced; the diagram renders in GitHub preview.

Report per file: what changed and why, facts corrected (old → new, with the command or file that
proved it), dead links fixed, whether the file is needed.

## Whole-set checks

- `grep -rn "{{" README.md docs/` prints nothing, including the SVGs in `docs/brand/`.
- `docs/README.md` lists every page that exists and no page that does not; its «Пункт ТЗ о
  документации» table covers every documentation item in `context/requirements.md`.
- The same number is the same everywhere: README, `evidence.md`, `for-jury.md`, the deck.
- Statuses agree: README «Критерии ТЗ», `requirements-map.md`, `for-jury.md`.
- Every limitation in the README is in `limitations.md` with a status, and vice versa for the
  strongest ones.
- Templates `docs/adr/_template.md` and `docs/screens/_template.md` are listed in
  `.claude/scrub-paths` so they do not ship.
