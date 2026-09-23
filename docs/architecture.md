# Архитектура

Проект развивается как модульный монолит: React Mini App и MAX-бот обращаются к FastAPI, а доменная логика не зависит от транспорта, базы данных и внешних API.

На этапе 2 добавлены `UserContext`, строгий детерминированный Rule Engine, JSON Scenario Loader и чистый Route Generator. Доменная логика не обращается к FastAPI, PostgreSQL или внешним сервисам.

На этапе 3 добавлены тонкие FastAPI handlers, service/repository слой и сохранение маршрутов в PostgreSQL. API получает профиль фиксированного development-пользователя, вызывает существующий Route Generator, сохраняет только применимые шаги и рассчитывает progress по `UserRouteStep`. Аутентификация MAX остаётся за пределами этапа.
