from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rag.domain.errors import (
    DomainError,
    IndexNotReady,
    InputError,
    ModelFailure,
    NotFound,
    StageError,
)

STATUS: list[tuple[type[DomainError], int]] = [
    (NotFound, 404),
    (StageError, 409),
    (InputError, 422),
    (ModelFailure, 502),
    (IndexNotReady, 503),
]


def status_of(exc: DomainError) -> int:
    return next((code for kind, code in STATUS if isinstance(exc, kind)), 400)


async def domain_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(
        status_code=status_of(exc), content={"detail": exc.message, "code": exc.code}
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error)
