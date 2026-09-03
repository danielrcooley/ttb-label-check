"""Batch-mode requests (X-Batch: 1) must never be refused halfway through a multi-image request."""

from __future__ import annotations

import time

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

from tests.integration.conftest import app_json, image_files

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def one_worker_client():
    with TestClient(create_app(Settings(ocr_workers=1))) as c:
        for _ in range(120):
            if c.get("/api/v1/health").json()["ready"]:
                break
            time.sleep(0.5)
        yield c


def test_two_image_batch_verify_succeeds_on_a_single_worker(one_worker_client, manifest):
    app = manifest["applications"][0]
    r = one_worker_client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-001_front_clean.png", "APP-001_back_clean.png"),
        headers={"X-Batch": "1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "ready_for_approval"
