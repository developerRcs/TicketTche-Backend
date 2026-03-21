#!/bin/bash
set -e

echo "Waiting for PostgreSQL at ${DB_HOST:-db}:${DB_PORT:-5432}..."
until python -c "
import psycopg2, sys
try:
    psycopg2.connect(
        host='${DB_HOST:-db}',
        port=${DB_PORT:-5432},
        user='${DB_USER:-tickettche}',
        password='${DB_PASSWORD:-tickettche_local_pass}',
        dbname='${DB_NAME:-tickettche_local}',
        connect_timeout=3
    )
except Exception as e:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Waiting for Redis..."
until python -c "
import redis, sys
try:
    r = redis.StrictRedis.from_url('${REDIS_URL:-redis://redis:6379/0}', socket_connect_timeout=3)
    r.ping()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  sleep 1
done
echo "Redis is ready."

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "Running migrations..."
  python manage.py migrate --noinput
  echo "Migrations done."
fi

exec "$@"
