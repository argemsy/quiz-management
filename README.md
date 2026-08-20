# quiz-management

Proyecto para la gestión de Exámenes. Backend en Python organizado con capas DDD
(domain/application/infrastructure/presentation) sobre 3 apps de Django, con GraphQL
como interfaz principal de la API.

## Stack

- **Python 3.12+** (3.14 vía `.python-version`), dependencias con **Poetry**.
- **Django 6.1** sirve el panel de administración (`manage.py`, puerto `8000`).
- **FastAPI 0.141** sirve GraphQL vía `strawberry-graphql` (federation schema, puerto `8500`).
  Son dos procesos independientes (no comparten servidor).
- **Postgres 15** como base de datos (`psycopg2-binary` + `dj-database-url`).
- **Redis 7** disponible como servicio de infraestructura (aún sin consumidores en el código).
- **Event bus** en memoria (in-process pub/sub), con patrón dead-letter en la app `eventing`.
- Auth por JWT (`PyJWT`) con clases de permisos custom en GraphQL — no se usa el sistema de
  permisos de Django.
- **Testing**: `pytest` + `pytest-django` + `pytest-asyncio`.
- **Linting**: `black` + `isort` + `flake8`.

## Apps

| App | Capas | Descripción |
|---|---|---|
| `quiz` | DDD completo | Exámenes, preguntas, respuestas, resultados |
| `eventing` | DDD completo | Dead-letter/outbox para el event bus |
| `account` | infra + presentation | Usuario custom (`MyUser`, UUID como PK), organizaciones (`Tenant`) y su membresía (`UserTenant`) |
| `shared` | cross-cutting | Event bus, exceptions, schema GraphQL base, decoradores |

## Levantar el proyecto

Todo corre vía Docker Compose, orquestado con `make`:

```bash
make help    # ver todos los targets disponibles
make init    # down + volume + up (build + start de todos los servicios)
make ps      # ver estado de los servicios
```

Servicios: `admin` (Django, `:8000`), `api` (FastAPI/GraphQL, `:8500`), `db` (Postgres, `:5432`),
`redis` (`:6379`), `migrator` (corre las migraciones al arrancar).

### Variables de entorno

Copiar `devops/docker.env.example` a `devops/docker.env` y completar los valores antes de
`make up`. Ese archivo es el que se inyecta en los contenedores — no confundir con un `.env`
en la raíz, que solo lo leerían procesos corridos directo en el host.

## Comandos frecuentes

```bash
make test           # pytest
make test-dev        # pytest -s -vv
make lint            # black + isort + flake8 sobre src/ y tests/
make migrations      # makemigrations (dentro del servicio migrator)
make migrate         # migrate (dentro del servicio migrator)
```

Ver `Makefile` para la lista completa de targets.

## Documentación para desarrollo

Las convenciones de código, patrones obligatorios y estructura del proyecto están
documentadas en [`CLAUDE.md`](./CLAUDE.md) (y el detalle extendido en `docs/claude/`).
