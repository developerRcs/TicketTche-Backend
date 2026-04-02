#!/bin/bash
set -e

# Conecta explicitamente ao banco 'postgres' (sempre existe)
# e cria os bancos da aplicacao e de testes se nao existirem.
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
  SELECT 'CREATE DATABASE ${POSTGRES_DB}' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = '${POSTGRES_DB}'
  )\gexec

  SELECT 'CREATE DATABASE tickettche_test' WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'tickettche_test'
  )\gexec

  GRANT ALL PRIVILEGES ON DATABASE "${POSTGRES_DB}"   TO "${POSTGRES_USER}";
  GRANT ALL PRIVILEGES ON DATABASE tickettche_test TO "${POSTGRES_USER}";
EOSQL

echo "Bancos '${POSTGRES_DB}' e 'tickettche_test' prontos."
