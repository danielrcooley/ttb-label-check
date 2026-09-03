"""Pydantic models shared by the API and the pipeline.

Coordinates: every box is a quadrilateral of four (x, y) points in the *oriented original
image* space (after EXIF transpose, before any downscaling). The client draws in that space.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

Point = tuple[float, float]
Quad = tuple[Point, Point, Point, Point]


class BeverageType(StrEnum):
    spirits = "spirits"
    wine = "wine"
    malt = "malt"


class Status(StrEnum):
    match = "match"
    needs_review = "needs_review"
    mismatch = "mismatch"
    not_found = "not_found"
    not_checked = "not_checked"
    info = "info"


class Verdict(StrEnum):
    ready_for_approval = "ready_for_approval"
    needs_review = "needs_review"
    issues_found = "issues_found"
    unreadable = "unreadable"


class ApplicationFields(BaseModel):
    """What the agent has in front of them from the COLA application, as written."""

    model_config = ConfigDict(str_strip_whitespace=True)

    application_id: str | None = Field(default=None, max_length=64, description="Agent's reference, e.g. a TTB ID")
    beverage_type: BeverageType
    brand_name: str = Field(min_length=1, max_length=200)
    class_type: str = Field(min_length=1, max_length=200)
    alcohol_content: str | None = Field(
        default=None, max_length=100, description='As written, e.g. "45% Alc./Vol. (90 Proof)"'
    )
    net_contents: str = Field(min_length=1, max_length=100, description='As written, e.g. "750 mL"')
    bottler: str | None = Field(
        default=None, max_length=300, description="Name and address of bottler/producer/importer"
    )
    country_of_origin: str | None = Field(default=None, max_length=100)
    imported: bool = False


class OcrLine(BaseModel):
    image_index: int
    text: str
    confidence: float
    box: Quad


class Evidence(BaseModel):
    image_index: int
    box: Quad
    text: str


class Check(BaseModel):
    id: str
    label: str
    status: Status
    expected: str | None = None
    found: str | None = None
    score: float | None = Field(default=None, description="0-100 similarity where applicable")
    note: str = ""
    rule: str | None = Field(default=None, description="Regulatory citation where applicable")
    evidence: list[Evidence] = Field(default_factory=list)


class WarningReport(BaseModel):
    present: bool
    exact: bool
    assessment: str = Field(
        default="absent", description="exact | case | noise | wording | absent (how the read text relates to 16.21)"
    )
    similarity: float
    found_text: str | None = None
    diff: str | None = Field(default=None, description="Compact word diff: -expected +found")
    anchor_caps: Status
    anchor_bold: Status
    body_not_bold: Status
    evidence: list[Evidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    rule: str = "27 CFR 16.21 (text), 16.22 (format)"


class ImageQuality(BaseModel):
    mean_confidence: float
    line_count: int
    readable: bool
    reason: str | None = None


class ImageInfo(BaseModel):
    index: int
    filename: str | None
    width: int
    height: int
    format: str
    rotated_degrees: int = Field(default=0, description="Rotation applied by the orientation retry, if any")
    quality: ImageQuality


class Timing(BaseModel):
    total_ms: int
    queue_ms: int
    ocr_ms: list[int]


class EngineInfo(BaseModel):
    name: str
    models: dict[str, str]
    workers: int


class ExtractedFields(BaseModel):
    """Best guesses read from the label without application data (extract-only mode)."""

    alcohol_percent: float | None = None
    proof: float | None = None
    net_contents_ml: list[float] = Field(default_factory=list)
    warning_present: bool = False
    origin_lines: list[str] = Field(default_factory=list)
    bottler_lines: list[str] = Field(default_factory=list)
    largest_text: str | None = Field(default=None, description="Tallest line, usually the brand")


class ExtractResponse(BaseModel):
    request_id: str
    images: list[ImageInfo]
    lines: list[OcrLine]
    fields: ExtractedFields
    timing: Timing
    engine: EngineInfo


class CompareResult(BaseModel):
    verdict: Verdict
    checks: list[Check]
    warning: WarningReport
    summary: str


class VerifyResponse(CompareResult):
    request_id: str
    application: ApplicationFields
    images: list[ImageInfo]
    lines: list[OcrLine]
    timing: Timing
    engine: EngineInfo


class CompareItem(BaseModel):
    item_id: str = Field(max_length=128)
    application: ApplicationFields
    lines: list[OcrLine]
    images: list[ImageInfo] = Field(default_factory=list)


class CompareRequest(BaseModel):
    items: list[CompareItem] = Field(min_length=1)


class CompareResponseItem(CompareResult):
    item_id: str


class CompareResponse(BaseModel):
    request_id: str
    results: list[CompareResponseItem]


class HealthResponse(BaseModel):
    status: str
    ready: bool
    error: str | None = Field(default=None, description="Set when OCR warm-up failed")
    engine: EngineInfo
    max_concurrency: int
    in_flight: int
    version: str
    git_sha: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    hint: str | None = None
    request_id: str | None = None
