.DEFAULT_GOAL := help

COMPOSE := docker compose
ENV ?= .env

# Core
up: ## Поднять инфраструктуру и приложение
	$(COMPOSE) up -d db
	$(COMPOSE) run --rm db_migrate
	$(COMPOSE) up -d app

down: ## Остановить всё и удалить контейнеры
	$(COMPOSE) down

restart: down up ## Перезапуск всего стека

logs: ## Логи приложения
	$(COMPOSE) logs -f app

ps: ## Статус контейнеров
	$(COMPOSE) ps

# Init / Seeds
init-lenta: ## Инициализация источника Lenta
	$(COMPOSE) --profile init run --rm lenta_init

# Tests
test: ## Запуск тестов (локально в контейнере)
	$(COMPOSE) run --rm \
		-e SENTIMENT_ENABLED=0 \
		-e SENTIMENT_FAIL_OPEN=1 \
		app python -m pytest

test-unit: ## Быстрые unit-тесты
	$(COMPOSE) run --rm \
		-e SENTIMENT_ENABLED=0 \
		app pytest -m "not slow"

test-cov: ## Тесты с покрытием
	$(COMPOSE) run --rm \
		-e SENTIMENT_ENABLED=0 \
		app pytest --cov=src/app --cov-report=term-missing