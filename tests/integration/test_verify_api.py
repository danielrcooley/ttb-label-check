"""End-to-end checks through the API with the real OCR engine on committed fixtures."""

from __future__ import annotations

import pytest

from tests.integration.conftest import app_json, image_files

pytestmark = pytest.mark.integration


def _app(manifest, app_id):
    return next(a for a in manifest["applications"] if a["id"] == app_id)


def _check(resp, check_id):
    return next(c for c in resp["checks"] if c["id"] == check_id)


def test_clean_front_and_back_is_ready_for_approval(client, manifest):
    app = _app(manifest, "APP-001")  # Old Tom Distillery, the brief's sample
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-001_front_clean.png", "APP-001_back_clean.png"),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verdict"] == "ready_for_approval", body["summary"]
    assert body["warning"]["present"] and body["warning"]["exact"]
    for cid in ("brand_name", "class_type", "alcohol_content", "net_contents", "bottler", "country_of_origin"):
        assert _check(body, cid)["status"] == "match", (cid, _check(body, cid))
    assert all(c["evidence"] for c in body["checks"] if c["status"] == "match")
    assert body["timing"]["total_ms"] < 15000  # generous for CI; the deployed gate is measured separately


def test_wrong_abv_on_label_is_an_issue(client, manifest):
    app = _app(manifest, "APP-001")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-001_front_wrong_abv.png", "APP-001_back_clean.png"),
    )
    body = r.json()
    assert body["verdict"] == "issues_found"
    assert _check(body, "alcohol_content")["status"] == "mismatch"


def test_title_case_warning_anchor_needs_review(client, manifest):
    app = _app(manifest, "APP-002")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-002_front_clean.png", "APP-002_back_titlecase.png"),
    )
    body = r.json()
    assert body["warning"]["present"]
    assert body["warning"]["anchor_caps"] == "needs_review"
    assert body["verdict"] in ("needs_review", "issues_found")


def test_altered_warning_wording_is_an_issue(client, manifest):
    app = _app(manifest, "APP-004")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-004_front_clean.png", "APP-004_back_altered.png"),
    )
    body = r.json()
    assert body["warning"]["present"] and not body["warning"]["exact"]
    assert "-may" in (body["warning"]["diff"] or "")
    assert body["verdict"] == "issues_found"


def test_missing_warning_is_an_issue(client, manifest):
    app = _app(manifest, "APP-006")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-006_front_clean.png", "APP-006_back_missing.png"),
    )
    body = r.json()
    assert not body["warning"]["present"]
    assert body["verdict"] == "issues_found"


def test_case_only_brand_difference_is_a_match_with_note(client, manifest):
    """Dave's case: application says Stone's Throw, label says STONE'S THROW."""
    app = _app(manifest, "APP-002")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app, brand_name="Stone's Throw")},
        files=image_files("APP-002_front_clean.png", "APP-002_back_clean.png"),
    )
    body = r.json()
    brand = _check(body, "brand_name")
    assert brand["status"] == "match" and "case" in brand["note"]


def test_sideways_image_is_recovered_by_rotation_retry(client, manifest):
    app = _app(manifest, "APP-004")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-004_front_clean.png", "APP-004_back_rotate90.png"),
    )
    body = r.json()
    back = body["images"][1]
    assert back["rotated_degrees"] in (90, 270)
    assert body["warning"]["present"]


def test_front_only_reports_warning_missing_with_guidance(client, manifest):
    app = _app(manifest, "APP-001")
    r = client.post("/api/v1/verify", data={"application": app_json(app)}, files=image_files("APP-001_front_clean.png"))
    body = r.json()
    assert not body["warning"]["present"]
    assert "not uploaded" in body["warning"]["notes"][0]


def test_extract_reads_fields_without_application_data(client):
    r = client.post("/api/v1/extract", files=image_files("APP-001_front_clean.png", "APP-001_back_clean.png"))
    assert r.status_code == 200, r.text
    f = r.json()["fields"]
    assert f["alcohol_percent"] == 45.0 and f["proof"] == 90.0
    assert 750.0 in f["net_contents_ml"]
    assert f["warning_present"]


def test_bad_inputs_get_clear_errors(client, manifest):
    app = _app(manifest, "APP-001")
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=[("images", ("x.pdf", b"%PDF-1.7 fake", "application/pdf"))],
    )
    assert r.status_code == 415 and r.json()["code"] == "unsupported_format"
    r = client.post("/api/v1/verify", data={"application": "not json"}, files=image_files("APP-001_front_clean.png"))
    assert r.status_code == 422
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app, brand_name="")},
        files=image_files("APP-001_front_clean.png"),
    )
    assert r.status_code == 422 and "brand_name" in r.json()["message"]


def test_health_reports_engine_and_capacity(client):
    body = client.get("/api/v1/health").json()
    assert body["ready"] and body["max_concurrency"] >= 1
    assert "det" in body["engine"]["models"]


def test_ready_probe_answers_200_once_warm(client):
    r = client.get("/api/v1/ready")
    assert r.status_code == 200 and r.json() == {"ready": True}


def test_request_id_in_body_matches_the_header(client, manifest):
    app = manifest["applications"][0]
    r = client.post("/api/v1/verify", data={"application": app_json(app)}, files=image_files("APP-001_front_clean.png"))
    assert r.json()["request_id"] == r.headers["X-Request-ID"]
    assert "Server-Timing" in r.headers and "Content-Security-Policy" in r.headers


def test_early_rejections_carry_security_headers_and_do_not_crash(client):
    r = client.post(
        "/api/v1/extract",
        content=b"x",
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "abc"},
    )
    assert r.status_code == 400 and "Content-Security-Policy" in r.headers
    assert r.headers["Server-Timing"].startswith("total;dur=")
    r = client.post(
        "/api/v1/extract",
        content=b"x" * 10,
        headers={"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "99999999999"},
    )
    assert r.status_code == 413 and r.json()["code"] == "request_too_large"
    assert r.headers["Server-Timing"].startswith("total;dur=") and r.headers["X-Request-ID"]
