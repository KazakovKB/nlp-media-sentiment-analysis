include .env
export

.DEFAULT_GOAL := help

COMPOSE := docker compose
ENV ?= .env

DC := $(COMPOSE) --env-file $(ENV)

up: ## Поднять инфраструктуру и приложение
	$(DC) up -d db
	$(DC) run --rm db_migrate
	$(DC) up -d rabbitmq
	$(DC) up -d app
	$(DC) up -d worker
	$(DC) up -d web-proxy

up-build: ## Поднять инфраструктуру и приложение (с пересборкой app/worker)
	$(DC) build app worker db_migrate
	$(DC) up -d db
	$(DC) up -d db_migrate
	$(DC) up -d rabbitmq
	$(DC) up -d app
	$(DC) up -d worker
	$(DC) up -d web-proxy

down: ## Остановить всё и удалить контейнеры
	$(DC) down

restart: down up ## Перезапуск всего стека

mlflow-up: ## Поднять MLflow
	$(DC) --profile mlflow up -d postgres_mlflow mlflow

mlflow-down: ## Остановить MLflow
	$(DC) --profile mlflow stop postgres_mlflow mlflow

mlflow-rm: ## Снести MLflow контейнеры
	$(DC) --profile mlflow down

init-lenta: ## Инициализация источника Lenta
	$(DC) --profile init run --rm lenta_init

test: ## Запуск тестов (локально в контейнере)
	$(DC) up -d db_test rabbitmq worker
	$(DC) run --rm -e DATABASE_URL=$(DATABASE_URL_TEST) db_migrate_test
	$(DC) run --rm --no-deps -e DATABASE_URL=$(DATABASE_URL_TEST) app python -m pytest
	$(DC) down

test-unit: ## Быстрые unit-тесты
	$(DC) run --rm \
		-e SENTIMENT_ENABLED=0 \
		app pytest -m "not slow"

test-cov: ## Тесты с покрытием
	$(DC) run --rm \
		-e SENTIMENT_ENABLED=0 \
		app pytest --cov=src/app --cov-report=term-missing