# Архитектура

Модульный монолит. Один процесс FastAPI:

- отдаёт API `/api/v1` и собранное мини-приложение (одинаковый origin, один HTTPS-адрес, без CORS);
- принимает события бота MAX (`POST /max/webhook` или long polling);
- раз в час рассылает напоминания о шагах, у которых приближается рекомендуемый срок.

## Поток данных

```text
Анкета (6 ответов) ─► UserProfile ─► UserContext
                                        │
data/scenarios/*.json ─seed─► Scenario, ScenarioStep, Rule, Source, Document
                                        │
                           RouteGenerator.generate(context, scenario)
                           (все правила шага через AND, сортировка по position)
                                        │
                           UserRoute + UserRouteStep (deadline = создание + recommended_days)
                                        │
                  API: прогресс, карточка шага, complete / reopen
                                        │
                  NotificationService ─► MessageSender ─► MAXClient ─► MAX
```

## Слои и зависимости

| Слой | Модули | Зависит от |
|---|---|---|
| Домен | `rules/`, `scenarios/engine.py`, `scenarios/schemas.py` | только Pydantic |
| Приложение | `routes/service.py`, `users/service.py`, `auth/service.py`, `notifications/service.py` | домен, репозитории |
| Инфраструктура | `*/repository.py`, `core/database.py`, `integrations/max/`, `notifications/max_sender.py` | SQLAlchemy, httpx |
| Транспорт | `api/`, `main.py`, `bot/` | FastAPI |

Правила:

- Rule Engine детерминирован и строго типизирован: `18` ≠ `"18"`, `false` ≠ `0`. Ошибки типов ловятся при загрузке сценария, а не во время запроса.
- Бизнес-сервисы не вызывают MAX API: уведомления идут через протокол `MessageSender`. Без токена бота используется `NullSender`, и API работает без MAX.
- Уведомления из API отправляются фоновой задачей после ответа, поэтому медленный или недоступный MAX не задерживает запросы пользователя.

## Аутентификация

1. Мини-приложение получает `window.WebApp.initData` через `shared/max/maxBridge.ts`.
2. `POST /api/v1/auth/max` проверяет подпись: `secret = HMAC_SHA256("WebAppData", BOT_TOKEN)`, `hash = HMAC_SHA256(secret, отсортированные параметры через \n)`, а также срок `auth_date` (24 часа).
3. Backend создаёт пользователя по `user.id` из подписанных данных и выдаёт токен `base64(payload).HMAC` со сроком 7 дней.
4. Для автоматической проверки API используются тестовые токены из `TEST_ACCESS_TOKENS`, каждый привязан к отдельному `max_user_id`.
5. Dev-вход (`DEV_AUTH_ENABLED`) работает только при `APP_ENV` ≠ `production`.

## Бот

| Событие | Ответ |
|---|---|
| `bot_started`, `/start` | Приветствие и кнопка «Открыть маршрут». Payload с кодом вуза (`?start=kfu`) добавляет вуз в анкету |
| `message_callback` `done:<step_id>` | Кнопка «✅ Выполнено»: шаг отмечается (`completed_via=chat`), сообщение меняется на подтверждение, приходит следующий шаг |
| `/next` | Следующий шаг с кнопкой, открывающей этот шаг (`payload=step_<id>`) |
| прочее | Подсказка по командам |
| маршрут построен / шаг выполнен / маршрут завершён | Сообщение со следующим шагом или поздравление |
| срок шага наступает в течение суток | Одно напоминание на шаг (`reminded_at`) |

Если MAX отклоняет кнопку `open_app` (например, мини-приложение ещё не привязано к боту), сообщение отправляется повторно с обычной ссылкой, и уведомление всё равно доходит.

## Выбор сценария

Каждый сценарий содержит `audience` — правила на `UserContext`. `ScenarioService.get_for` берёт первый активный сценарий, чьи правила совпали. Так `student_relocation_v1` (`citizenship EQ RU`) и `foreign_student_v1` (`citizenship EQ FOREIGN`) работают на одном движке.

## Масштабирование

Новый регион или категория пользователей добавляются данными: шаги, правила, источники и документы в JSON сценария. Опубликованная версия сценария не меняется — выпускается новая `version`, а старые маршруты продолжают ссылаться на свои шаги.
