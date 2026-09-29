# Подключение RAG

Вопросы студентов работают в двух местах: кнопка «Задать вопрос по шагу» в карточке шага и любой вопрос текстом боту. Бэкенд выбирает, кто отвечает:

| Настройка | Кто отвечает | `/health` → `assistant` |
|---|---|---|
| `RAG_URL` | Полный RAG-сервис команды (`backend/app/ai`: bge-m3, Qdrant, LLM) | `rag` |
| `OLLAMA_API_KEY` (без `RAG_URL`) | Облегчённый RAG внутри бэкенда: поиск по словам (BM25) в той же базе знаний и модель в Ollama Cloud (`LLM_MODEL`, по умолчанию `gpt-oss:20b`) с тем же промптом | `rag-cloud` |
| ничего | Встроенный поиск по шагам маршрута | `stub` |

Если RAG не ответил, ответил «нет информации» или вернул ответ не по формату, отвечает встроенный поиск.

## Облегчённый RAG на Render (без отдельного сервера)

Нужен только ключ Ollama Cloud: ollama.com → Settings → Keys. В Render → Environment задайте:

- `OLLAMA_API_KEY=<ключ>`;
- `LLM_MODEL=gpt-oss:20b` (имя модели для API — без `-cloud`, список есть на `https://ollama.com/api/tags`);
- `LLM_TIMEOUT_SECONDS=30`.

После перезапуска `/health` покажет `"assistant": "rag-cloud"`. Код — `backend/app/assistant/cloud_rag.py`. База знаний и промпт общие с полным RAG: `backend/app/ai/knowledge_base` и `backend/app/ai/prompt.py`.

## RAG-помощник команды

Отдельный сервис в `backend/app/ai`, в образ «Маршрута» не входит.

- **База знаний** — `knowledge_base/**/*.json`: 47 карточек о регистрации, ОМС, проезде, Пушкинской карте и поддержке студентов. У каждой карточки есть официальный источник и дата проверки.
- **Поиск.** Эмбеддинги `BAAI/bge-m3` (sentence-transformers), векторная база Qdrant, берутся два ближайших фрагмента.
- **Ответ.** LLM через Ollama, по умолчанию `qwen3:8b`. Модель отвечает только по найденным фрагментам и сама выбирает, на какие из них сослаться. Ссылки берутся из базы знаний, модель их не придумывает. Если ответа в базе нет, сервис отвечает `204`, и тогда отвечает встроенный поиск.
- **Файлы.** `api.py` — `POST /ask` и `GET /health`; `rag.py` — поиск и генерация; `ingest.py` — загрузка базы знаний в Qdrant; `start.py` — запуск в контейнере; `Dockerfile`, `requirements.txt`.

**Запуск вместе с «Маршрутом»:**

```bash
# в .env: RAG_URL=http://rag:8090/ask и RAG_TIMEOUT_SECONDS=180
docker compose --profile rag up --build
```

Поднимаются Qdrant, Ollama и сервис `rag`. При первом старте `rag` скачивает модель в Ollama и bge-m3 (вместе около 7 ГБ) и загружает базу знаний в Qdrant. Модель задаётся переменной `LLM_MODEL`: для слабой машины подойдёт `qwen3:1.7b`.

**Скорость.** На процессоре без GPU ответ занимает около минуты (проверено на 2 CPU с `qwen3:1.7b`). Поэтому для RAG `RAG_TIMEOUT_SECONDS` нужно поднять. На проде нужен сервер с GPU или LLM по API, тогда ответ приходит за секунды.

**Модель в Ollama Cloud (рекомендуется для прода).** Если задан `OLLAMA_API_KEY`, ответ генерирует облачная модель Ollama, например `LLM_MODEL=gpt-oss:20b`, а локальная LLM не нужна. Ключ создаётся на ollama.com в настройках аккаунта. Имя модели для API — без суффикса `-cloud`: список доступных моделей отдаёт `https://ollama.com/api/tags`. На сервере остаются только эмбеддинги bge-m3 и Qdrant, это около 2 ГБ памяти. Qdrant можно не запускать отдельно: с `QDRANT_PATH` база хранится в папке внутри контейнера.

**Развёртывание на маленькой ВМ** (например, бесплатная ВМ Cloud.ru на 2 vCPU и 4 ГБ). На ВМ нужны Docker и папка `backend/app/ai`:

```bash
docker build -t marshrut-rag backend/app/ai
docker run -d --name rag --restart unless-stopped -p 8090:8090 \
  -e QDRANT_PATH=/data/qdrant -e HF_HOME=/data/models \
  -e OLLAMA_API_KEY=<ключ Ollama> -e LLM_MODEL=gpt-oss:20b \
  -e RAG_TOKEN=<случайный токен> \
  -v rag_data:/data marshrut-rag
curl http://localhost:8090/health
```

Первый старт скачивает bge-m3 (около 2,3 ГБ) и загружает базу знаний. В Render задайте `RAG_URL=http://<IP ВМ>:8090/ask`, тот же `RAG_TOKEN` и `RAG_TIMEOUT_SECONDS=30`.

**После изменения базы знаний** перезапустите сервис с `RAG_REINGEST=1` или выполните `python ingest.py` в `backend/app/ai`.

## Как подключить другой RAG-сервис

1. **Сделать в RAG-сервисе метод** `POST /ask` по контракту ниже.
2. **Проверить локально.** Можно без RAG, на фейковом сервисе:

   ```bash
   python3 tools/fake_rag.py                  # http://localhost:8090/ask
   # в .env: RAG_URL=http://host.docker.internal:8090/ask   (из Docker)
   #   или   RAG_URL=http://localhost:8090/ask              (backend без Docker)
   docker compose up --build
   curl -s localhost:8000/health              # "assistant": "rag"
   ```

   Задайте вопрос в карточке шага: ответ начнётся с `[fake RAG]`. Флаги `--delay 10` и `--fail` имитируют медленный и упавший сервис, тогда ответит заглушка.
3. **Включить на проде.** В Render → Environment задать `RAG_URL=https://<rag-сервис>/ask` и, если сервис проверяет токен, `RAG_TOKEN`. После перезапуска `/health` покажет `"assistant": "rag"`.

## Контракт

`POST RAG_URL`, заголовки `Content-Type: application/json` и, если задан `RAG_TOKEN`, `Authorization: Bearer <RAG_TOKEN>`.

**Запрос:**

```json
{
  "question": "Что взять с собой в поликлинику?",
  "lang": "ru",
  "region_code": "54",
  "region_title": "Новосибирская область",
  "citizenship": "RU",
  "university_code": "nsu",
  "step": {
    "code": "clinic_attachment",
    "title": "Прикрепление к поликлинике",
    "short_description": "Выберите поликлинику рядом с домом или вузом.",
    "full_description": "…",
    "location": "Поликлиника или Госуслуги",
    "sources": [{"title": "…", "url": "https://…", "organization": "…"}]
  },
  "route": [ { "code": "…", "title": "…", "short_description": "…", "full_description": "…", "location": "…", "sources": [] } ]
}
```

- `step` — шаг, из карточки которого задан вопрос. Для вопроса боту его нет (`null`).
- `route` — все шаги маршрута студента с официальными источниками. Их удобно использовать как контекст или фильтр поиска: регион и ситуация студента в них уже учтены.
- `lang` — `ru` или `en`, отвечать нужно на этом языке.
- Персональных данных нет: ни имени, ни MAX ID.

**Ответ `200`:**

```json
{
  "answer": "Возьмите паспорт, полис ОМС и СНИЛС…",
  "sources": [{"title": "Прикрепление к поликлинике", "url": "https://www.gosuslugi.ru/…", "organization": "Госуслуги"}],
  "step_code": "clinic_attachment"
}
```

- `answer` — обязательно, до 4000 символов, обычный текст без разметки.
- `sources` — ссылки, на которые опирается ответ. Показываются под ответом, в боте это кнопки (до трёх).
- `step_code` — необязательно. Код шага из `route`, к которому относится ответ: студент получит кнопку «Открыть шаг».
- `204` или пустой ответ — «не знаю»: тогда отвечает заглушка.

## Что будет при сбоях

| Ситуация | Что видит студент |
|---|---|
| `RAG_URL` не задан | Ответ заглушки |
| Сервис не ответил за `RAG_TIMEOUT_SECONDS` (8 с), вернул ошибку или ответ не по контракту | Ответ заглушки. В `/api/v1/ask` поле `fallback: true`, в логах предупреждение без текста вопроса |
| Больше 10 вопросов в минуту от одного студента | `429 RATE_LIMITED`, в приложении и боте — «подождите минуту». Лимит защищает RAG-сервис от лишней нагрузки |
| Ни RAG, ни заглушка не нашли ответа | Предложение открыть маршрут и раздел «Помощь» |

Бесплатный хостинг засыпает: первый вопрос после простоя может не уложиться в 8 секунд. Этот случай закрывает заглушка. Пинговать RAG-сервис стоит так же, как основной (cron-job.org).

## Где что в коде

| Файл | Что делает |
|---|---|
| `backend/app/assistant/schemas.py` | Контракт: `RagRequest`, `RagResponse`, ответ API `AskResponse` |
| `backend/app/assistant/providers.py` | `RagAssistant` (HTTP-клиент) и `StubAssistant` (заглушка) |
| `backend/app/assistant/service.py` | Сбор контекста студента и цепочка помощников `build_assistants` |
| `backend/app/api/v1/assistant.py` | `POST /api/v1/ask` |
| `backend/app/bot/handler.py` | Вопрос текстом боту → `answer_question` |
| `frontend/src/features/AskQuestion.tsx` | «Задать вопрос по шагу» в карточке шага |
| `backend/tests/test_assistant.py` | Контракт, фолбэк при ошибке и тайм-ауте, бот |
| `tools/fake_rag.py` | Фейковый RAG-сервис для локальной проверки |

Другой движок (не HTTP) подключается так же: класс с методом `answer(RagRequest) -> RagResponse | None` добавляется в `build_assistants`.
