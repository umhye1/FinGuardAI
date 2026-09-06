import logging
import secrets
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from finguard_ai.classification import LocalClassifier, MissingClassifier
from finguard_ai.config import Settings
from finguard_ai.errors import ServiceUnavailable
from finguard_ai.provider import GeminiProvider
from finguard_ai.rag import RagService
from finguard_ai.repository import CorpusRepository, make_pool
from finguard_ai.schemas import ClassificationRequest, ClassificationResult, QuestionRequest, RagResult

log = logging.getLogger(__name__)


@dataclass
class Services:
    classifier: object
    repository: object | None
    provider: object
    classifier_ready: bool


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=65536):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await JSONResponse(status_code=413, content={"error": "REQUEST_TOO_LARGE"})(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(settings: Settings | None = None, injected: Services | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or Settings()
        app.state.settings = config
        app.state.capacity = threading.BoundedSemaphore(config.max_concurrent_requests)
        pool = provider = None
        try:
            if injected:
                app.state.services = injected
            else:
                provider = GeminiProvider(config)
                repository = None
                if config.connection_info:
                    pool = make_pool(config.connection_info, config.pool_max_size)
                    pool.open()
                    repository = CorpusRepository(pool)
                if config.classifier_mode == "gemini":
                    classifier, ready = provider, provider.configured
                else:
                    try:
                        classifier = LocalClassifier(config.classifier_path, config.allow_demo_model)
                        ready = True
                    except (OSError, ValueError, KeyError, TypeError):
                        classifier, ready = MissingClassifier(), False
                        log.warning("Classifier artifact missing or invalid; classification returns 503")
                app.state.services = Services(classifier, repository, provider, ready)
            yield
        finally:
            if pool:
                pool.close()
            if provider:
                provider.close()

    app = FastAPI(
        title="FinGuardAI Internal API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(BodyLimitMiddleware)

    def authorize(request: Request, x_service_token: str = Header(default="")):
        expected = request.app.state.settings.service_token.get_secret_value()
        if not secrets.compare_digest(x_service_token.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="INVALID_SERVICE_TOKEN")

    def reserve(request: Request):
        limiter = request.app.state.capacity
        if not limiter.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="AI_CAPACITY_EXCEEDED")
        try:
            yield
        finally:
            limiter.release()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(status_code=422, content={"error": "INVALID_REQUEST"})

    async def unavailable(request, exc):
        return JSONResponse(status_code=503, content={"error": "AI_UNAVAILABLE"})

    app.add_exception_handler(ServiceUnavailable, unavailable)
    app.add_exception_handler(psycopg.Error, unavailable)
    app.add_exception_handler(PoolTimeout, unavailable)

    @app.get("/health/live")
    def live():
        return {"status": "UP"}

    @app.get("/health/ready")
    def ready(request: Request):
        services = request.app.state.services
        if not services.classifier_ready or not services.provider.configured or services.repository is None:
            return JSONResponse(status_code=503, content={"status": "NOT_READY"})
        services.repository.ready()
        return {"status": "UP"}

    @app.post(
        "/internal/v1/classifications",
        response_model=ClassificationResult,
        dependencies=[Depends(authorize), Depends(reserve)],
    )
    def classify(body: ClassificationRequest, request: Request):
        return request.app.state.services.classifier.classify(body.text)

    @app.post(
        "/internal/v1/rag/answers",
        response_model=RagResult,
        dependencies=[Depends(authorize), Depends(reserve)],
    )
    def answer(body: QuestionRequest, request: Request):
        services = request.app.state.services
        return RagService(services.repository, services.provider, request.app.state.settings).answer(
            body.question
        )

    return app


app = create_app()
