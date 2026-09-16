# Маршрут

## Problem

После переезда в другой регион студенту приходится самостоятельно собирать сведения о регистрации, медицинском обслуживании, льготах и мерах поддержки.

## Solution

«Маршрут» — MAX-бот с Mini App, который на основании ответов пользователя формирует понятную последовательность действий. На текущем этапе создан только технический каркас.

## Target audience

Студенты — граждане РФ, переехавшие в другой регион для обучения.

## User scenario

Пользователь запускает бота, проходит onboarding в Mini App, получает персональный маршрут и отмечает выполненные шаги. Реализация сценария начнётся после bootstrap-этапа.

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

На этапе 0 реализован `GET /health`:

```json
{"status":"ok"}
```

OpenAPI доступен по адресу `http://localhost:8000/docs`.

## Data

Сценарии будут храниться в `data/scenarios` отдельно от Python-кода.

## Mock data

Демонстрационные сценарии и источники будут добавлены на этапе 4 с обязательной маркировкой `MOCK`.

## Testing

```bash
cd backend
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/mypy app tests
```

```bash
cd frontend
npm run build
```

## Demo scenario

Целевой сценарий — маршрут студента после переезда. На этапе 0 доступна только проверка инфраструктуры.

## Known limitations

Профиль, сценарии, маршруты, MAX Bridge и бот ещё не реализованы. Проект не является государственным сервисом и не принимает юридически значимые решения.

## Scaling

Новые регионы и сценарии будут добавляться данными без изменения Rule Engine. Масштабирование сохраняет модульный монолит до появления подтверждённой необходимости в иной архитектуре.

