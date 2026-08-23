"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.base")

application = get_asgi_application()

from src.shared.presentation.auth_middleware import AuthMiddleware
from src.shared.presentation.rate_limit_middleware import RateLimitMiddleware
from src.shared.presentation.schema import get_context, schema

subgraph_path = "/quizzes/"
subgraph_prefix = "/api/graph"

graphql_app = GraphQLRouter(
    schema,
    path=subgraph_path,
    context_getter=get_context,
)
fastapp = FastAPI()
# Starlette applies middleware in reverse of add order (last added runs
# first) — AuthMiddleware added last so RateLimitMiddleware actually runs
# outermost, rejecting before JWT decode.
fastapp.add_middleware(AuthMiddleware)
fastapp.add_middleware(RateLimitMiddleware)
fastapp.include_router(graphql_app, prefix=subgraph_prefix)
