# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This repository is currently a bootstrap skeleton: only project configuration exists (`pyproject.toml`, `poetry.lock`, `Makefile`, `.python-version`). There is no `src/`, `tests/`, or `devops/` directory yet, even though the `Makefile` already references paths inside them (`src/`, `tests/`, `devops/docker-compose.yaml`, `devops/Dockerfile`, `devops/terraform/`). When creating the first application code, follow that layout since the tooling already assumes it.

quiz-management is a system for managing exams ("Proyecto para la gestión de Exámenes").

## Tech stack

- Python >=3.12 (pyproject) / 3.14 pinned via `.python-version` — dependency management via Poetry.
- Both `django` and `fastapi` are declared as dependencies, alongside `pydantic` / `pydantic-settings`. Check which framework actually gets used for the HTTP layer once application code exists — the Makefile's `migrations`/`migrate`/`reset_db` targets assume a Django app (`manage.py`) run inside a `migrator` service.
- `httpx` for outbound HTTP, `uvicorn` as ASGI server, `python-dotenv` for env loading.
- Testing: `pytest` + `pytest-asyncio`.
- Linting/formatting: `black`, `isort` (black profile), `flake8`.

## Commands

Most non-trivial commands run through Docker Compose (`devops/docker-compose.yaml`, not yet present) via the `Makefile`.

```bash
make help            # list all available targets

# Docker lifecycle
make up               # pull + build + start all services (detached)
make down             # stop all services
make volume           # remove all volumes and force a clean slate
make prune            # down + volume + docker system prune
make ps               # show service status
make init             # down + volume + up + tf-up (full reset + provision)

# Django / database (run inside the `migrator` compose service)
make migrations       # makemigrations
make migrate          # migrate
make reset_db         # reset_db --noinput --close-sessions

# Code quality
make lint             # black + isort + flake8 on src/ and tests/
make lint-src         # black + isort + flake8 on src/ only
make clean            # remove __pycache__, *.pyc, *.pyo, *~

# Testing
make test             # pytest
make test-dev         # pytest -s -vv
make test-snapshot    # pytest --snapshot-update   (syrupy)

# Docker image build
make docker-build     # buildkit build, target=production, tag tea/backend:dev

# Terraform (devops/terraform/environments/$(ENV), ENV defaults to "local")
make tf-init ENV=qa   # terraform init -reconfigure -upgrade
make tf-plan          # validate + plan
make tf-apply         # apply -auto-approve
make tf-destroy       # destroy -auto-approve
make tf-up ENV=qa     # tf-init + tf-apply
make tf-export-env    # dump terraform s3_bucket_names output into .env
```

To run a single test once a `tests/` directory exists, use plain pytest args, e.g. `pytest tests/path/to/test_file.py::test_name`.

There is no `.env` checked in; `make tf-export-env` appends S3 bucket names produced by Terraform into a local `.env` file.
