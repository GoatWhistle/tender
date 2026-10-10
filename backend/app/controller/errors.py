"""Доменные ошибки в HTTP: статус по таблице, тело `{"code", "message"}`.

Эндпоинт перечисляет свои ошибки в `responses=error_responses(...)`, и они попадают в OpenAPI
вместе с кодами. Ошибка без своей строки в `STATUS` получает статус ближайшего предка.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.domain import errors as e

STATUS: dict[type[e.DomainError], int] = {
    e.DomainError: 400,
    e.StaleRevision: 409,
    e.InvalidFactEdit: 422,
    e.FactNotFound: 404,
    e.SessionNotFound: 404,
    e.IdempotencyConflict: 409,
    e.StaleQuestion: 409,
    e.OptionNotFound: 422,
    e.PositionNotFound: 404,
    e.GroupNotFound: 404,
    e.CatalogEmpty: 503,
    e.ModelFailure: 503,
}


class ErrorBody(BaseModel):
    code: str
    message: str


def status_of(error: type[e.DomainError]) -> int:
    for cls in error.__mro__:
        if cls in STATUS:
            return STATUS[cls]
    return 400


def error_responses(*errors: type[e.DomainError]) -> dict[int | str, dict[str, Any]]:
    """Ошибки эндпоинта для OpenAPI: по статусу — модель тела и перечень кодов."""
    by_status: dict[int, list[str]] = {}
    for error in errors:
        by_status.setdefault(status_of(error), []).append(error.code)
    return {
        status: {"model": ErrorBody, "description": "Коды: " + ", ".join(sorted(codes))}
        for status, codes in sorted(by_status.items())
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(e.DomainError)
    async def domain_error(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, e.DomainError)
        body = ErrorBody(code=exc.code, message=exc.message)
        return JSONResponse(status_code=status_of(type(exc)), content=body.model_dump())
