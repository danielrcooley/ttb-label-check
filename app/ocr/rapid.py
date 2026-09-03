"""RapidOCR (ONNX Runtime) engine with vendored models and explicit thread settings.

Model files come only from ``settings.models_dir`` (see tools/vendor_models.py and
app/models/MANIFEST.json). Nothing is downloaded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from app.config import Settings

from .base import RawLine

log = logging.getLogger(__name__)


class RapidEngine:
    name = "rapidocr-onnxruntime"

    def __init__(self, settings: Settings) -> None:
        from rapidocr import RapidOCR

        manifest = json.loads((settings.models_dir / "MANIFEST.json").read_text(encoding="utf-8"))
        models = {role: settings.models_dir / m["file"] for role, m in manifest["models"].items()}
        for role, path in models.items():
            if not Path(path).exists():
                raise FileNotFoundError(f"vendored OCR model missing: {role} -> {path}")
        params = {
            "Global.use_cls": settings.ocr_use_cls,
            "Global.log_level": "warning",
            "Det.model_path": str(models["det"]),
            "Rec.model_path": str(models["rec"]),
            "Det.limit_side_len": settings.ocr_det_limit_side_len,
            "Rec.rec_batch_num": settings.ocr_rec_batch_num,
            "EngineConfig.onnxruntime.intra_op_num_threads": settings.ocr_intra_op_threads,
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        }
        if "cls" in models:
            params["Cls.model_path"] = str(models["cls"])
        self._ocr = RapidOCR(params=params)
        self._models = {role: f"{m['file']} (sha256 {m['sha256'][:12]})" for role, m in manifest["models"].items()}
        try:
            from importlib.metadata import version

            self._version = f"rapidocr {version('rapidocr')} / onnxruntime {version('onnxruntime')}"
        except Exception:  # pragma: no cover - metadata missing in odd environments
            self._version = "rapidocr"

    def recognize(self, rgb: np.ndarray) -> list[RawLine]:
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])
        result: Any = self._ocr(bgr)
        boxes, txts, scores = (
            getattr(result, "boxes", None),
            getattr(result, "txts", None),
            getattr(result, "scores", None),
        )
        if boxes is None or not txts:
            return []
        lines: list[RawLine] = []
        confs = list(scores) if scores is not None else [0.0] * len(txts)
        for box, text, score in zip(boxes, txts, confs, strict=True):
            if len(box) != 4 or not text or not str(text).strip():
                continue
            quad = (
                (float(box[0][0]), float(box[0][1])),
                (float(box[1][0]), float(box[1][1])),
                (float(box[2][0]), float(box[2][1])),
                (float(box[3][0]), float(box[3][1])),
            )
            lines.append(RawLine(text=str(text).strip(), confidence=float(score), box=quad))
        return lines

    def info(self) -> dict[str, str]:
        return {"engine": self._version, **self._models}
