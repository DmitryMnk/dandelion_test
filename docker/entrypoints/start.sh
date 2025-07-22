#!/bin/bash
chmod +x start.sh
set -e

# Запуск приложения
exec uvicorn main:app --host 0.0.0.0 --port ${APP_HTTP_PORT} --reload

# Выполнение миграций
alembic upgrade heads