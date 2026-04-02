.PHONY: help \
	local-up local-down local-logs local-shell local-migrate local-createsuperuser \
	staging-up staging-down staging-logs staging-migrate \
	prod-up prod-down prod-logs prod-migrate \
	test test-fast coverage lint format build-dev build-prod

DC_LOCAL   = docker compose -f docker-compose.yml
DC_STAGING = docker compose -f docker-compose.staging.yml --env-file .envs/.env.staging
DC_PROD    = docker compose -f docker-compose.prod.yml    --env-file .envs/.env.prod

help:
	@echo ""
	@echo "TicketTche Backend"
	@echo ""
	@echo "  LOCAL"
	@echo "    make local-up              Sobe ambiente local"
	@echo "    make local-down            Derruba ambiente local"
	@echo "    make local-logs            Logs em tempo real"
	@echo "    make local-shell           Shell Django"
	@echo "    make local-migrate         Executa migrations"
	@echo "    make local-createsuperuser Cria superusuario"
	@echo ""
	@echo "  STAGING"
	@echo "    make staging-up            Sobe homologacao"
	@echo "    make staging-down          Derruba homologacao"
	@echo "    make staging-logs          Logs de homologacao"
	@echo "    make staging-migrate       Migrations em homologacao"
	@echo ""
	@echo "  PRODUCAO"
	@echo "    make prod-up               Sobe producao"
	@echo "    make prod-down             Derruba producao"
	@echo "    make prod-logs             Logs de producao"
	@echo "    make prod-migrate          Migrations em producao"
	@echo ""
	@echo "  TESTES"
	@echo "    make test                  Testes com cobertura >=98.9% (dentro do container)"
	@echo "    make test-fast             Testes rapidos sem cobertura"
	@echo "    make coverage              Relatorio HTML de cobertura"
	@echo "    make lint                  flake8 + isort + black"
	@echo "    make format                Formata codigo"
	@echo ""

# ---------------------------------------------------------------------------
# LOCAL
# ---------------------------------------------------------------------------
local-up:
	$(DC_LOCAL) up -d --build
	@echo "Ambiente local rodando em http://localhost:8000"

local-down:
	$(DC_LOCAL) down

local-logs:
	$(DC_LOCAL) logs -f

local-shell:
	$(DC_LOCAL) exec web python manage.py shell

local-migrate:
	$(DC_LOCAL) exec web python manage.py makemigrations
	$(DC_LOCAL) exec web python manage.py migrate

local-createsuperuser:
	$(DC_LOCAL) exec web python manage.py createsuperuser

# ---------------------------------------------------------------------------
# STAGING
# ---------------------------------------------------------------------------
staging-up:
	$(DC_STAGING) up -d --build

staging-down:
	$(DC_STAGING) down

staging-logs:
	$(DC_STAGING) logs -f

staging-migrate:
	$(DC_STAGING) exec web python manage.py migrate --noinput

# ---------------------------------------------------------------------------
# PRODUCAO
# ---------------------------------------------------------------------------
prod-up:
	$(DC_PROD) up -d --build

prod-down:
	$(DC_PROD) down

prod-logs:
	$(DC_PROD) logs -f

prod-migrate:
	$(DC_PROD) exec web python manage.py migrate --noinput

# ---------------------------------------------------------------------------
# TESTES (rodam dentro do container com PostgreSQL real)
# ---------------------------------------------------------------------------
test:
	@echo "Subindo banco para testes..."
	$(DC_LOCAL) up -d db redis
	@until $(DC_LOCAL) exec -T db pg_isready -U tickettche -q; do sleep 1; done
	@echo "Banco pronto. Rodando testes..."
	$(DC_LOCAL) run --rm \
		-e DJANGO_SETTINGS_MODULE=config.settings.test \
		-e RUN_MIGRATIONS=false \
		web \
		pytest --cov=apps --cov-report=term-missing --cov-fail-under=98.9 -v

test-fast:
	$(DC_LOCAL) up -d db redis
	@until $(DC_LOCAL) exec -T db pg_isready -U tickettche -q; do sleep 1; done
	$(DC_LOCAL) run --rm \
		-e DJANGO_SETTINGS_MODULE=config.settings.test \
		-e RUN_MIGRATIONS=false \
		web \
		pytest --tb=short -q

coverage:
	$(DC_LOCAL) up -d db redis
	@until $(DC_LOCAL) exec -T db pg_isready -U tickettche -q; do sleep 1; done
	$(DC_LOCAL) run --rm \
		-e DJANGO_SETTINGS_MODULE=config.settings.test \
		-e RUN_MIGRATIONS=false \
		web \
		pytest --cov=apps --cov-report=html --cov-report=term-missing
	@echo "Relatorio em htmlcov/index.html"

# ---------------------------------------------------------------------------
# QUALIDADE
# ---------------------------------------------------------------------------
lint:
	flake8 apps/ config/
	isort --check-only apps/ config/
	black --check apps/ config/

format:
	black apps/ config/
	isort apps/ config/

# ---------------------------------------------------------------------------
# BUILD
# ---------------------------------------------------------------------------
build-dev:
	docker build --target dev  -t tickettche-backend:dev  .

build-prod:
	docker build --target prod -t tickettche-backend:prod .
