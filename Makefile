.PHONY: help up down build rebuild restart logs logs-follow clean ps

help: ## Show this help message
	@echo "GameGroup Development Commands"
	@echo "=============================="
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

up: ## Start all services in detached mode
	docker compose up -d

down: ## Stop and remove all containers
	docker compose down

build: ## Build all services
	docker compose build

rebuild: ## Rebuild and restart all services
	$(MAKE) down
	$(MAKE) build
	$(MAKE) up

restart: ## Restart all services
	docker compose restart

logs: ## View logs from all services
	docker compose logs

logs-follow: ## Follow logs from all services
	docker compose logs -f

clean: ## Stop containers and remove volumes
	docker compose down -v

ps: ## List running containers
	docker compose ps
