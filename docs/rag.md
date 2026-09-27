# Подключение RAG

Вопросы студентов уже работают: кнопка «Задать вопрос по шагу» в карточке шага и любой вопрос текстом боту. Сейчас отвечает встроенная заглушка: она находит шаг маршрута, о котором вопрос, и отвечает его текстом и официальными источниками. Чтобы отвечал RAG, достаточно поднять сервис с одним методом и указать его адрес в `RAG_URL`. Код «Маршрута» менять не нужно.

## Как подключить

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
