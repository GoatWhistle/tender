# GPU-сервис OpenJev 4B v5

Самостоятельный процесс decision-модели для будущего стека приложения. Сервис принимает
описание и новые гипотезы, возвращает native NLI либо выбирает один класс по явным критериям.
Модель: `AlexWortega/openjev`, подкаталог `qwen3.5-4b-nli-v5`, ревизия
`a20448012c213128955ca0c693e7c943865cab77`. Веса BF16, attention SDPA, FLA 0.5.2 и
reference causal convolution. `causal-conv1d` не устанавливается и не собирается.

## Запуск на Linux с NVIDIA

Нужны Linux x86_64, NVIDIA GPU с BF16 (например, A100), совместимый с CUDA 13 драйвер,
Docker Compose v2 и NVIDIA Container Toolkit. Зависимости CUDA приходят с закреплёнными
Python wheels. Код не устанавливает и не меняет драйверы. Для 4B начните с GPU на 16 GiB
или больше; запас памяти зависит от длины описания, числа гипотез и настроек кеша.

Из корня репозитория:

```bash
cp services/openjev/.env.example .env
docker compose --profile gpu config
docker compose --profile gpu up --build -d openjev
docker compose logs -f openjev
curl --fail http://127.0.0.1:8000/health/ready
```

При первом старте сервис скачивает около 9.1 GB весов и небольшие файлы модели с
фиксированной ревизии. Все SHA256 и размеры, включая официальный Python-код и tokenizer,
закреплены в `openjev_service/adapter/model_manifest.json`. Файлы скачиваются во временный
`.partial`, проверяются и затем атомарно заменяются. Повторный запуск проверяет реальные
байты на постоянном томе `openjev-weights`; корректные файлы повторно не скачиваются.
Интернет требуется для отсутствующих или повреждённых файлов. Загрузка не требует токена.

`/health/live` доступен во время загрузки, `/health/ready` отвечает 503 до проверки весов,
прогрева полного forward и prepared continuation. Весь inference выполняется одним потоком
одного процесса. Параллельные workers и `--reload` для этого сервиса не применяются;
дополнительная блокировка тома не позволяет двум процессам разделить один каталог модели.

```bash
docker compose --profile gpu restart openjev  # веса остаются на томе
docker compose --profile gpu down            # том также сохраняется
```

`down -v` удалит веса. При остановке сервис прекращает приём запросов, отклоняет ожидающие,
завершает текущую GPU-операцию и освобождает все prepared contexts. При отказе CUDA/runtime
readiness становится 503; подробности доступны в логах, процесс нужно перезапустить.

## API

Native NLI: один полный вход на каждую гипотезу, одна обученная трёхклассовая голова:
`contradicted`, `supported`, `not_stated`. Вход не является chat prompt.

```bash
curl --fail http://127.0.0.1:8000/v1/nli \
  -H 'Content-Type: application/json' -d '{
    "premise": "Стол изготовлен из дерева. Высота 75 см.",
    "hypotheses": ["Стол деревянный.", "Стол изготовлен из стекла.", "Стол красный."]
  }'
```

Ответ содержит `results` с гипотезой, `label` и native `probabilities`, а также `context`
и `model_revision`. Повторные запросы с точно тем же `premise` автоматически используют
тот же prepared context. Готовые ответы не кешируются.

Контекст можно подготовить явно и использовать для новых гипотез без повторной передачи
описания:

```bash
context_id=$(curl --fail http://127.0.0.1:8000/v1/contexts \
  -H 'Content-Type: application/json' \
  -d '{"premise":"Стол изготовлен из дерева. Высота 75 см."}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["context"]["id"])')

curl --fail http://127.0.0.1:8000/v1/nli \
  -H 'Content-Type: application/json' \
  -d "{\"context_id\":\"$context_id\",\"hypotheses\":[\"Высота стола 75 см.\"]}"

curl --fail http://127.0.0.1:8000/v1/choice \
  -H 'Content-Type: application/json' \
  -d "{\"context_id\":\"$context_id\",\"instructions\":\"Выбери материал стола\",\"options\":[{\"id\":\"wood\",\"criterion\":\"Стол изготовлен из дерева\"},{\"id\":\"glass\",\"criterion\":\"Стол изготовлен из стекла\"}]}"

curl --fail -X DELETE "http://127.0.0.1:8000/v1/contexts/$context_id"
```

В каждом запросе требуется ровно одно поле: `premise` или `context_id`. У `choice`
минимум две опции с уникальными `id` и непустыми `criterion`; произвольные внешние ID
переносятся в ответ. Внутри используются нейтральные метки `o0`, `o1` и официальный шаблон
`The answer to "{instr}" is {label}: {crit}`, поэтому ID не подменяет смысл критерия.
`support_probabilities` — исходные `P(supported)` для критериев, `probabilities` — их
нормализация по опциям, `choice` — argmax. Эти числа не являются откалиброванной уверенностью
или автоматическим порогом принятия решения. Изменение вопроса/критериев вызывает новый
inference с тем же подготовленным описанием.

Для проверки полного inference передайте `"use_cache": false` вместе с `premise`.
Это запрещено вместе с `context_id`. OpenAPI и интерактивные примеры: `/docs`.

## Кеш, очередь и ограничения

Кеш живёт в GPU-процессе между HTTP-запросами, на диск сохраняются только веса. Его ключ
включает точное исходное описание, ревизию, BF16/SDPA и шаблон. Полная пара токенизируется
без truncation; её начало обязано точно совпасть с токенами prepared prefix. До continuation
копируются все attention KV, recurrent и convolution states. TTL абсолютный с момента
создания; попадание обновляет LRU, но не продлевает TTL. Истёкшие contexts освобождаются
также при простое. После TTL, LRU eviction, удаления или перезапуска ID возвращает 404;
повторите подготовку либо отправьте `premise`.

Число contexts, сумма их уникальных tensor storage bytes и сумма prefix tokens ограничены.
Byte budget относится к удерживаемым состояниям; текущий prefill и копия для microbatch
временно требуют дополнительной памяти. Входы и размеры microbatch также ограничены.
Очень длинная пара отклоняет весь запрос до GPU; дробление или усечение текста не происходит.
Microbatch разбивает гипотезы, сохраняя порядок ответа. Верхняя граница padded tokens
считается по полным парам, даже при переиспользовании prefix.

| Переменная | По умолчанию | Назначение |
| --- | ---: | --- |
| `OPENJEV_MAX_TOKENS` | 4096 | Токены полной пары с шаблоном |
| `OPENJEV_MAX_BATCH` | 32 | Гипотезы/опции на запрос |
| `OPENJEV_MICROBATCH` | 4 | Максимум строк одного forward |
| `OPENJEV_MICROBATCH_TOKENS` | 16384 | `batch × max(full_pair_tokens)` |
| `OPENJEV_QUEUE_SIZE` | 8 | Ожидающие задания, отдельно от активного |
| `OPENJEV_REQUEST_TIMEOUT` | 120 | Секунды ожидания и исполнения |
| `OPENJEV_MAX_BODY_BYTES` | 1048576 | Байты тела до разбора JSON, включая chunked body |
| `OPENJEV_CACHE_ENTRIES` | 8 | Максимум contexts |
| `OPENJEV_CACHE_BYTES` | 1073741824 | Удерживаемые состояния (1 GiB) |
| `OPENJEV_CACHE_TOKENS` | 32768 | Сумма prefix tokens |
| `OPENJEV_CACHE_TTL` | 300 | Секунды жизни context |
| `OPENJEV_MODEL_DIR` | `/models/openjev` | Каталог модели при прямом Python-запуске |
| `OPENJEV_BIND_ADDRESS` | `127.0.0.1` | Адрес публикации Compose |
| `OPENJEV_PORT` | 8000 | Порт публикации Compose |

Дедлайн не прерывает уже запущенную CUDA-операцию. Клиент получает 504, а GPU-поток
завершает её последовательно; отменённые ожидающие задания пропускаются.

| HTTP | Причина |
| --- | --- |
| 422 | Неверная схема, пустые строки, повторяющиеся ID, неверный выбор premise/context |
| 413 | Слишком длинная пара, batch, body или context сверх бюджета |
| 409 | Несовпадение точного token prefix |
| 404 | Context отсутствует, истёк или был вытеснен |
| 429 | Очередь заполнена; `Retry-After: 1` |
| 503 | Прогрев, остановка либо ошибка runtime; `Retry-After: 1` |
| 504 | Истёк дедлайн запроса |

Ошибки сервиса имеют форму `{"error":{"code":"...","message":"..."}}`; ошибки Pydantic
используют стандартное поле `detail`. Сервис не содержит авторизации; Compose по умолчанию
публикует его на loopback, чтобы основной бэкенд позже подключался как HTTP-клиент.

## Прямой GPU-запуск и проверки

В отдельном Python 3.12 окружении на Linux x86_64:

```bash
python3.12 -m venv services/openjev/.venv
services/openjev/.venv/bin/pip install -r services/openjev/requirements.lock.txt
PYTHONPATH=services/openjev OPENJEV_MODEL_DIR=var/openjev \
  services/openjev/.venv/bin/python -m openjev_service
```

Проверить или заранее скачать закреплённые файлы:

```bash
PYTHONPATH=services/openjev python -m openjev_service.adapter.weights --model-dir var/openjev
PYTHONPATH=services/openjev python -m openjev_service.adapter.weights --model-dir var/openjev --offline
```

CPU-тесты используют подставной `Runtime` без Torch, CUDA, сети и весов. Зависимости для
тестирования устанавливаются в окружение существующего бэкенда:

```bash
cd backend && uv sync && cd ..
PYTHONPATH=services/openjev backend/.venv/bin/python -m unittest discover -s tests/decisions -v
backend/.venv/bin/ruff check --config services/openjev/pyproject.toml services/openjev/openjev_service tests/decisions
backend/.venv/bin/ruff format --check --config services/openjev/pyproject.toml services/openjev/openjev_service tests/decisions
```

Проверяется HTTP-контракт, кеш/изменение inputs/TTL/LRU/bytes/tokens, prefix mismatch,
целостность загрузки, microbatch и bounded queue с отменой и дедлайном. Прогрев на GPU
не заменяет проверку parity: на реальной машине сравните `/v1/nli` с `use_cache:false`
и несколько разных continuation к сохранённому context.

Проверка реального HTTP/GPU с уже готовым сервисом:

```bash
python3 services/openjev/verify_gpu.py --url http://127.0.0.1:8000 \
  --dataset evals/datasets/nli_ru_v0.json --out var/service-gpu-validation.json
```

На A100 10 октября 2026 проверен прямой Python-запуск с закреплённым runtime:
60 примеров, 21 context, полный и prepared inference — 59/60 правильных ответов,
0 изменений класса. Максимальная разница вероятностей — 0.0052522421; BF16 prepared path
не обещает битовую идентичность с полным inference. Во всех 21 проверках A→B→A повторный
ответ совпал точно. Проверены автоматическое повторное использование состояния, создание
нового context при изменении описания, удаление/404, нейтрализация внешних ID опций и
413/422 без потери readiness. Это проверка API на GPU через Python, не GPU-запуск контейнера.
Исходные результаты: [JSON](../../evals/reports/service-gpu-validation.json),
[проверка](../../evals/reports/verify-gpu.log), [лог сервиса](../../evals/reports/service-gpu.log).

## Граница модуля

Сервис отдельный от `backend/`: в `controller` находится HTTP/Pydantic, в `usecase` — сценарии,
очередь и кеш, в `usecase/interface.py` — порт `Runtime` с типизированным prepared context,
в `adapter` — GPU-модель и верифицированный загрузчик. Сборка выполнена вручную в фабрике
`controller.api.create_app`; runtime заменяется без импорта ML-библиотек в сценарии и тесты.
Ничего из `evals/` не импортируется. SQLite, каталог и основной HTTP-бэкенд этот Compose
пока не запускает. Их будущая интеграция проходит через отдельную реализацию порта decision
в `backend/app/adapter/`, обращающуюся к этому HTTP API.
