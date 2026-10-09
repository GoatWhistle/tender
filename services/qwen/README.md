# Qwen embeddings и strict извлечение

Сервисы для `Qwen/Qwen3-Embedding-0.6B` и `Qwen/Qwen3.5-4B` работают рядом с
OpenJev. Модели и лицензии закреплены в `model-manifest.json`; приложение не
получает CUDA-зависимости. Экстрактор возвращает предложения фактов: принятие
и проверка истинности через decision-модель подключаются в приложении отдельно.
Профиль `profiles/9b/` заменяет экстрактор на `Qwen/Qwen3.5-9B`, сохраняя embedding-модель.
9B проверен рядом с OpenJev на A100 40 ГиБ: пик трёх моделей 35.71 ГиБ при
16 клиентах по ~7.4K токенов. Итоговые замеры и ограничения —
[`evals/reports/2026-10-10-qwen/README.md`](../../evals/reports/2026-10-10-qwen/README.md).

## Чистая Linux-машина

Нужны Linux x86-64, NVIDIA GPU, совместимый драйвер, Docker Engine с Compose v2
и NVIDIA Container Toolkit. Проверенный профиль — одна A100 40 ГБ; значения
`gpu-memory-utilization` относятся ко всей карте, а не к остаткам свободной памяти.
Для другого GPU бюджеты нужно пересчитать. Интернет нужен для сборки образов
и первичной загрузки; для анализа скачанные веса доступны офлайн.

Из корня репозитория:

```sh
docker compose -f compose.yaml -f compose.qwen.yaml --profile gpu build
docker compose -f compose.yaml -f compose.qwen.yaml --profile download run --rm qwen-download
docker compose -f compose.yaml --profile gpu run --rm --entrypoint python openjev \
  -m openjev_service.adapter.weights --model-dir /models/openjev
docker compose -f compose.yaml -f compose.qwen.yaml --profile gpu up -d \
  openjev qwen-embedding qwen-extractor
```

Внутренний `qwen-engine` поднимется автоматически после прогрева embedding-сервиса.
Постоянный том `qwen-weights` хранит две Qwen; кеши компиляции разделены.
`openjev-weights` обслуживает существующий decision-сервис. Повторный запуск
проверяет SHA256 весов и конфигурации. Корректные веса не скачиваются повторно.
Не удалять тома командой `down -v`, если нужно сохранить веса.

```sh
curl --fail http://localhost:8000/health/ready  # OpenJev, OPENJEV_PORT меняет порт
curl --fail http://localhost:8081/health
curl --fail http://localhost:8082/health/ready
docker compose -f compose.yaml -f compose.qwen.yaml --profile gpu logs --tail 100
```

Все внешние порты привязаны к `127.0.0.1`. vLLM экстрактора доступен только внутри
Compose-сети: обращаться к публичному strict API, чтобы получить проверку схемы
и законченного ответа. Ошибки слишком длинного prompt возвращает движок,
усечение не включено. Контекст embeddings — 4096, экстрактора — 8192 токена,
включая ответ; API разрешает до 2048 токенов ответа.

## Профиль 9B

Для 9B добавить `compose.qwen-9b.yaml` последним. Профиль использует отдельный том
весов, отдельный кеш компиляции экстрактора и GPU-бюджет 0.60 вместо 0.35.
Оба профиля закрепляют BF16 и отключают vision; одновременно запускать два
экстрактора на проверенной A100 40 ГБ нельзя.

```sh
docker compose -f compose.yaml -f compose.qwen.yaml -f compose.qwen-9b.yaml --profile gpu build
docker compose -f compose.yaml -f compose.qwen.yaml -f compose.qwen-9b.yaml \
  --profile download run --rm qwen-download
docker compose -f compose.yaml -f compose.qwen.yaml -f compose.qwen-9b.yaml \
  --profile gpu up -d openjev qwen-embedding qwen-extractor
```

При первом запуске подготовить веса OpenJev командой из основного профиля выше.
Вернуться к 4B: подготовить основной том весов и повторить `up`, убрав последний
`-f compose.qwen-9b.yaml`. Имена API и порты сохраняются; реальная ревизия модели
возвращается в readiness и `/v1/models`.

## Embeddings

```sh
curl --fail http://localhost:8081/v1/embeddings -H 'Content-Type: application/json' \
  -d '{"model":"qwen-embedding","input":["Instruct: Retrieve matching product categories.\nQuery: Деревянный стол","Стол письменный"]}'
```

Векторы — 1024 float, last-token pooling, L2-нормализация. Документы индексируются
без query instruction. Поисковые запросы используют английскую инструкцию
`Instruct: ...\nQuery: ...`; версия инструкции должна участвовать в ключе индекса.
Замена модели и инструкции требует перестроения векторного индекса.

## Strict JSON Schema

`POST /v1/chat/completions` принимает OpenAI-совместимый запрос с
`response_format.type=json_schema` и `json_schema.strict=true`.
`additionalProperties=false` и перечисление всех полей в `required` обязательны
для каждого object. Необязательное значение выражается nullable типом.
Поддерживаемый набор: `type`, `properties`, `required`, `additionalProperties`,
`items`, `enum`, `anyOf`, локальные `$defs`/`$ref`, `title`, `description`.
Другие keywords возвращают 422, чтобы не создавать ложной гарантии strict.
Streaming и tools в этом API отключены.

Движок использует XGrammar constrained decoding; API дополнительно проверяет
схему и `finish_reason=stop`. Обрезанный ответ или нарушение схемы — 502,
невалидный запрос — 422, заполненная очередь — 429, недоступный движок — 503.
Readiness включает реальную генерацию по закрытой схеме, а не только загрузку GPU.

```sh
curl --fail http://localhost:8082/v1/chat/completions \
  -H 'Content-Type: application/json' -d '{
  "model":"qwen-extractor",
  "messages":[{"role":"user","content":"Высота стола 70 см. Извлеки высоту."}],
  "max_tokens":128,
  "response_format":{"type":"json_schema","json_schema":{
    "name":"height","strict":true,"schema":{
      "type":"object","additionalProperties":false,"required":["height_cm"],
      "properties":{"height_cm":{"type":"integer"}}
    }
  }}
}'
```

Специализированный endpoint принимает исходные сообщения, принятые факты и
ограниченный набор целевых полей:

```sh
curl --fail http://localhost:8082/v1/extract -H 'Content-Type: application/json' -d '{
  "messages":[{"id":"m1","text":"Высота стола 70 см."}],
  "targets":[{"attribute_ref":"height","description":"Высота стола","subject_ref":"table"}],
  "accepted_facts":[]
}'
```

Факт содержит `attribute_ref`, `raw_value`, `raw_unit`, `source_quote`,
`source_message_id`, `negated`, `uncertain`, `subject_ref`.
Экстрактор дополнительно видит схему в prompt; `raw_value` — значение,
`raw_unit` — единица измерения или null. Схема одновременно ограничивает decoding.
Схема ограничивает ID допустимыми enum. API проверяет пару field/subject и
дословное присутствие непустой цитаты в указанном сообщении. Пустой список
`facts` допустим. Ответ всегда имеет `status=proposed`: schema strict не
проверяет смысл извлечения, совместимость единиц и актуальность после исправлений.

## Vast: запуск в существующем контейнере

В непривилегированном Vast-контейнере Docker-in-Docker недоступен. Тот же
`launch.sh` работает с отдельным venv под supervisor. Перед установкой прочитать
`/etc/vast-agents-guide.md`. В примере `$QWEN_ROOT` — выбранная папка сервиса:

```sh
QWEN_ROOT=/workspace/qwen-services
mkdir -p "$QWEN_ROOT"
cp services/qwen/*.py services/qwen/*.json services/qwen/launch.sh "$QWEN_ROOT/"
uv venv --python /venv/main/bin/python "$QWEN_ROOT/.venv"
uv pip install --python "$QWEN_ROOT/.venv/bin/python" -r services/qwen/requirements.lock.txt
"$QWEN_ROOT/.venv/bin/python" "$QWEN_ROOT/download.py" --root "$QWEN_ROOT/models"
"$QWEN_ROOT/.venv/bin/python" "$QWEN_ROOT/install_supervisor.py" --root "$QWEN_ROOT"
supervisorctl status qwen-embedding qwen-engine qwen-extractor
```

На стенде OpenJev использует 8080, embeddings — 8081, strict extractor — 8082;
внутренний engine — 8083. Доступ через SSH:

```sh
ssh -N -p 21205 root@38.255.16.69 \
  -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 -L 8082:127.0.0.1:8082
```

Если локальный порт занят, поменять левую часть `-L` и адрес клиента.
Supervisor перезапускает сервисы при падении; логи — `/var/log/portal/qwen-*.log`.

Для переключения supervisor на 9B скопировать также `services/qwen/profiles/`
в `$QWEN_ROOT/profiles/`, загрузить отдельный каталог и перезапустить экстрактор:

```sh
QWEN_MANIFEST_DIR="$QWEN_ROOT/profiles/9b" "$QWEN_ROOT/.venv/bin/python" \
  "$QWEN_ROOT/download.py" --root "$QWEN_ROOT/models-9b"
"$QWEN_ROOT/.venv/bin/python" "$QWEN_ROOT/install_supervisor.py" \
  --root "$QWEN_ROOT" --profile 9b
supervisorctl restart qwen-engine qwen-extractor
```

Откат: installer с `--profile 4b`, затем тот же restart. Уже загруженные модели
не удаляются. Настройки OpenJev не меняются.

## Локальный backend с удалёнными моделями

Backend остаётся на пользовательской машине. Модельные порты пробрасываются
через SSH с `ServerAliveInterval=30`, `ServerAliveCountMax=3`, `BatchMode=yes` и
`ExitOnForwardFailure=yes`; менеджер процессов перезапускает SSH после разрыва.
На macOS это LaunchAgent с `RunAtLoad=true`, `KeepAlive=true`, `ThrottleInterval=10`.
Настройки машины и пути к ключам сохраняются вне Git.

Развёрнутый локальный профиль использует свободные порты:

| Назначение | Локальный URL | Серверный порт |
| --- | --- | --- |
| Backend и каталог | `http://127.0.0.1:18085` | локальный процесс |
| OpenJev | `http://127.0.0.1:18080` | 8080 |
| Embeddings | `http://127.0.0.1:18083/v1` | 8081 |
| Strict extractor | `http://127.0.0.1:18084/v1` | 8082 |

```sh
launchctl print gui/$(id -u)/ru.tender.models-tunnel
launchctl kickstart -k gui/$(id -u)/ru.tender.models-tunnel
launchctl print gui/$(id -u)/ru.tender.backend
curl --fail http://127.0.0.1:18085/health/ready
```

Runtime локального backend и файл `model-endpoints.json` лежат в игнорируемом
`var/local-stack/`; API-документация — `/api/docs`. Текущий backend обслуживает
каталог. Автоматическое обращение к моделям подключают продуктовые адаптеры
поиска и извлечения; наличие URL не означает реализации этих сценариев.

## Проверки

CPU, без GPU и весов (нужны fastapi/httpx/jsonschema):

```sh
PYTHONPATH=services/qwen python3 -m unittest discover -s tests/qwen -v
python3 -m ruff check --config backend/pyproject.toml services/qwen tests/qwen
python3 -m ruff format --check --config backend/pyproject.toml services/qwen tests/qwen
docker compose -f compose.yaml -f compose.qwen.yaml --profile gpu --profile download config --quiet
```

На сервере, когда три модели готовы:

```sh
python3 services/qwen/verify_gpu.py --out /tmp/qwen-gpu-check.json --repeats 20
```

Этот короткий набор проверяет формат, цитаты и производительность; он не заменяет
продуктовые eval retrieval и verifier. Сохраняются все latency samples, условия,
ответы и совокупная VRAM. Prefix-cache замер использует повторяемый prompt, а
не независимый test-набор.

Источники: [Qwen embeddings](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B),
[Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B),
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B),
[vLLM structured outputs](https://docs.vllm.ai/en/v0.22.1/features/structured_outputs/).
