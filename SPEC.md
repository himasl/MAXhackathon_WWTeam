# SPEC.md --- «Маршрут»

> **Обновлено 23.09.2026** после разбора материалов хакатона: добавлен раздел 43
> (требования к сдаче, критерии оценки, деплой, обновлённый порядок этапов). Где разделы
> 1–42 расходятся с разделом 43, действует раздел 43.

## 1. Общая информация

Рабочее название проекта: **«Маршрут»**.

Проект создаётся для хакатона по треку «Забота о людях».

Основной продукт --- чат-бот MAX с подключённым Mini App.

Основной MVP-сценарий: персональный навигатор для студента ---
гражданина РФ, который переехал в другой регион для обучения и должен
разобраться с административными и социальными действиями после переезда.

Примеры действий: - регистрация; - прикрепление к поликлинике; -
региональные/студенческие меры поддержки; - транспортные льготы; -
взаимодействие с МФЦ; - необходимые документы; - сроки; - следующие
действия.

**Важно:** - продукт НЕ является государственным сервисом; - продукт НЕ
принимает юридически значимые решения; - продукт НЕ гарантирует право
пользователя на льготу; - продукт помогает человеку построить маршрут
действий на основании официальных источников и заданных правил; - для
MVP допускаются демонстрационные данные; - каждый источник данных должен
иметь признак происхождения: `official / mock / calculated`.

## 2. Главная продуктовая гипотеза

### Problem

Студент, впервые переехавший в другой регион для обучения, сталкивается
с информацией из разных источников.

Ему приходится самостоятельно выяснять: - что необходимо сделать; - в
каком порядке; - какие документы понадобятся; - какие действия относятся
именно к его ситуации; - куда обращаться; - какие существуют сроки; -
какие действия уже выполнены; - что делать дальше.

### Solution

Пользователь отвечает на несколько вопросов.

На основании `UserContext` система строит персональный маршрут:

``` text
UserContext
    ↓
Rules Engine
    ↓
Scenario
    ↓
Personalized Route
    ↓
Route Steps
```

Каждый шаг содержит: - название; - описание; - причину появления; -
список документов; - срок; - официальный источник; - место выполнения; -
статус; - следующий шаг.

Пользователь может отмечать шаги выполненными.

MAX-бот сообщает пользователю: - следующий шаг; - приближение срока; -
изменение маршрута; - завершение маршрута.

Mini App используется для просмотра и управления маршрутом.

## 3. Главный User Flow

Обязательный end-to-end сценарий:

``` text
Пользователь открывает MAX-бот
            ↓
          /start
            ↓
«Поможем разобраться, что нужно
 сделать после переезда»
            ↓
       [Начать маршрут]
            ↓
       открывается Mini App
            ↓
         onboarding
            ↓
В какой регион переехали?
            ↓
         возраст
            ↓
      форма обучения
            ↓
общежитие / квартира / родственники
            ↓
есть ли временная регистрация
            ↓
есть ли прикрепление к поликлинике
            ↓
       Generate Route
            ↓
      персональный маршрут
```

Пример результата:

``` text
Ваш маршрут

2 из 6 выполнено

██████░░░░ 33%

✓ Переезд
✓ Заселение

● Временная регистрация
  Желательно проверить до 25 сентября
  [Подробнее]

○ Прикрепление к поликлинике
○ Студенческий проездной
○ Доступные меры поддержки
```

## 4. Архитектура

Использовать **Modular Monolith**. Не реализовывать микросервисы.

``` text
                    MAX
                     │
          ┌──────────┴──────────┐
          │                     │
      MAX Bot               MAX Mini App
          │                     │
          │                  React
          │                     │
          └──────────┬──────────┘
                     │
                     ▼
                  FastAPI
                     │
            Application Layer
                     │
       ┌─────────────┼─────────────┐
       │             │             │
       ▼             ▼             ▼
Scenario Engine   User Service   Route Service
       │
       ▼
Rules Engine
       │
       ▼
Repositories
       │
       ▼
PostgreSQL
```

Внешние интеграции:

``` text
Application
    │
    └── Integration Interfaces
             │
             ├── MAX
             ├── Government Data
             └── Notifications
```

Главное правило:

> Domain logic MUST NOT depend directly on MAX API, FastAPI, PostgreSQL
> or external government services.

## 5. Стек

### Backend

-   Python 3.13
-   FastAPI
-   Pydantic v2
-   SQLAlchemy 2
-   Alembic
-   PostgreSQL
-   httpx

### Frontend

-   React
-   TypeScript
-   Vite
-   MAX UI
-   MAX Bridge

### Infrastructure

-   Docker
-   Docker Compose

### Testing

-   pytest
-   pytest-asyncio
-   httpx

### Quality

-   ruff
-   mypy

Не добавлять зависимости без конкретной причины.

## 6. Структура репозитория

``` text
/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── users/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   ├── scenarios/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   ├── service.py
│   │   │   └── engine.py
│   │   ├── routes/
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── repository.py
│   │   │   └── service.py
│   │   ├── rules/
│   │   │   ├── engine.py
│   │   │   ├── evaluator.py
│   │   │   └── schemas.py
│   │   ├── sources/
│   │   │   ├── models.py
│   │   │   └── repository.py
│   │   ├── notifications/
│   │   │   └── service.py
│   │   ├── integrations/
│   │   │   ├── max/
│   │   │   │   ├── client.py
│   │   │   │   ├── webhook.py
│   │   │   │   └── schemas.py
│   │   │   └── government/
│   │   │       ├── base.py
│   │   │       ├── mock.py
│   │   │       └── real.py
│   │   └── api/
│   │       └── v1/
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── pages/
│   │   ├── features/
│   │   ├── entities/
│   │   └── shared/
│   ├── Dockerfile
│   └── package.json
├── data/
│   └── scenarios/
├── docs/
│   ├── architecture.md
│   └── demo.md
├── compose.yaml
├── .env.example
├── .gitignore
├── README.md
└── SPEC.md
```

## 7. Модель данных

### users

``` text
users

id                  UUID PK
max_user_id         BIGINT UNIQUE
created_at          TIMESTAMP
updated_at          TIMESTAMP
```

Не хранить лишние ФИО, паспорт и другие ненужные персональные данные.

### user_profiles

``` text
user_profiles

id
user_id
age
region_code
education_type
housing_type
has_registration
has_clinic_attachment
created_at
updated_at
```

Enums:

``` text
education_type:
FULL_TIME
PART_TIME

housing_type:
DORMITORY
RENT
RELATIVES
OTHER
```

## 8. Scenario

``` text
scenarios

id
code
title
description
version
is_active
created_at
updated_at
```

MVP code:

``` text
student_relocation_v1
```

## 9. ScenarioStep

``` text
scenario_steps

id
scenario_id
code
title
short_description
full_description
position
category
estimated_duration
is_required
created_at
updated_at
```

Категории:

``` text
REGISTRATION
HEALTHCARE
EDUCATION
TRANSPORT
SOCIAL_SUPPORT
OTHER
```

## 10. Rules

Правила не должны быть размазаны `if`-ами по backend.

``` text
rules

id
scenario_step_id
field
operator
value
created_at
```

Поддерживаемые операторы:

``` text
EQ
NE
GT
GTE
LT
LTE
IN
NOT_IN
```

Пример:

``` json
{
  "field": "housing_type",
  "operator": "EQ",
  "value": "DORMITORY"
}
```

## 11. Rule Engine

Реализовать детерминированную оценку правил.

**Не использовать LLM для определения eligibility.**

``` text
evaluate(rule, context) -> bool
```

Пример context:

``` json
{
  "age": 18,
  "region_code": "77",
  "education_type": "FULL_TIME",
  "housing_type": "DORMITORY",
  "has_registration": false
}
```

Rule:

``` json
{
  "field": "has_registration",
  "operator": "EQ",
  "value": false
}
```

Результат: `true`.

## 12. Route Generation

``` text
RouteService.generate_route(user_id)
```

Алгоритм: 1. load user profile; 2. load active scenario; 3. load
scenario steps; 4. load rules; 5. evaluate rules against UserContext; 6.
include applicable steps; 7. sort steps; 8. create UserRoute; 9. create
UserRouteSteps; 10. return route.

## 13. UserRoute

``` text
user_routes

id
user_id
scenario_id
scenario_version
status
created_at
completed_at
```

Status:

``` text
ACTIVE
COMPLETED
ARCHIVED
```

## 14. UserRouteStep

``` text
user_route_steps

id
route_id
scenario_step_id
position
status
deadline
completed_at
created_at
updated_at
```

Status:

``` text
TODO
IN_PROGRESS
DONE
SKIPPED
```

## 15. Документы

``` text
documents

id
code
title
description
```

Связь:

``` text
scenario_step_documents

scenario_step_id
document_id
required
```

## 16. Источники

``` text
sources

id
title
url
organization
source_type
region_code
published_at
checked_at
created_at
```

Типы:

``` text
OFFICIAL
MOCK
OTHER
```

Связь:

``` text
scenario_step_sources
```

Каждый шаг должен показывать источник и дату проверки.

## 17. API

Все endpoint'ы под `/api/v1`, кроме health endpoint.

### Health

``` http
GET /health
```

``` json
{
  "status": "ok"
}
```

### Current user

``` http
GET /api/v1/me
```

### Profile

``` http
GET /api/v1/profile
PUT /api/v1/profile
```

Пример:

``` json
{
  "age": 18,
  "region_code": "77",
  "education_type": "FULL_TIME",
  "housing_type": "DORMITORY",
  "has_registration": false,
  "has_clinic_attachment": false
}
```

### Generate route

``` http
POST /api/v1/routes
```

### Current route

``` http
GET /api/v1/routes/current
```

### Route step

``` http
GET /api/v1/routes/{route_id}/steps/{step_id}
```

### Complete step

``` http
POST /api/v1/routes/{route_id}/steps/{step_id}/complete
```

### Reopen

``` http
POST /api/v1/routes/{route_id}/steps/{step_id}/reopen
```

## 18. Frontend

Основная навигация должна быть простой. Не создавать большое количество
разделов.

Основные области: - Маршрут; - Поддержка.

## 19. Экран Welcome

``` text
Добро пожаловать 👋

Разберёмся, что нужно сделать
после переезда на учёбу.

Ответьте на несколько вопросов,
и мы составим персональный
маршрут действий.

Это займёт около минуты.

[Составить маршрут]
```

## 20. Onboarding

Использовать wizard, а не одну большую форму.

Пример:

``` text
1 / 5

Куда вы переехали?

[ Москва ]
[ Санкт-Петербург ]
[ Татарстан ]
[ Другой регион ]

                [Далее]
```

Показывать progress.

## 21. Route Screen

``` text
Добрый день 👋

Ваш маршрут

2 из 6 выполнено

██████░░░░ 33%

✓ Заселение
  Выполнено

● Временная регистрация
  Следующий шаг
  Подготовьте необходимые документы.
  [Открыть]

○ Прикрепление к поликлинике
○ Студенческий проездной
○ Меры поддержки
```

## 22. Step Screen

Обязательные блоки: - название; - «Почему этот шаг появился?»; - что
сделать; - документы; - куда обратиться; - источник; - дата проверки
источника; - ссылка на официальный источник; - кнопка завершения шага.

Пример объяснения:

``` text
Почему этот шаг появился?

Вы указали, что переехали
для обучения и пока не имеете
регистрации.
```

## 23. Completion

``` text
🎉 Маршрут завершён

Все необходимые действия
из вашего маршрута выполнены.

6 / 6

[Посмотреть маршрут]
```

## 24. MAX Bot

Бот не должен дублировать Mini App.

Responsibilities: - entry point; - notifications; - reminders; - next
action; - deep links into Mini App.

`/start`:

``` text
Привет!

Я помогу разобраться, что нужно
сделать после переезда на учёбу.

Составим персональный маршрут:
от документов до доступных
студенческих возможностей.

[Открыть маршрут]
```

## 25. Уведомления

Пример:

``` text
Напоминание

В вашем маршруте есть следующий шаг:

«Временная регистрация»

Посмотрите необходимые документы
и порядок действий.

[Открыть шаг]
```

На MVP не делать сложный scheduler. Достаточно простого notification
service и демонстрационного механизма.

## 26. MAX Integration

Создать `MAXClient`.

Responsibilities:

``` text
send_message()
send_notification()
create_subscription()
delete_subscription()
```

Никогда не вызывать MAX API напрямую из business services.

Base API URL должен быть configurable.

Токен должен поступать только из environment variables:

``` text
MAX_BOT_TOKEN
```

События:

``` text
MAX
 ↓
Webhook
 ↓
FastAPI
 ↓
MAX Event Handler
 ↓
Application
```

## 27. MAX Mini App authentication

Не доверять `user_id`, присланному frontend.

Frontend получает MAX initialization data и передаёт их backend. Backend
валидирует данные MAX. Только после успешной валидации пользователь
создаётся/авторизуется.

Development mode может использовать:

``` text
DEV_MAX_USER_ID
```

DEV authentication не должен быть включён в production.

## 28. Frontend MAX adapter

Не использовать `window.WebApp` по всему React-коду.

Создать:

``` text
shared/max/maxBridge.ts
```

API:

``` typescript
interface MaxBridge {
    getInitData(): string | null;
    getPlatform(): string;
    openLink(url: string): void;
}
```

Browser dev-версия должна запускаться без MAX.

## 29. Mock Mode

`.env`:

``` text
DATA_MODE=mock
```

Government provider:

``` python
class GovernmentProvider(Protocol):

    async def get_services(...):
        ...

    async def get_service(...):
        ...
```

Implementations:

``` text
MockGovernmentProvider
RealGovernmentProvider
```

MVP использует `MockGovernmentProvider`.

## 30. Scenario configuration

Сценарии хранить отдельно от Python-кода:

``` text
data/scenarios/student_relocation_v1.json
```

Пример:

``` json
{
  "code": "student_relocation_v1",
  "version": 1,
  "steps": [
    {
      "code": "temporary_registration",
      "title": "Проверьте вопрос регистрации",
      "category": "REGISTRATION",
      "rules": [
        {
          "field": "has_registration",
          "operator": "EQ",
          "value": false
        }
      ]
    }
  ]
}
```

Новый регион или сценарий должен добавляться без изменения Rule Engine.

## 31. Масштабируемая архитектура

``` text
CORE

UserContext
Scenario
RuleEngine
RouteGenerator
RouteProgress
       │
       │ одинаковые
       ▼

VARIABLE DATA

Scenario definitions
Rules
Sources
Regional requirements
Documents
Translations
Integrations
```

## 32. Обработка ошибок

Единый формат API:

``` json
{
  "error": {
    "code": "ROUTE_NOT_FOUND",
    "message": "Route was not found"
  }
}
```

Frontend обязан иметь: - loading; - empty; - success; - error.

После ошибки пользователь не должен терять маршрут.

## 33. Security

-   Never commit secrets.
-   Обязательны `.env.example` и `.gitignore`.
-   Secrets: `MAX_BOT_TOKEN`, `DATABASE_URL`, `WEBHOOK_SECRET`.
-   Не собирать паспортные данные.
-   Не собирать медицинские записи.
-   Не логировать персональную информацию без необходимости.
-   Никогда не логировать MAX tokens.
-   Не отдавать stack traces через API.

## 34. Docker

Весь проект должен запускаться одной командой:

``` bash
docker compose up --build
```

Services:

``` text
postgres
backend
frontend
```

Postgres healthcheck обязателен. Backend должен корректно дождаться
готовности БД.

## 35. .env.example

``` env
APP_ENV=development

DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/marshrut

MAX_BOT_TOKEN=
MAX_API_URL=https://platform-api2.max.ru

DATA_MODE=mock

DEV_AUTH_ENABLED=true
DEV_MAX_USER_ID=123456

FRONTEND_URL=http://localhost:5173
```

## 36. Tests

Минимум:

``` text
tests/

test_rule_engine.py
test_route_generation.py
test_profile.py
test_route_progress.py
test_sources.py
test_health.py
```

Обязательный E2E/API scenario:

``` text
create user
    ↓
save profile
    ↓
generate route
    ↓
route contains expected steps
    ↓
complete step
    ↓
progress changed
    ↓
complete all
    ↓
route == COMPLETED
```

## 37. Seed Data

Создать демонстрационные данные минимум для: - Москвы; -
Санкт-Петербурга; - Татарстана.

Не придумывать реальные юридические требования.

Если официальные данные ещё не внесены командой:

``` text
source_type = MOCK
```

Интерфейс должен показывать:

``` text
Демонстрационные данные
```

## 38. Что НЕ делать

Не реализовывать в MVP: - microservices; - Kafka; - RabbitMQ; -
Kubernetes; - complex event sourcing; - Redis без обоснованной
необходимости; - vector database; - RAG; - LLM agents; - OCR; - document
recognition; - Gosuslugi authorization; - fake Gosuslugi API; - medical
diagnosis; - automatic legal decisions; - admin panel; - native mobile
application.

Не имитировать реальные государственные интеграции.

## 39. README

README должен содержать:

``` text
# Маршрут

## Problem
## Solution
## Target audience
## User scenario
## Architecture
## Technology stack
## Repository structure
## Local development
## Docker
## Environment variables
## MAX configuration
## API
## Data
## Mock data
## Testing
## Demo scenario
## Known limitations
## Scaling
```

## 40. Definition of Done

Фича считается законченной только если:

``` text
✓ работает
✓ имеет обработку ошибок
✓ имеет типы
✓ покрыта нужными тестами
✓ API документирован
✓ frontend имеет loading/error
✓ Docker продолжает собираться
✓ секреты не появились в Git
✓ README обновлён при необходимости
```

## 41. Порядок разработки

Codex НЕ должен пытаться реализовать всё за один prompt.

### Этап 0 --- Bootstrap

Создать: - backend; - frontend; - PostgreSQL; - Docker; - Docker
Compose; - `.env.example`; - README; - health endpoint.

Результат:

``` bash
docker compose up --build
```

запускает весь проект.

**STOP.**

### Этап 1 --- Database

Реализовать: - SQLAlchemy async; - Alembic; - User; - UserProfile; -
Scenario; - ScenarioStep; - Rule; - Source; - UserRoute; -
UserRouteStep; - первую migration.

**STOP.**

### Этап 2 --- Scenario Engine

Реализовать: - UserContext; - Rule evaluator; - Scenario loader; - Route
generator; - обязательные тесты.

**STOP.**

### Этап 3 --- API

Реализовать: - profile; - scenario; - route; - route steps; -
progress; - sources; - OpenAPI.

**STOP.**

### Этап 4 --- Seed

Создать: - `student_relocation_v1`; - mock scenario; - mock sources; -
demo user.

**STOP.**

### Этап 5 --- Frontend

Реализовать: - Welcome; - Onboarding; - Route; - Step; - Completion.

Пока использовать обычный browser mode.

**STOP.**

### Этап 6 --- MAX Bridge

Реализовать: - MAX adapter; - init data; - authentication; - open
links; - platform detection.

**STOP.**

### Этап 7 --- MAX Bot

Реализовать: - `/start`; - open Mini App; - webhook; - notifications.

**STOP.**

### Этап 8 --- Error handling

Реализовать: - backend exceptions; - frontend errors; - retry; - empty
states; - 404; - integration unavailable.

**STOP.**

### Этап 9 --- Tests

Полностью прогнать:

``` text
pytest
ruff
mypy
npm build
docker compose build
```

**STOP.**

### Этап 10 --- Hackathon readiness

Проверить: - README; - Docker; - `.env.example`; - OpenAPI; - demo
data; - demo scenario; - отсутствие secrets; - clean repository; -
reproducible build.

## 42. Правила работы Codex

Перед реализацией каждой задачи:

1.  Прочитать `SPEC.md`.
2.  Изучить текущее состояние репозитория.
3.  Определить затрагиваемые модули.
4.  Составить короткий implementation plan.
5.  Реализовать минимальное законченное изменение.
6.  Запустить релевантные тесты.
7.  Запустить lint/type checks, если они доступны на текущем этапе.
8.  Перечислить изменённые файлы.
9.  Перечислить выполненные команды.
10. Сообщить об оставшихся ограничениях.
11. Остановиться перед следующим этапом.

Codex не должен: - переписывать несвязанный код; - молча менять API
contracts; - добавлять зависимости без необходимости; - реализовывать
speculative features; - заранее реализовывать следующие этапы; -
усложнять архитектуру без требования из SPEC.

При неоднозначности использовать самое простое решение, соответствующее
SPEC.


## 43. Требования хакатона и обновлённый план

### 43.1 Допуск (0 баллов, если не выполнено)

-   Бот или мини-приложение запускается в MAX (мобильная **и** веб-версия), основной
    сценарий проходится до конца.
-   Мини-приложение подключено к боту, а не изолировано; открывается только по HTTPS.
-   Есть презентация (PDF). Первый слайд --- техническая информация: ссылка на бота,
    репозиторий и commit hash, адрес API, тестовые токены, порядок прохождения сценария.

### 43.2 Как оценивают онлайн-этап

-   Продукт, 40%: масштабирование 35%, ценность 25%, UX/UI 20%, целостность 15%,
    презентация 5%.
-   Техника, 60%: работоспособность 30%, интеграция и обмен данными 20%, архитектура 20%,
    стабильность и ошибки 10%, безопасность и данные 10%, документация 10%.
-   Бонус +0,15 за использование MAX сверх минимума, которое полезно и работает от
    начала до конца. Для нас это напоминания о сроках и deep link из сообщения бота в
    конкретный шаг Mini App (`open_app` + `payload=step_<id>`).

### 43.3 Собственное API

Backend заявляется как собственное API, поэтому к сдаче прикладываются:

-   публичный HTTPS-адрес, доступный весь период проверки (ответ до 5 секунд);
-   `openapi.yaml` (OpenAPI 3.1, генерируется `backend/scripts/export_openapi.py`);
-   `DATA-API.yaml` по формату DATA-API 1.0 (шаблон и валидатор:
    https://gitverse.ru/stasnorman/example-data-api), прогнанный через валидатор;
-   тестовые учётные записи: переменная `TEST_ACCESS_TOKENS` (`token:max_user_id`),
    значения передаются через защищённый канал, в репозитории не хранятся.

### 43.4 Решения, уточняющие разделы 1--42

-   **Деплой**: один Docker-образ (корневой `Dockerfile`), FastAPI отдаёт API,
    мини-приложение и webhook. Хостинг --- Render Free + Neon Free (PostgreSQL),
    пинг `/health` раз в 10 минут. Подробности --- `docs/deploy.md`.
-   **Docker Compose** (заменяет §34): сервисы `postgres` и `backend`; frontend
    собирается внутри образа backend. Сборка не дольше 5 минут.
-   **Бот**: `BOT_MODE=webhook` в production, `polling` локально. Уведомления --- через
    `NotificationService` и протокол `MessageSender`.
-   **TLS до MAX**: `platform-api2.max.ru` использует сертификат НУЦ Минцифры; публичные
    сертификаты лежат в `backend/certs/`.
-   **Аутентификация** (§27): `POST /api/v1/auth/max` проверяет HMAC initData и выдаёт
    подписанный токен; клиент передаёт `Authorization: Bearer`.
-   **Сроки шагов**: `recommended_days` в сценарии; срок --- рекомендация, рассчитанная
    сервисом (`deadline_origin=calculated`), а не юридическое требование.
-   **Источники**: реальные ссылки на официальные страницы помечаются `OFFICIAL` с датой
    проверки; где официального источника нет --- `MOCK` и «Демонстрационные данные».
-   **Правила**: тип значения проверяется при загрузке сценария (возраст --- число,
    булевы поля --- bool, перечисления --- допустимые значения).

### 43.5 Статус этапов

| Этап | Статус |
|---|---|
| 0--3. Bootstrap, БД, движок, API | готово |
| 4. Seed: сценарий, источники, документы для Москвы, СПб, Татарстана | готово |
| 5. Frontend: Welcome, Onboarding, Route, Step, Completion, Support | готово |
| 6. MAX Bridge, initData, авторизация | готово |
| 7. Бот: `/start`, `/next`, webhook/polling, уведомления, напоминания | готово |
| 8. Ошибки: единый формат, retry, empty/loading/error | готово |
| 9. pytest, ruff, mypy, npm build, docker build | готово |
| 10. Деплой на HTTPS, Mini App URL в настройках бота, презентация | в работе |
| 11. Пилот: коды вузов (КФУ, СПбГУ, ВШЭ), сценарий `foreign_student_v1`, «✅ Выполнено» из чата, `/api/v1/stats`, календарь .ics, приглашение одногруппника | готово |

### 43.6 Won't have в MVP

Админка для редакторов сценариев, интеграции с государственными ИС, локализация
интерфейса, LLM.
