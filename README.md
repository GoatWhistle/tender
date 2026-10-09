# Tender Hack: автозаполнение характеристик СТЕ и подбор КТРУ

План реализации — `docs/Предлагаемое решение.md`. Трекер и порядок работы — `AGENTS.md`.

## Устройство

```
backend/                 FastAPI + SQLAlchemy + Alembic, SQLite
  main.py                сборка прода вручную: `create_app` (запуск — `uvicorn --factory
                         main:create_app`) и синхронизация справочника `sync_catalog`
  composition.py         общая проводка сценариев из портов — для прода, тестов и замеров
  settings.py            настройки окружения `Settings` и пути к данным
  build_var.py           офлайн-артефакты для замеров: снимок КТРУ, словарь, образцы СТЕ → var/
  app/                   только слои — docs/adr/0001-layers-and-ports.md
    domain/              понятия и правила без библиотек: позиции КТРУ, характеристики, значения
    usecase/             сценарии на единице работы и порты (`interface.py`)
    controller/          роутеры FastAPI, схемы Pydantic, зависимости, ошибки → HTTP
    adapter/             реализации портов: справочник из XML ЕИС и из JSON-снимка
    repository/          хранилища на SQLite, ORM всех таблиц (`orm/`), in-memory (`memory/`)
  migrations/            миграции схемы
  tests/                 тесты через HTTP API и сценарии на in-memory хранилищах
frontend/                витрина покупателя: React + Vite, мок API — frontend/README.md
data/yandex_disk/        данные организаторов: XML КТРУ, выгрузки СТЕ
evals/                   замеры: наборы `datasets/`, скрипты `smoke/`, отчёты `reports/`
var/                     локальные артефакты (не в git): база, снимок КТРУ, словарь
```

Зависимости слоёв идут внутрь, к `domain`; `backend/tests/test_layers.py` это проверяет.
Сущность проходит слои под одним именем: справочник КТРУ — `domain/catalog.py`,
`usecase/catalog.py`, `controller/catalog.py`, `repository/catalog.py`.

## Разработка

```bash
cd backend
uv sync
uv run alembic upgrade head                        # схема в var/tender.db
uv run python -c 'import main; main.sync_catalog()'  # КТРУ из data/ в базу
uv run uvicorn --factory main:create_app --reload  # http://localhost:8000/api/docs
uv run python build_var.py                         # var/ktru.json, var/vocab.json для evals/
```

Проверки перед PR:

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
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
  в `build_usecases`.
- **Миграция** — `uv run alembic revision --autogenerate -m "short english slug"`, затем
  прочитать и поправить. `test_models_match_migrations` падает, если модели разошлись с
  миграциями.
- **Ошибки** — подкласс `DomainError` в `app/domain/errors.py` с `code` и `message` по-русски,
  без HTTP-статуса. Статус — строка в `STATUS` (`app/controller/errors.py`); эндпоинт перечисляет
  ошибки в `responses=error_responses(...)`.
- **Замер** — скрипт в `evals/`, продукт берёт через `composition.py` и адаптеры; `app`, `main`
  и `composition` `evals` не импортируют.
