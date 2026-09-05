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
    net_contents: str | None = Field(
        default=None,
        max_length=100,
        description='As written, e.g. "750 mL". May be blank (the COLA form carries none): the result then '
        "shows what the label says and asks the agent to confirm it",
    )
    bottler: str | None = Field(
        default=None, max_length=300, description="Name and address of bottler/producer/importer"
    )
    country_of_origin: str | None = Field(default=None, max_length=100)
    imported: bool = False


class OcrLine(BaseModel):
    image_index: int = Field(ge=0, le=64)
    text: str = Field(max_length=1000)
    confidence: float = Field(ge=0, le=1)
    box: Quad
    # Type weight measured from the pixels of the warning statement's lines only (stroke width over
    # type height; app/pipeline/typeface.py, D-044 / D-045). None when the line is not part of a
    # located statement or the print was too small or faint to measure. head/tail split a line that
    # carries the warning heading into the heading and the rest; weight_split says how the boundary
    # was found ("gap": the word gap after the heading in the print; "share": the heading's share of
    # the characters, a weaker basis). stroke_px and type_px are the whole line's stroke and type
    # height in the image's own pixels, so lines from reads at different scales compare.
    weight: float | None = Field(default=None, ge=0, le=2)
    weight_head: float | None = Field(default=None, ge=0, le=2)
    weight_tail: float | None = Field(default=None, ge=0, le=2)
    weight_split: str | None = Field(default=None, max_length=8)
    stroke_px: float | None = Field(default=None, ge=0)
    type_px: float | None = Field(default=None, ge=0)


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
        default="absent",
        description="exact | noise | wording | absent | not_required (how the read text relates to 16.21; "
        "exact ignores letter case and spacing, the anchor's capitals are anchor_caps)",
    )
    similarity: float
    found_text: str | None = None
    diff: str | None = Field(default=None, description="Compact word diff: -expected +found")
    anchor_caps: Status
    anchor_bold: Status
    type_weight_ratio: float | None = Field(
        default=None, description="Heading stroke weight over the body's, when measured (D-044 / D-045)"
    )
    type_weight_basis: str | None = Field(
        default=None,
        description="What the ratio compares, or why there is none: 'the rest of its line' (gap or share), "
        "'the other lines', 'too small', 'size differs', 'no heading line', 'boundary uncertain'",
    )
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
    lines: list[OcrLine] = Field(max_length=2000)
    images: list[ImageInfo] = Field(default_factory=list, max_length=64)


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
    requests_in_flight: int = 0
    version: str
    git_sha: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    hint: str | None = None
    request_id: str | None = None
