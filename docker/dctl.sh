#!/bin/bash
set -e
chmod +x "$0"

cd "$(dirname "${BASH_SOURCE[0]}")"

export DEFAULT_USER="1000";
export DEFAULT_GROUP="1000";

export USER_ID=`id -u`
export GROUP_ID=`id -g`
export USER=$USER

if [ "$USER_ID" == "0" ];
then
    export USER_ID=$DEFAULT_USER;
fi

if [ "$GROUP_ID" == "0" ];
then
    export GROUP_ID=$DEFAULT_GROUP;
fi

source .env

if [ "$1" == "revision" ];
  then
    docker exec ${PROJECT_PREFIX}-back alembic revision --autogenerate
  fi

if [ "$1" == "downgrade" ];
  then
    docker exec ${PROJECT_PREFIX}-back alembic downgrade -1
  fi

if [ "$1" == "upgrade" ];
  then
    docker exec ${PROJECT_PREFIX}-back alembic upgrade heads
  fi

if [ "$1" == "recreate_schema" ];
  then
    docker exec ${PROJECT_PREFIX}-psql psql -U ${POSTGRES_USER} -d ${POSTGRES_NAME} -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  fi
