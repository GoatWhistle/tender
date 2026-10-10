# Tender Hack: автозаполнение характеристик СТЕ и подбор КТРУ

План реализации — `docs/Предлагаемое решение.md`. Трекер и порядок работы — `AGENTS.md`.
Поля КТРУ и дерево групп — `docs/Словарь данных КТРУ.md`.

## Устройство

```
backend/                 FastAPI + SQLAlchemy + Alembic, SQLite
  main.py                сборка прода вручную: `create_app` (запуск — `uvicorn --factory
                         main:create_app`) и синхронизация справочника `sync_catalog`
  composition.py         общая проводка сценариев из портов — для прода, тестов и замеров
  settings.py            настройки окружения `Settings` и пути к данным
  build_var.py           офлайн-артефакты для замеров: снимок КТРУ, словарь, образцы СТЕ → var/
  app/                   только слои — docs/adr/0001-layers-and-ports.md
    domain/              понятия и правила без библиотек: позиции КТРУ, характеристики, значения,
                         запросы к моделям и их ответы (`inference.py`)
    usecase/             сценарии на единице работы, порты (`interface.py`), общая проверка
                         ответов моделей (`model_checks.py`)
    controller/          роутеры FastAPI, схемы Pydantic, зависимости, ошибки → HTTP
    adapter/             реализации портов: справочник из XML ЕИС и из JSON-снимка, заглушки
                         моделей для тестов (`stub/`)
    repository/          хранилища на SQLite, ORM всех таблиц (`orm/`), in-memory (`memory/`)
  migrations/            миграции схемы
  tests/                 тесты через HTTP API и сценарии на in-memory хранилищах
frontend/                React + Vite: экран поставщика `/sell` на API сессий, витрина на мок-сервисе
                         — frontend/README.md
data/yandex_disk/        данные организаторов: XML КТРУ, выгрузки СТЕ
evals/                   замеры: наборы `datasets/`, скрипты `smoke/`, `catalog/`, `e2e/`, отчёты `reports/`
var/                     локальные артефакты (не в git): база, снимок КТРУ, словарь
artifacts/               подготовленная SQLite КТРУ с реальными векторами Qwen (в git)
services/openjev/        самостоятельный GPU-сервис OpenJev 4B: API, кеш и pinned runtime
services/qwen/           Qwen3 embeddings и Qwen3.5 strict extractor, Docker и GPU-проверки
```

Зависимости слоёв идут внутрь, к `domain`; `backend/tests/test_layers.py` это проверяет.
Сущность проходит слои под одним именем: справочник КТРУ — `domain/catalog.py`,
`usecase/catalog.py`, `controller/catalog.py`, `repository/catalog.py`.

## Разработка

Гибридный поиск групп: `POST /api/v1/search`, TF-IDF + Qwen + синонимы, слияние RRF.
Готовая база трёх категорий, запуск без векторизации документов, настройки сервиса,
команда сборки и smoke-замер — [`docs/search.md`](docs/search.md).

Сессии анализа: создание, история сообщений, извлечение фактов без модели, проверка правил
и сужение позиций с объяснениями через
`/api/v1/sessions`. Контракт, идемпотентность и примеры — [`docs/sessions.md`](docs/sessions.md).

GPU decision-сервис запускается отдельно: `docker compose --profile gpu up --build -d openjev`.
Условия запуска, API/curl, переменные окружения и CPU-проверки —
[`services/openjev/README.md`](services/openjev/README.md).

Embeddings и strict экстрактор запускаются рядом с OpenJev через
`compose.qwen.yaml`: подготовка весов, запуск на чистой машине, API и проверки —
[`services/qwen/README.md`](services/qwen/README.md).

```bash
cd backend
uv sync
uv run alembic upgrade head                        # схема в var/tender.db
uv run python -c 'import main; main.sync_catalog()'  # КТРУ из data/ в базу
uv run uvicorn --factory main:create_app --reload  # http://localhost:8000/api/docs
uv run python build_var.py                         # var/ktru.json, var/vocab.json для evals/
```

Фронтенд — Node 22+, npm. `/api` Vite проксирует на бэкенд `http://localhost:8000`; экран
поставщика и контракт — [`frontend/README.md`](frontend/README.md).

```bash
cd frontend
npm ci
npm run dev           # http://localhost:5173, экран поставщика — /sell
npm run build         # typecheck и сборка в frontend/dist
npm run format        # Prettier переписывает файлы
```

Проверки перед PR:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

### Образцы

- **Новая сущность** — по слоям, файлы под одним именем
  ([`docs/adr/0001-layers-and-ports.md`](docs/adr/0001-layers-and-ports.md)):
  1. `app/domain/<имя>.py` — dataclass-ы и правила без SQLAlchemy, Pydantic и FastAPI;
  2. `app/usecase/<имя>.py` — сценарий-класс на единице работы, каждый вызов — блок `with uow:`;
     хранилище — порт-`Protocol` в `app/usecase/interface.py`;
  3. `app/repository/<имя>.py` — реализация порта, ORM таблицы — `app/repository/orm/<имя>.py` и
     импорт в `app/repository/orm/__init__.py` (по нему миграции видят таблицы); наружу —
     доменные значения, не строки ORM; in-memory — `app/repository/memory/<имя>.py`;
  4. `app/controller/<имя>.py` и `<имя>_schemas.py` — роутер и схемы; сценарий приходит
     зависимостью из `app/controller/deps.py`;
  5. проводка — фабрика сценария в `backend/composition.py`, реализации — в `backend/main.py`,
     там же подключается роутер.
- **Порт модели или внешней системы** (поиск, decision-модель, извлекатель): `Protocol` в
  `app/usecase/interface.py` с доменными типами на входе и выходе; реализация — в
  `app/adapter/`, библиотеку импортирует только она; создаётся в `backend/main.py` и передаётся
  в `build_usecases`. Порт модели сценарий получает только за общей проверкой ответа —
  `checked_*` из `composition.py`; управляемая заглушка для тестов — `app/adapter/stub/`.
- **Миграция** — `uv run alembic revision --autogenerate -m "short english slug"`, затем
  прочитать и поправить. `test_models_match_migrations` падает, если модели разошлись с
  миграциями.
- **Ошибки** — подкласс `DomainError` в `app/domain/errors.py` с `code` и `message` по-русски,
  без HTTP-статуса. Статус — строка в `STATUS` (`app/controller/errors.py`); эндпоинт перечисляет
  ошибки в `responses=error_responses(...)`.
- **Замер** — скрипт в `evals/`, продукт берёт через `composition.py` и адаптеры; `app`, `main`
  и `composition` `evals` не импортируют.


### Оценка русских ошибок

Fixtures четырёх классов: `evals/datasets/errors_ru_v1.json`; правила и демонстрации —
`docs/Предлагаемое решение.md`, §§8.8, 9.3, 15.6, 16.1, 20.2. Метрики считаются из JSONL
ответов приложения, не из подставленного эталона:

```bash
python3 evals/errors/score.py --predictions /path/to/predictions.jsonl
python3 -m unittest discover -s tests/evals -v
ruff check evals/errors tests/evals evals/server/bench_typos_api.py evals/server/bench_llm_typos_api.py
```

Прогоны орфографии через API (модель уже должна быть запущена):

```bash
python3 evals/server/bench_typos_api.py --help
python3 evals/server/bench_llm_typos_api.py --help
```

Измеренные отчёты: `evals/reports/2026-10-10-openjev-typos-api.md` и
`evals/reports/2026-10-10-qwen4b-typos-api.md`. Это development-оценка опечаток;
качество остальных классов на приложении ещё не измерено.

### Сквозной замер

Набор разработки `evals/datasets/dev_v1.json` (60 кейсов) и holdout реальных СТЕ
`evals/datasets/ste_holdout_v1.csv` (60 строк) проходят через HTTP API продукта: сессия по
сообщениям и поиск групп. Формат наборов и как проверять разметку —
[`evals/datasets/README.md`](evals/datasets/README.md).

```bash
cd backend
uv run python ../evals/e2e/dataset.py                    # разметка против справочника КТРУ
uv run python ../evals/e2e/run.py --embeddings-url http://127.0.0.1:18083/v1  # отчёт в evals/reports/
uv run python ../evals/e2e/run.py --stub-embeddings      # проверка прогона без модели
cd .. && python3 -m unittest discover -s tests/evals -v  # подсчёт метрик
```

Отчёт — `evals/reports/<дата>-e2e.md` и `.json`: R@1/5/10 групп отдельно по набору и по
holdout, «вне КТРУ», точность и доля выданных кодов, сохранённая неоднозначность, факты,
статусы и разбивка по тегам. Точность кода учитывает все выдачи, включая ошибочную выдачу
товару вне КТРУ; доля выдачи считается от всех 60 кейсов разработки. R@K считается только
по кейсам с допустимыми группами. Отказ от классификации, классы ошибок и число вопросов
до кода — «пропущено», пока продукт их не поддерживает. Holdout выбирает `evals/e2e/sample_holdout.py` с
фиксированным seed; существующую разметку он не перетирает.

Первый отчёт с реальными эмбеддингами:
[`2026-10-10-e2e.md`](evals/reports/2026-10-10-e2e.md), построчные ответы — в соседнем JSON.

### Свободные значения характеристик

Для сопоставления «стальная» → «Сталь» задайте `DECISION_URL` существующего OpenJev-сервиса
(пример — `backend/.env.example`). Предложения подтверждаются на экране поставщика; возможны
«Принять», «Выбрать другое» и «Не знаю». Автопринятие включено с порогом оценки 0,90 при однозначной привязке;
`DECISION_AUTO_ACCEPT_ENABLED=false` оставляет все предложения на подтверждение. Контракт, ограничения и правила ревизий — [docs/sessions.md](docs/sessions.md).

Воспроизводимый замер enum-сопоставления через HTTP-сценарий продукта, из корня репозитория:

```bash
backend/.venv/bin/python evals/enum/run.py --url http://127.0.0.1:18080 --out var/enum-mapping.json
```

Используются `dev_v1.json` (подбор порога) и отдельный замороженный `enum_holdout_v2.json`
(проверка без подбора). Понадобится справочник КТРУ в `KTRU_XML_DIR`; GPU-сервис запускается
по [инструкции OpenJev](services/openjev/README.md).
[Сохранённый отчёт](evals/reports/2026-10-10-enum-mapping.md) содержит методику, абсолютные
числа, статистические ограничения, задержку и VRAM.
