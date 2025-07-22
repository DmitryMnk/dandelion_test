# Запус проекта
___

1. Перейти в директорию docker и скопировать .env.example командой
```
cp .env.example .env
```
при необходимости внести изменения в .env

2. Запустить проект docker compose up --build.
3. Перейти в браузер localhost:8300//api/dandelion_test/docs - сваггер.

# Пояснения по атомарности.
Атомарность операций с postgresql достигается за счет использования транзакций с уровнем изолированности read commit.
В Редис так же можно использовать транзакции и пр. инструменты. В данном случае для увеличения числа очков использовал incrby, которая атомарна по умолчанию.

# Пример запросов
curl -X 'POST' \
  'http://localhost:8300/api/dandelion_test/v1/events/event' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": 2,
  "event_type": "complete_level",
  "details": {
    "level": 30
  }
}'


curl -X 'GET' \
  'http://localhost:8300/api/dandelion_test/v1/users/stats/2' \
  -H 'accept: application/json'
