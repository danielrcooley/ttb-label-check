from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "labels"


@pytest.fixture(scope="session")
def manifest() -> dict:
    return json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def client():
    settings = Settings(ocr_workers=2)
    app = create_app(settings)
    with TestClient(app) as c:
        for _ in range(120):  # wait for the pool to warm (models load in the background)
            if c.get("/api/v1/health").json()["ready"]:
                break
            time.sleep(0.5)
        else:
            pytest.fail("OCR pool did not become ready")
        yield c


def app_json(app: dict, **overrides) -> str:
    fields = {
        "application_id": app["id"],
        "beverage_type": app["beverage_type"],
        "brand_name": app["brand"],
        "class_type": app["class_type"],
        "alcohol_content": app["alcohol_content"],
        "net_contents": app["net_contents"],
        "bottler": app["bottler"],
        "country_of_origin": app["origin"].replace("Product of ", ""),
        "imported": "USA" not in app["origin"],
    }
    fields.update(overrides)
    return json.dumps(fields)


def image_files(*names: str):
    return [("images", (n, (FIXTURES / n).read_bytes(), "image/png")) for n in names]
