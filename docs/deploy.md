# Деплой (бесплатно, HTTPS)

Схема: **Render Free** (Docker web service: API + мини-приложение + webhook) и **Neon Free** (PostgreSQL). Бесплатная база Render удаляется через 30 дней, поэтому она не используется.

## 1. База данных — Neon

1. Зарегистрироваться на https://neon.tech и создать проект (регион — Frankfurt).
2. Скопировать connection string вида `postgresql://user:pass@ep-xxx.eu-central-1.aws.neon.tech/neondb?sslmode=require`. Backend сам преобразует его для asyncpg.

## 2. Приложение — Render

1. Залить репозиторий на GitHub.
2. На https://render.com: **New → Blueprint** → выбрать репозиторий. Render прочитает `render.yaml`.
3. Заполнить переменные, помеченные `sync: false`:
   - `DATABASE_URL` — строка из Neon;
   - `MAX_BOT_TOKEN` — токен бота;
   - `PUBLIC_URL` и `FRONTEND_URL` — адрес сервиса, например `https://marshrut-tf5o.onrender.com`;
   - `TEST_ACCESS_TOKENS` — например `<случайная строка>:900000001`, для проверяющих.

   `SECRET_KEY` и `WEBHOOK_SECRET` Render сгенерирует сам.
4. Дождаться деплоя и проверить `https://<адрес>/health` → `{"status":"ok"}`.

При старте контейнер применяет миграции, загружает сценарий и регистрирует webhook бота на `PUBLIC_URL/max/webhook`.

## 3. Не давать сервису засыпать

Бесплатный сервис Render засыпает через 15 минут без входящего трафика, а просыпается около минуты. Автопроверка API ждёт ответа до 5 секунд, а webhook MAX — до 30.

На https://cron-job.org создать задание: `GET https://<адрес>/health` каждые 10 минут. 750 бесплатных часов Render в месяц хватает на один сервис без перерыва.

## 4. Мини-приложение в MAX

В настройках бота `@t818_hakaton_max_bot` на платформе MAX для партнёров (business.max.ru) указать URL мини-приложения — `PUBLIC_URL`. Если доступ к настройкам есть только у организаторов, нужно отправить им этот адрес.

## 5. Проверка перед сдачей

```bash
python tools/run_data_api.py --base-url https://<адрес> --token <тестовый токен>
python validate_data_api.py DATA-API.yaml   # валидатор организаторов
python backend/scripts/export_openapi.py --server https://<адрес>
```

В `DATA-API.yaml` должен стоять реальный `api.baseUrl`.
