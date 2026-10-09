# Repository Guidelines

## Project Structure & Module Organization

This directory currently contains no source code, tests, assets, or build configuration. Establish a clear layout when adding the first implementation. Suggested locations are `src/` for application code, `tests/` for automated tests, `assets/` for static resources, and `docs/` for supporting documentation. Group related modules by feature and document actual entry points in `README.md`.

## Build, Test, and Development Commands

No build, test, or local development commands are configured yet. When selecting a toolchain, provide reproducible commands for installation, local execution, testing, formatting, and production builds. Record these commands in `README.md` and update this guide. Do not assume commands such as `npm test` or `make build` work until their configuration exists.

## Coding Style & Naming Conventions

Adopt the chosen language’s standard formatter and linter, and commit their configuration. Until then, follow surrounding code, use consistent indentation within each file, and choose descriptive names. Keep modules focused and avoid introducing multiple naming styles for equivalent concepts. Do not mix whitespace cleanup with unrelated functional changes.

## Testing Guidelines

No testing framework or coverage threshold is established. Add tests alongside new behavior using the selected framework’s naming conventions. Cover normal operation, edge cases, and failure paths. Document how contributors run the suite; keep tests deterministic and independent of private credentials.

## Commit & Pull Request Guidelines

No Git repository or commit history is present, so existing message conventions cannot be inferred. Once Git is initialized, use concise, imperative commit subjects, such as `Add initial application scaffold`. Keep commits focused. Pull requests should explain the change, list validation performed, link relevant issues, and include screenshots for visible interface changes.

## Security & Configuration

Keep secrets and machine-specific settings out of version control. Provide example configuration with placeholder values and document required environment variables. Configure ignore rules before adding generated artifacts or local credentials.

## Скилы и трекер

- **Скилы** — `.claude/skills/` (mattpocock, см. `.claude/skills/README-pocock.md`). Трекер для
  `to-spec` / `to-tickets` / `triage` / `wayfinder` / `implement` / `orchestrate-issues` и любой
  работы с issues и PR — GitHub Issues через MCP `github`: [`.claude/tracker.md`](.claude/tracker.md).
  Доменные доки — этот файл и `docs/`.
- **Работа:** один issue — свежая сессия, свой worktree, ветка `feat/<slug>`, PR в `main` с
  `Closes #N`. Порядок — по строке `Blocked by:` в теле issue.
- **Без следов ИИ-агентов:** Claude, Claude Code, Codex и другие агенты не упоминаются как автор,
  соавтор или источник в коммитах, PR, issues и комментариях — без `Co-Authored-By`,
  `Generated with …` и AI-дисклеймеров.
