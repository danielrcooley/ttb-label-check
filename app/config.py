"""Application settings, loaded from environment variables (prefix TTB_).

Every limit that a reviewer might probe is here, named, and documented in LIMITS.md.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "app" / "models"
STATIC_DIR = REPO_ROOT / "app" / "static"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TTB_", env_file=".env", extra="ignore")

    # --- deployment identity
    app_name: str = "Label Check (prototype)"
    agency_name: str | None = Field(default=None, description="Optional agency name for internal branding")
    git_sha: str = Field(default_factory=lambda: os.environ.get("GIT_SHA", "dev"))
    trust_proxy: bool = Field(default=False, description="Trust the first X-Forwarded-For hop for client identity")

    # --- OCR engine
    ocr_workers: int = Field(default_factory=lambda: max(1, min(8, os.cpu_count() or 1)))
    ocr_intra_op_threads: int = 1
    ocr_det_limit_side_len: int = 640
    ocr_rec_batch_num: int = 16
    ocr_use_cls: bool = False
    ocr_ascii_alphabet: bool = Field(
        default=True,
        description="Decode with the recognizer's alphabet restricted to printable ASCII (English label text)",
    )
    ocr_max_side: int = Field(default=1280, description="Images are downscaled to this longest side before OCR")
    ocr_low_conf_retry: float = Field(default=0.80, description="Mean confidence below which a 90-degree retry runs")
    ocr_min_lines_retry: int = Field(default=3, description="Fewer detected lines than this also triggers the retry")
    warning_rescue: bool = Field(
        default=True,
        description="When no warning statement is found upright, re-read the images sideways: the statement "
        "is often printed vertically along the edge of a small label",
    )
    warning_rescue_below: float = Field(
        default=0.5,
        description="Similarity of the best upright statement below which the sideways re-read runs "
        "(a garbled but present statement scores higher and would not be helped)",
    )
    warning_rescue_max_side: int = Field(
        default=2048,
        description="Longest side for the one full-resolution re-read of large artwork whose statement "
        "was unreadable at the working size",
    )
    models_dir: Path = MODELS_DIR

    # --- request limits (see LIMITS.md)
    max_image_bytes: int = 10 * 1024 * 1024
    max_request_bytes: int = 40 * 1024 * 1024
    max_image_pixels: int = 25_000_000
    max_images_per_application: int = 6
    max_compare_items: int = 100
    max_csv_rows: int = 5000
    max_csv_bytes: int = 2 * 1024 * 1024
    per_client_inflight: int = 4
    global_inflight: int = Field(default=24, description="Concurrent metered requests across all clients")
    interactive_wait_seconds: float = Field(
        default=8.0, description="How long an interactive request may wait for a worker slot"
    )

    # --- matching thresholds (tuned against tests/fixtures and real labels; see docs/EVAL_REAL.md)
    match_review_threshold: int = Field(
        default=80,
        description="Fuzzy score at/above which a non-exact match is Needs review rather than a mismatch "
        "(decorative fonts on real labels read at 80-89 while genuinely different names score under 70)",
    )
    match_mismatch_threshold: int = Field(default=70, description="Below this the best candidate counts as Not found")
    warning_mismatch_similarity: float = Field(
        default=0.80, description="Below this the warning is treated as wording differs"
    )
    net_contents_tolerance: float = Field(default=0.01, description="Relative tolerance for unit-conversion rounding")

    @property
    def static_dir(self) -> Path:
        return STATIC_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
