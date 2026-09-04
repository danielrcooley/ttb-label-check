from __future__ import annotations

from typing import cast

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.config import Settings
from app.csvio import parse_csv, template_csv
from app.schemas import ApplicationFields
from app.security import request_id_of

router = APIRouter(prefix="/api/v1/csv", tags=["batch"])


class CsvRowOut(BaseModel):
    row_number: int
    application: ApplicationFields | None
    images: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CsvParseResponse(BaseModel):
    request_id: str
    rows: list[CsvRowOut]
    columns: list[str]
    unmapped_columns: list[str]
    delimiter: str
    warnings: list[str]


@router.get("/template", response_class=PlainTextResponse, summary="Download the batch CSV template")
async def csv_template() -> PlainTextResponse:
    return PlainTextResponse(
        template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="label-check-batch-template.csv"'},
    )


@router.post("/parse", response_model=CsvParseResponse, summary="Parse and validate a batch CSV of application rows")
async def csv_parse(request: Request, file: UploadFile = File(...)) -> CsvParseResponse:
    settings = cast(Settings, request.app.state.settings)
    data = await file.read(settings.max_csv_bytes + 1)
    if len(data) > settings.max_csv_bytes:
        raise HTTPException(status_code=413, detail=f"CSV larger than {settings.max_csv_bytes // 1024} KB.")
    result = parse_csv(data, max_rows=settings.max_csv_rows)
    return CsvParseResponse(
        request_id=request_id_of(request),
        rows=[
            CsvRowOut(row_number=r.row_number, application=r.application, images=r.images, errors=r.errors)
            for r in result.rows
        ],
        columns=result.columns,
        unmapped_columns=result.unmapped_columns,
        delimiter=result.delimiter,
        warnings=result.warnings,
    )
