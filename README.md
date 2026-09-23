# Маршрут

## Problem

После переезда в другой регион студенту приходится самостоятельно собирать сведения о регистрации, медицинском обслуживании, льготах и мерах поддержки.

## Solution

«Маршрут» — MAX-бот с Mini App, который на основании ответов пользователя формирует понятную последовательность действий. Backend уже формирует и сохраняет персональные маршруты через HTTP API.

## Target audience

Студенты — граждане РФ, переехавшие в другой регион для обучения.

## User scenario

Пользователь запускает бота, проходит onboarding в Mini App, получает персональный маршрут и отмечает выполненные шаги.

## Architecture

Модульный монолит: React → FastAPI → PostgreSQL. Доменная логика будет отделена от MAX API, FastAPI, PostgreSQL и внешних поставщиков данных.

## Technology stack

- Python 3.13, FastAPI
- React, TypeScript, Vite
- PostgreSQL
- Docker Compose

## Repository structure

- `backend` — API и в дальнейшем доменные модули
- `frontend` — browser-mode Mini App
- `data/scenarios` — конфигурации сценариев
- `docs` — архитектура и демо

## Local development

Backend:

```bash
cd backend
python3.13 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Frontend: `http://localhost:5173`. API: `http://localhost:8000`. Health: `http://localhost:8000/health`.

## Environment variables

Переменные и безопасные development-значения перечислены в `.env.example`. Секреты не должны попадать в Git.

## MAX configuration

Интеграция MAX будет добавлена на этапах 6–7. Токен передаётся только через `MAX_BOT_TOKEN`.

## API

Этап 3 предоставляет `GET /health`, профиль development-пользователя и API маршрутов под `/api/v1`. Новый маршрут создаётся из активного сценария существующим Rule Engine, сохраняется в PostgreSQL и поддерживает complete/reopen с пересчётом progress.

OpenAPI доступен по адресу `http://localhost:8000/docs`.

## Data

Сценарии будут храниться в `data/scenarios` отдельно от Python-кода. Схема PostgreSQL управляется Alembic:

```bash
cd backend
.venv/bin/alembic upgrade head
```

Первая миграция создаёт пользователей, профили, сценарии, шаги, правила, источники и пользовательские маршруты. При запуске через Docker Compose миграции применяются автоматически до старта API.

`ScenarioLoader` читает JSON-файлы из `SCENARIO_DATA_DIR`. Правила проходят строгую валидацию: неизвестные поля и скалярные значения для `IN`/`NOT_IN` отклоняются. `RouteGenerator` детерминированно применяет правила с AND-семантикой и сохраняет порядок шагов по `position`.

## Mock data

Демонстрационные сценарии и источники будут добавлены на этапе 4 с обязательной маркировкой `MOCK`.

## Testing

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy app tests migrations
```

Unit-тесты Rule Engine покрывают все поддерживаемые операторы, строгую проверку типов, загрузку сценария и генерацию персонального маршрута.

```bash
cd frontend
npm run build
```

## Demo scenario

Целевой сценарий — маршрут студента после переезда. Демонстрационные данные будут добавлены отдельно на этапе 4.

## Known limitations

Для API используется один фиксированный development-пользователь; полноценная аутентификация, demo seed, MAX Bridge и бот ещё не реализованы. Проект не является государственным сервисом и не принимает юридически значимые решения.

## Scaling

Новые регионы и сценарии будут добавляться данными без изменения Rule Engine. Масштабирование сохраняет модульный монолит до появления подтверждённой необходимости в иной архитектуре.
