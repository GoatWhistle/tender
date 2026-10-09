import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from ..config import REVISION, Settings
from ..errors import ServiceError
from ..usecase.worker import GPUWorker
from .errors import STATUS
from .schemas import (
    ChoiceRequest,
    ChoiceResponse,
    NLIRequest,
    NLIResponse,
    PreparedResponse,
    PrepareRequest,
)


class BodyLimit:
    """Ограничить байты до разбора JSON, включая тело по частям."""

    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.limit:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "body_too_large",
                            "message": "Тело запроса превышает OPENJEV_MAX_BODY_BYTES",
                        }
                    },
                )
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def default_runtime(settings):
    os.environ.setdefault("USE_TF", "0")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    from ..adapter.runtime import OpenJevRuntime

    return OpenJevRuntime(settings)


def create_app(settings=None, runtime_factory=None):
    settings = settings or Settings.from_env()
    runtime_factory = runtime_factory or default_runtime

    @asynccontextmanager
    async def lifespan(app):
        worker = GPUWorker(settings, runtime_factory)
        app.state.worker = worker
        worker.start()
        try:
            yield
        finally:
            await worker.stop()

    app = FastAPI(title="Сервис решений OpenJev", version="1.0.0", lifespan=lifespan)
    app.add_middleware(BodyLimit, limit=settings.max_body_bytes)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        status = STATUS[error.code]
        headers = {"Retry-After": "1"} if status in (429, 503) else None
        return JSONResponse(
            status_code=status,
            content={"error": {"code": error.code, "message": str(error)}},
            headers=headers,
        )

    @app.get("/health/live")
    async def live(request: Request):
        worker = request.app.state.worker
        return {
            "status": "alive",
            "worker": worker.state,
            "queued": worker.queue.qsize(),
            "active": worker.active,
            "model_revision": REVISION,
        }

    @app.get("/health/ready")
    async def ready(request: Request):
        if request.app.state.worker.state != "ready":
            raise ServiceError("not_ready", "GPU worker ещё не готов")
        return {
            "status": "ready",
            "device": "cuda",
            "dtype": "bfloat16",
            "attention": "sdpa",
            "runtime": "fla-only",
            "model_revision": REVISION,
        }

    @app.post("/v1/contexts", response_model=PreparedResponse)
    async def prepare(body: PrepareRequest, request: Request):
        return await request.app.state.worker.submit("prepare", body.premise)

    @app.delete("/v1/contexts/{context_id}", status_code=204)
    async def delete(context_id: str, request: Request):
        await request.app.state.worker.submit("delete", context_id)
        return Response(status_code=204)

    @app.post("/v1/nli", response_model=NLIResponse)
    async def nli(body: NLIRequest, request: Request):
        return await request.app.state.worker.submit("nli", body)

    @app.post("/v1/choice", response_model=ChoiceResponse)
    async def choice(body: ChoiceRequest, request: Request):
        return await request.app.state.worker.submit("choice", body)

    return app


app = create_app()
