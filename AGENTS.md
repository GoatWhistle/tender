# Repository Guidelines

## Project Structure & Module Organization

Бэкенд — `backend/`, слои `domain` / `usecase` / `controller` / `adapter` / `repository`,
порт в `usecase/interface.py` — на всё, что можно заменить другой реализацией, даже если она
сейчас одна. Сборка — вручную, без DI-контейнера: реализации выбирает `backend/main.py`,
сценарии из портов собирает `backend/composition.py`. Правило и граница —
[`docs/adr/0001-layers-and-ports.md`](docs/adr/0001-layers-and-ports.md), раскладка и куда
класть новую сущность — `README.md`, «Устройство» и «Образцы». Замеры — `evals/`, продукт их не
импортирует.

## Build, Test, and Development Commands

Команды — `README.md`, «Разработка». Проверки перед PR:
`cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.

Отдельный GPU-сервис — `services/openjev/`, порт runtime — `openjev_service/usecase/interface.py`.
Запуск: `docker compose --profile gpu up --build -d openjev`; документация и проверки —
`services/openjev/README.md`. CPU-тесты без весов:
`PYTHONPATH=services/openjev backend/.venv/bin/python -m unittest discover -s tests/decisions -v`.

## Coding Style & Naming Conventions

Ruff (line 100) и mypy strict — конфиг в `backend/pyproject.toml`. Тексты, docs, issues,
коммиты — по-русски, идентификаторы — по-английски. Do not mix whitespace cleanup with unrelated
functional changes.

## Testing Guidelines

pytest, тесты — `backend/tests/`: через HTTP API на временной SQLite со схемой из миграций и
сценарии на in-memory хранилищах. Фикстуры — `backend/tests/conftest.py`; набор не читает
выгрузки организаторов и не ходит в сеть.

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
