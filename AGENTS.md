# Repository Guidelines

## Структура

- `src/rag/` — прототип RAG по справочнику КТРУ: подбор позиции по описанию товара от
  поставщика. Цепочка, данные, команды и API — [`README.md`](README.md).
- Слои `src/rag/` как в `legacy/backend`: `domain/` → `usecase/` (порты в `interface.py`) →
  `adapter/`, `repository/`, `controller/`; сборка — `main.py` и `composition.py`. Карта
  слоёв и правила — README, «Слои».
- `data/` — выгрузка КТРУ и индекс, вне git. Собирается `rag-parse` → `rag-embed`
  (README, «Собрать индекс»).
- `legacy/` — архив прежнего проекта: бэкенд, фронтенд, сервисы, docs, evals. Работа идёт в
  `src/rag/`; `legacy/` открывай только по прямой просьбе, тогда правила — в
  [`legacy/AGENTS.md`](legacy/AGENTS.md), пути в нём считаются от `legacy/`.

## Команды

Окружение — uv, всё из корня: `uv sync`, команды — `uv run rag-*`, список в
`[project.scripts]` `pyproject.toml`. Ключ API эмбеддингов — в `.env` по образцу
`.env.example`. Перед коммитом: `uvx ruff check src`.

Прототип без тестов: изменение проверяй прогоном `uv run rag-rerank "<описание товара>"` и
сравни выдачу до и после.

## Инварианты

- **Строка индекса.** Номер строки в `data/vectors.npy` = индекс в `codes.json` и
  `texts.json`. Правка `position_text` (`domain/catalog.py`) или фильтра позиций
  (`adapter/ktru_zip.py`) меняет тексты, и векторы надо пересчитать: `rag-parse` при расхождении печатает «ВНИМАНИЕ: коды или тексты
  изменились».
- **Модель только через порт.** Сценарии зовут модель через `LanguageModel.complete`
  (`usecase/interface.py`); Agent SDK импортирует только `adapter/llm/claude_agent.py`, HTTP к
  OpenAI-совместимому API — только `adapter/llm/openai_compatible.py`. Реализацию выбирает
  `language_model` в `main.py`. Промпт и JSON-схема — в сценарии, а не в адаптере.
- **Изолированный вызов Claude.** `ClaudeAgentModel` собирает каждый вызов со своим
  `system_prompt`, `setting_sources=[]`, `tools=[]`, `cwd` во временной пустой папке и
  `output_format` с JSON-схемой. Иначе модель видит проект через рабочую папку и настройки
  Claude Code.
- **Слои.** `domain` и `usecase` не импортируют FastAPI, Pydantic, numpy, aiohttp, sklearn,
  openpyxl и Agent SDK. Pydantic-схемы — только в `controller/http/schemas.py`, HTTP-коды —
  в `controller/http/errors.py`.

## Стиль

Код без комментариев и docstring; неочевидное объясняется в `README.md`. Тексты, README,
issues, коммиты — по-русски, идентификаторы — по-английски. Whitespace-правки — отдельным
коммитом от функциональных.

## Скилы и трекер

- **Скилы** — `.claude/skills/` (mattpocock, см. `.claude/skills/README-pocock.md`). Трекер для
  `to-spec` / `to-tickets` / `triage` / `wayfinder` / `implement` / `orchestrate-issues` и любой
  работы с issues и PR — GitHub Issues через MCP `github`: [`.claude/tracker.md`](.claude/tracker.md).
- **Работа:** один issue — свежая сессия, свой worktree, ветка `feat/<slug>`, PR в `main` с
  `Closes #N`. Порядок — по строке `Blocked by:` в теле issue.
- **Авторство:** коммиты, PR, issues и комментарии подписаны только людьми команды — без
  `Co-Authored-By`, `Generated with …` и упоминаний Claude, Claude Code, Codex и других агентов.
