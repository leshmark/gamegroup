# Load environment variables from .env file
-include .env
export

# Configuration
DOMAIN ?= example.com
EMAIL ?= admin@$(DOMAIN)
CERT_PATH ?= ./certs

# GCP/Artifact Registry config - create aliases from .env variables
PROJECT_ID = $(GCP_PROJECT_ID)
REGION = $(GCP_REGION)
REPO = $(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo

.PHONY: help up down build rebuild restart logs logs-follow clean ps cert cert-staging
.PHONY: gcloud-auth publish-frontend publish-backend terraform-init terraform-plan terraform-apply
.PHONY: db-backup db-restore

##@ General
help: ## Show this help message
	@echo "\033[1mGameGroup Development Commands\033[0m"
	@echo "\033[1m==============================\033[0m"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Docker Development

dev: build down up logs-follow ## Rebuild and start all services for development

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

##@ Google Cloud & Artifact Registry

gcloud-sdk-install: ## Install Google Cloud SDK via snap
	sudo snap install google-cloud-sdk --classic

gcloud-auth: gcloud-login gcloud-set-project gcloud-adc-login gcloud-set-quota-project gcloud-docker-config ## Set up ADC and Authenticate Docker with Google Artifact Registry

gcloud-login:
	@echo "Logging in to Google Cloud with account $(GCP_ACCOUNT)..."
	@gcloud auth login $(GCP_ACCOUNT)

gcloud-set-project:
	@echo "Setting billing project to $(PROJECT_ID)..."
	@mkdir -p $(HOME)/.config/gcloud
	@gcloud config set project $(PROJECT_ID)

gcloud-adc-login:
	@echo "Authenticating with Google Cloud..."
	@echo "Please follow the prompts to authenticate with your Google account."
	@gcloud auth application-default login --project=$(PROJECT_ID)

gcloud-set-quota-project:
	@echo "Setting quota project to $(PROJECT_ID)..."
	@gcloud auth application-default set-quota-project $(PROJECT_ID)

gcloud-docker-config:
	@echo "Configuring Docker to use gcloud as a credential helper for Artifact Registry..."
	@mkdir -p $(HOME)/.docker
	@gcloud auth configure-docker $(REGION)-docker.pkg.dev 2>&1 | grep -v "WARNING.*docker.*not in system PATH" || true

gcloud-create-project: ## Create GCP project
	@echo "Creating GCP project $(PROJECT_ID)..."
	@gcloud projects create $(PROJECT_ID) --name="$(PROJECT_ID)"
	@echo "Project $(PROJECT_ID) created successfully"

gcloud-create-terraform-bucket: ## Create GCS bucket for Terraform state
	@echo "Creating Terraform state bucket..."
	@gcloud storage buckets create gs://$(PROJECT_ID)-terraform-state --location=$(REGION) --project=$(PROJECT_ID)
	@echo "Terraform state bucket created: $(PROJECT_ID)-terraform-state"

##@ Artifact Registry

# Build, tag, and push frontend image
publish-frontend: gcloud-auth ## Build, tag, and push frontend Docker image to Artifact Registry
	docker build -t $(FRONTEND_IMAGE) ./frontend
	docker tag $(FRONTEND_IMAGE) $(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(FRONTEND_IMAGE):latest
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(FRONTEND_IMAGE):latest

# Build, tag, and push backend image
publish-backend: gcloud-auth ## Build, tag, and push backend Docker image to Artifact Registry
	docker build -t $(BACKEND_IMAGE) ./backend
	docker tag $(BACKEND_IMAGE) $(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(BACKEND_IMAGE):latest
	docker push $(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(BACKEND_IMAGE):latest

##@ TLS Certificates

cert: ## Generate TLS certificate using certbot for DOMAIN
	@echo "Generating TLS certificate for $(DOMAIN)..."
	@mkdir -p $(CERT_PATH)
	docker run -it --rm \
		-v $(CERT_PATH):/etc/letsencrypt \
		-p 8082:80 -p 8443:443 \
		certbot/certbot certonly \
		--standalone \
		--preferred-challenges http \
		--email $(EMAIL) \
		--agree-tos \
		--no-eff-email \
		-d $(DOMAIN)
	@sudo chown -R $(USER):$(USER) $(CERT_PATH)
	@cd $(CERT_PATH)/live && ln -s $(DOMAIN) certificate
	@echo "Certificate generated in $(CERT_PATH)/live/certificate/"

cert-staging: ## Generate staging TLS certificate using certbot for DOMAIN (for testing)
	@echo "Generating STAGING TLS certificate for $(DOMAIN)..."
	@mkdir -p $(CERT_PATH)
	docker run -it --rm \
		-v $(CERT_PATH):/etc/letsencrypt \
		-p 8082:80 -p 8443:443 \
		certbot/certbot certonly \
		--standalone \
		--staging \
		--preferred-challenges http \
		--email $(EMAIL) \
		--agree-tos \
		--no-eff-email \
		-d $(DOMAIN)
	@sudo chown -R $(USER):$(USER) $(CERT_PATH)
	@cd $(CERT_PATH)/live && ln -s $(DOMAIN) certificate
	@echo "Staging certificate generated in $(CERT_PATH)/live/certificate/"

##@ Terraform

# Terraform Docker base command with all variables
TERRAFORM_DOCKER = docker run --rm -it \
	-v $(PWD)/infrastructure/gcp:/workspace \
	-w /workspace \
	-v $(HOME)/.config/gcloud:/root/.config/gcloud \
	-e TF_VAR_project_id=$(GCP_PROJECT_ID) \
	-e TF_VAR_region=$(GCP_REGION) \
	-e TF_VAR_frontend_image=$(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(FRONTEND_IMAGE):latest \
	-e TF_VAR_backend_image=$(REGION)-docker.pkg.dev/$(PROJECT_ID)/container-repo/$(BACKEND_IMAGE):latest \
	-e TF_VAR_frontend_domain_name=$(FRONTEND_DOMAIN_NAME) \
	-e TF_VAR_backend_domain_name=$(BACKEND_DOMAIN_NAME) \
	-e TF_VAR_db_host=$(DB_HOST) \
	-e TF_VAR_db_name=$(DB_NAME) \
	-e TF_VAR_db_user=$(DB_USER) \
	-e TF_VAR_db_port=$(DB_PORT) \
	-e TF_VAR_db_password=$(DB_PASSWORD) \
	-e TF_VAR_forward_email_user=$(FORWARD_EMAIL_USER) \
	-e TF_VAR_forward_email_password=$(FORWARD_EMAIL_PASSWORD) \
	-e TF_VAR_from_email=$(FROM_EMAIL) \
	-e TF_VAR_jwt_private_key=$(JWT_PRIVATE_KEY) \
	-e TF_VAR_log_level=$(LOG_LEVEL) \
	-e TF_VAR_allowed_origins=$(ALLOWED_ORIGINS) \
	hashicorp/terraform:latest

terraform-init: ## Initialize Terraform in a container
	$(TERRAFORM_DOCKER) init

terraform-plan: ## Run Terraform plan in a container
	$(TERRAFORM_DOCKER) plan

terraform-apply: ## Run Terraform apply in a container
	$(TERRAFORM_DOCKER) apply

terraform-destroy: ## Run Terraform destroy in a container
	$(TERRAFORM_DOCKER) destroy

##@ Database Backup & Restore

db-backup: ## Backup the database to backup.tar.gz
	@echo "Creating database backup..."
	docker exec gamegroup-db pg_dump -U $${DB_USER:-postgres} -F t $${DB_NAME:-gamegroup} > backup.tar
	gzip -f backup.tar
	@echo "Database backup saved to ./backup.tar.gz"

db-restore: ## Restore the database from backup.tar.gz
	@if [ ! -f ./backup.tar.gz ]; then echo "Error: backup.tar.gz not found!"; exit 1; fi
	@echo "Restoring database from backup..."
	gunzip -c backup.tar.gz | docker exec -i gamegroup-db pg_restore -U $${DB_USER:-postgres} -d $${DB_NAME:-gamegroup} -c --if-exists
	@echo "Database restored from ./backup.tar.gz"
