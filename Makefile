# Active environment: `make ENVIRONMENT=prod ...` (default: dev)
ENVIRONMENT ?= dev
ENV_FILE  := .env.$(ENVIRONMENT)

# Load environment variables from .env and .env.<ENVIRONMENT>
-include $(ENV_FILE)
export

# Configuration
DOMAIN ?= example.com
EMAIL ?= admin@$(DOMAIN)
# CERT_PATH ?= ./certs

ifeq ($(ENVIRONMENT),dev)
DOCKER_FILES := -f compose.yml -f compose-dev.yml
else
DOCKER_FILES := -f compose.yml
endif
# Database backup naming: backup-<ENVIRONMENT>-<YYYY-MM-DD_HHMMSS>.tar.gz
# Override with: make db-backup BACKUP_TS=2026-11-04
BACKUP_TS   ?= $(shell date +%Y-%m-%d_%H%M%S)
BACKUP_FILE ?= backup-$(ENVIRONMENT)-$(BACKUP_TS).tar.gz
# Latest backup for the active environment (used as db-restore default)
LAST_BACKUP      ?= $(shell ls -1t backup-$(ENVIRONMENT)-*.tar.gz 2>/dev/null | head -n 1)

# Print configuration banner before any target runs
$(info )
$(info Configuration)
$(info ------------)
$(info ENVIRONMENT: $(ENVIRONMENT))
$(info DOMAIN:      $(DOMAIN))
$(info EMAIL:       $(EMAIL))
$(info CERT_PATH:   $(CERT_PATH))
$(info DOCKER_FILES: $(DOCKER_FILES))
$(info BACKUP_FILE: $(BACKUP_FILE))
$(info LAST_BACKUP:      $(LAST_BACKUP))
$(info ------------)

# Detect docker binary
DOCKER := $(shell command -v docker 2>/dev/null || echo docker)

# Detect docker compose command: prefer V2 plugin (docker compose), fall back to V1 (docker-compose)
DOCKER_COMPOSE := $(shell if $(DOCKER) compose version >/dev/null 2>&1; then echo "$(DOCKER) compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "$(DOCKER) compose"; fi)

.PHONY: help dev rebuild build up down restart logs logs-follow clean ps cert cert-staging cert-dev ruff ruff-format ruff-fix
.PHONY: gcloud-auth publish-frontend publish-backend terraform-init terraform-plan terraform-apply
.PHONY: db-backup db-restore

##@ General
help: ## Show this help message
	@echo 
	@echo "\033[1mGameGroup Development Commands\033[0m"
	@echo "\033[1m==============================\033[0m"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Docker Development
dev: down build up logs-follow ## Rebuild and start all services for development
rebuild: dev ## Rebuild and start all services for development

build: ## Build all services
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT}  build 

up: ## Start all services in detached mode
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} ${DOCKER_FILES} up -d

down: ## Stop and remove all containers
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} ${DOCKER_FILES} down

restart: ## Restart all services
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} restart

logs: ## View logs from all services
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} logs

logs-follow: ## Follow logs from all services
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} logs -f

clean: ## Stop containers and remove volumes
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} down -v

ps: ## List running containers
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} ps

##@ Local Database Backup & Restore
db-backup: ## Backup the database to backup-<ENVIRONMENT>-<date>.tar.gz
	@echo "Creating database backup..."
	$(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} exec -T postgres pg_dump -U $${DB_USER:-postgres} -F t $${DB_NAME:-gamegroup} > backup-$(ENVIRONMENT)-$(BACKUP_TS).tar
	gzip -f backup-$(ENVIRONMENT)-$(BACKUP_TS).tar
	@echo "Database backup saved to ./$(BACKUP_FILE)"

db-restore: ## Restore the database from a backup (BACKUP=<file>, default: newest for ENVIRONMENT)
	@if [ -z "$(LAST_BACKUP)" ] || [ ! -f "$(LAST_BACKUP)" ]; then \
		echo "Error: no backup found for $(ENVIRONMENT). Use: make db-restore BACKUP=backup-$(ENVIRONMENT)-<date>.tar.gz"; \
		exit 1; \
	fi
	@echo "Restoring database from $(LAST_BACKUP)..."
	gunzip -c $(LAST_BACKUP) | $(DOCKER_COMPOSE) -p gamegroup-${ENVIRONMENT} exec -T postgres pg_restore -U $${DB_USER:-postgres} -d $${DB_NAME:-gamegroup} -c --if-exists
	@echo "Database restored from $(BACKUP)"

##@ Code Quality
ruff: ## Run ruff linting on Python code
	@echo "Running ruff linting on frontend Python code..."
	$(DOCKER) run --rm -v $(PWD)/frontend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff check *.py"
	@echo "Running ruff linting on backend Python code..."
	$(DOCKER) run --rm -v $(PWD)/backend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff check *.py"

ruff-format: ## Format Python code with ruff
	@echo "Formatting frontend Python code with ruff..."
	$(DOCKER) run --rm -v $(PWD)/frontend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff format *.py"
	@echo "Formatting backend Python code with ruff..."
	$(DOCKER) run --rm -v $(PWD)/backend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff format *.py"

ruff-fix: ## Format Python code with ruff
	@echo "Formatting frontend Python code with ruff..."
	$(DOCKER) run --rm -v $(PWD)/frontend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff check --fix *.py"
	@echo "Formatting backend Python code with ruff..."
	$(DOCKER) run --rm -v $(PWD)/backend:/app -w /app python:3.13-slim sh -c "pip install -q ruff && ruff check --fix *.py"

##@ TLS Certificates
cert-dev: ## Generate self-signed certificate for local development
	@echo "Generating self-signed certificate for localhost development..."
	@mkdir -p $(CERT_PATH)/live/certificate
	$(DOCKER) run --rm \
		-v $(PWD)/$(CERT_PATH)/live/certificate:/certs \
		alpine/openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
		-keyout /certs/privkey.pem \
		-out /certs/fullchain.pem \
		-subj "/C=US/ST=State/L=City/O=Development/CN=localhost" \
		-addext "subjectAltName=DNS:localhost,DNS:*.localhost,IP:127.0.0.1"
	@sudo chown -R $(USER):$(USER) $(CERT_PATH)
	@chmod 644 $(CERT_PATH)/live/certificate/privkey.pem
	@chmod 644 $(CERT_PATH)/live/certificate/fullchain.pem
	@echo "Self-signed certificate generated in $(CERT_PATH)/live/certificate/"
	@echo "  privkey.pem  - Private key"
	@echo "  fullchain.pem - Certificate"


cert-prod: ## Generate TLS certificate using certbot for DOMAIN
	@echo "Generating TLS certificate for $(DOMAIN)..."
	@mkdir -p $(CERT_PATH)/live/certificate
	$(DOCKER) run -it --rm \
		--network host \
		-v $(CERT_PATH):/etc/letsencrypt \
		certbot/certbot certonly \
		--standalone \
		--http-01-port $(HTTP_PORT) \
		--https-port $(HTTPS_PORT) \
		--preferred-challenges http \
		--email $(EMAIL) \
		--agree-tos \
		--no-eff-email \
		-d $(DOMAIN)
	@sudo chown -R $(USER):$(USER) $(CERT_PATH)
	@cd $(CERT_PATH)/live && ln -s $(DOMAIN) certificate
	@echo "Certificate generated in $(CERT_PATH)/live/certificate/"


