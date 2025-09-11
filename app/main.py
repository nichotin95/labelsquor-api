"""
LabelSquor API - Modern FastAPI application with advanced features
"""
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette_context import plugins
from starlette_context.middleware import ContextMiddleware
import sentry_sdk
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import setup_logging, log
from app.core.exceptions import BaseAPIException, handle_api_exception, handle_unexpected_exception
from app.middleware import (
    RequestIDMiddleware,
    TimingMiddleware,
    SecurityHeadersMiddleware
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    """
    # Startup
    log.info("Starting LabelSquor API", version=settings.VERSION, env=settings.ENVIRONMENT)
    
    # Setup logging
    setup_logging()
    
    # Initialize Sentry if configured
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
        log.info("Sentry initialized")
    
    # Initialize database connections, caches, etc.
    # await init_db()
    
    yield
    
    # Shutdown
    log.info("Shutting down LabelSquor API")
    # Close database connections, cleanup resources
    # await close_db()


def create_application() -> FastAPI:
    """
    Create FastAPI application with all configurations
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
        default_response_class=ORJSONResponse,  # Fast JSON responses
        lifespan=lifespan,
        debug=settings.DEBUG,
        # Advanced OpenAPI customization
        openapi_tags=[
            {"name": "health", "description": "Health check endpoints"},
            {"name": "brands", "description": "Brand management"},
            {"name": "products", "description": "Product management"},
            {"name": "categories", "description": "Category taxonomy"},
            {"name": "search", "description": "Search functionality"},
        ],
        swagger_ui_parameters={
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
            "syntaxHighlight.theme": "monokai"
        }
    )
    
    # Add custom exception handlers
    app.add_exception_handler(BaseAPIException, handle_api_exception)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_exception_handler(Exception, handle_unexpected_exception)
    
    # Add middleware stack (order matters!)
    
    # 1. Sentry error tracking (outermost)
    if settings.SENTRY_DSN:
        app.add_middleware(SentryAsgiMiddleware)
    
    # 2. CORS
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-Process-Time"]
        )
    
    # 3. GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # 4. Security headers
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 5. Request context (correlation IDs)
    app.add_middleware(
        ContextMiddleware,
        plugins=(
            plugins.RequestIdPlugin(),
            plugins.CorrelationIdPlugin(
                header_name="X-Correlation-ID",
                force_new_uuid=False
            ),
        )
    )
    
    # 6. Custom middleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(TimingMiddleware)
    
    # Add API routes
    app.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Add Prometheus metrics
    if settings.ENVIRONMENT != "development":
        instrumentator = Instrumentator()
        instrumentator.instrument(app).expose(app, endpoint="/metrics")
    
    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> Dict[str, Any]:
        """Root endpoint with API information"""
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "docs": f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
            "openapi": f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        }
    
    # GraphQL endpoint (optional)
    if settings.ENABLE_GRAPHQL:
        from strawberry.fastapi import GraphQLRouter
        from app.graphql import schema
        
        graphql_app = GraphQLRouter(
            schema,
            graphiql=settings.DEBUG,
            context_getter=lambda: {"settings": settings}
        )
        app.include_router(
            graphql_app, 
            prefix="/graphql",
            tags=["graphql"]
        )
    
    return app


# Create the application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS if not settings.DEBUG else 1,
        log_config=None,  # Use our custom logging
        access_log=False,  # We handle access logs in middleware
        server_header=False,  # Don't expose server info
        date_header=False,  # Let nginx handle this
    )
