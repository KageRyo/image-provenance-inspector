"""FastAPI application for Image Provenance Inspector."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .analyzers.comparison import compare_images
from .analyzers.image import inspect_image
from .api.analyze import service
from .errors import AnalysisError
from .models.result import (
    AnalysisResult,
    CompareResult,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
)

MAX_UPLOAD_BYTES = int(os.getenv("IPI_MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))

app = FastAPI(
    title="Image Provenance Inspector",
    description="Inspect image metadata, C2PA Content Credentials, and editing provenance.",
    version="0.1.0",
)


def _error_response(
    *, code: str, message: str, details: list[ErrorDetail] | None = None, status_code: int
) -> JSONResponse:
    payload = ErrorResponse(code=code, message=message, details=details or [])
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AnalysisError(
            code="payload_too_large",
            message=f"Uploaded files must be {MAX_UPLOAD_BYTES} bytes or smaller.",
            status_code=413,
        )
    if not data:
        raise AnalysisError(
            code="empty_file", message="The uploaded file is empty.", status_code=422
        )
    return data


@app.exception_handler(AnalysisError)
async def analysis_error_handler(_: Request, exc: AnalysisError) -> JSONResponse:
    return _error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(
            location=[str(part) if not isinstance(part, int) else part for part in error["loc"]],
            message=error["msg"],
            type=error["type"],
        )
        for error in exc.errors()
    ]
    return _error_response(
        code="validation_error",
        message="The request did not match the API schema.",
        details=details,
        status_code=422,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(code="http_error", message=str(exc.detail), status_code=exc.status_code)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/api/v1/analyze",
    response_model=AnalysisResult,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    tags=["analysis"],
    summary="Analyze one image",
)
async def analyze(
    image: Annotated[UploadFile, File(description="Image to inspect")],
) -> AnalysisResult:
    data = await _read_upload(image)
    return service.analyze(data)


@app.post(
    "/api/v1/compare",
    response_model=CompareResult,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    tags=["analysis"],
    summary="Compare an original and edited image",
)
async def compare(
    original: Annotated[UploadFile, File(description="Original image")],
    edited: Annotated[UploadFile, File(description="Edited image")],
) -> CompareResult:
    original_data = await _read_upload(original)
    edited_data = await _read_upload(edited)
    original_info, _ = inspect_image(original_data)
    edited_info, _ = inspect_image(edited_data)
    metrics, difference = compare_images(original_data, edited_data)
    return CompareResult(
        original=original_info,
        edited=edited_info,
        metrics=metrics,
        difference=difference,
    )
