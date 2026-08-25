.PHONY: help clean lint lint-src init down volume pull build up ps test test-dev test-one test-snapshot coverage coverage-html prune migrations migrate reset_db createsuperuser docker-build tf-init tf-plan tf-apply tf-destroy tf-up

.ONESHELL:
SHELL := /bin/bash

.DEFAULT_GOAL := help

help: ## Print help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_.-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Project Initialization & Docker Compose ---
# Terraform no está wireado todavía (devops/terraform/ no existe) — no se incluye en init.
init: down volume up ## Init Project (docker compose)
	@echo "¡Proyecto inicializado desde cero y actualizado correctamente!"

down: ## Stop all compose services
	docker compose -f devops/docker-compose.yaml down --remove-orphans

volume: ## Remove all containers volumes and force clean slate
	docker volume prune -f
	docker compose -f devops/docker-compose.yaml down -v --remove-orphans

pull: ## Pull images
	docker compose -f devops/docker-compose.yaml pull

build: ## Build Docker services
	docker compose -f devops/docker-compose.yaml build

up: pull build ## Run all services in background
	docker compose -f devops/docker-compose.yaml up -d --wait
	make ps

ps: ## Show all services status
	docker compose -f devops/docker-compose.yaml ps

prune: ## Remove all volumes, containers and images globally
	make down
	make volume
	docker system prune -f

# --- Django & Database Commands ---
migrations: ## Make Django migrations
	docker compose -f devops/docker-compose.yaml exec migrator python manage.py makemigrations

migrate: ## Run Django migrations
	docker compose -f devops/docker-compose.yaml exec migrator python manage.py migrate

reset_db: ## Reset database
	docker compose -f devops/docker-compose.yaml run --rm migrator python manage.py reset_db --noinput --close-sessions

createsuperuser: ## Create a Django superuser (interactive) in the running admin container
	docker compose -f devops/docker-compose.yaml exec admin python manage.py createsuperuser

# --- Code Quality & Testing ---
clean: ## Delete Python cache and temporary files
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
	find . -name '*~' -delete
	find . -name '__pycache__' -delete

lint: ## Run linters for src and tests
	black src/ tests/ && isort src/ tests/ --profile black && flake8 src/

lint-src: ## Run linters only for src/
	black src/ && isort src/ --profile black && flake8 src/

test: ## Run all tests via pytest
	pytest

test-dev: ## Run tests with verbose output and no capture
	pytest -s -vv

test-one: ## Run a single test: make test-one TEST=tests/path/to/test_file.py::test_name
	@if [ -z "$(TEST)" ]; then \
		echo "Usage: make test-one TEST=tests/path/to/test_file.py::test_name"; \
		exit 1; \
	fi
	pytest -vv "$(TEST)"

test-snapshot: ## Update syrupy snapshots
	pytest --snapshot-update

coverage: ## Run tests under coverage and print the terminal report (config: pyproject.toml [tool.coverage.*])
	coverage run -m pytest
	coverage report

coverage-html: ## Same as `coverage`, plus an HTML report at htmlcov/index.html
	coverage run -m pytest
	coverage html
	@echo "Report: htmlcov/index.html"

# --- Docker Build & Deployment Utils ---
docker-build: ## Build Docker image using buildkit
	DOCKER_BUILDKIT=1 docker build -f devops/Dockerfile --target development -t quiz-management/backend:dev .

# --- Terraform Infrastructure (pendiente: devops/terraform/ aún no existe) ---
ENV ?= local
TF_DIR := devops/terraform/environments/$(ENV)

tf-fmt: ## Formatea todo el código Terraform
	terraform fmt -recursive devops/terraform

tf-validate: ## Valida sintaxis y tipos
	cd $(TF_DIR) && terraform validate

tf-init: ## Inicializa el entorno (ej: make tf-init ENV=qa)
	cd $(TF_DIR) && terraform init -reconfigure -upgrade

tf-plan: tf-validate
	cd $(TF_DIR) && terraform plan

tf-apply:
	cd $(TF_DIR) && terraform apply -auto-approve

tf-destroy:
	cd $(TF_DIR) && terraform destroy -auto-approve

tf-up: tf-init tf-apply ## Todo en uno (ej: make tf-up ENV=qa)

tf-export-env: ## Vuelca los outputs de Terraform al .env local
	@terraform -chdir=$(TF_DIR) output -json s3_bucket_names | \
	  python3 -c "import json,sys; d=json.load(sys.stdin); print(f'S3_PUBLIC_BUCKET_NAME={d[\"public\"]}'); print(f'S3_PRIVATE_BUCKET_NAME={d[\"private\"]}')" \
	  >> .env
