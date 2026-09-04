"""Admission limiter: per-client and global caps, release on every path, client identity behind a proxy."""

from __future__ import annotations

from app.config import Settings
from app.security import AdmissionLimiter
from starlette.requests import Request


def _req(client: str = "10.0.0.1", xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/verify",
        "headers": headers,
        "client": (client, 1234),
        "query_string": b"",
    }
    return Request(scope)


def test_per_client_cap_then_release():
    lim = AdmissionLimiter(Settings(per_client_inflight=2, global_inflight=10))
    a, b, c = _req(), _req(), _req()
    assert lim.acquire(a) is None and lim.acquire(b) is None
    assert lim.acquire(c) == "too_many_inflight"
    assert lim.in_flight == 2
    lim.release(a)
    assert lim.acquire(c) is None  # the freed slot is reusable
    lim.release(b)
    lim.release(c)
    assert lim.in_flight == 0
    lim.release(c)  # releasing twice is harmless: the request was already accounted for
    assert lim.in_flight == 0


def test_global_cap_applies_across_clients():
    lim = AdmissionLimiter(Settings(per_client_inflight=10, global_inflight=2))
    assert lim.acquire(_req("10.0.0.1")) is None
    assert lim.acquire(_req("10.0.0.2")) is None
    assert lim.acquire(_req("10.0.0.3")) == "service_busy"


def test_release_of_a_request_that_was_never_admitted_is_a_no_op():
    lim = AdmissionLimiter(Settings(per_client_inflight=1, global_inflight=10))
    r = _req()
    assert lim.acquire(r) is None
    refused = _req()
    assert lim.acquire(refused) == "too_many_inflight"
    lim.release(refused)
    assert lim.in_flight == 1  # the admitted request still holds its slot


def test_client_identity_uses_the_last_forwarded_address_only_when_the_proxy_is_trusted():
    trusted = AdmissionLimiter(Settings(trust_proxy=True))
    assert trusted.client_id(_req("10.0.0.9", xff="1.2.3.4, 5.6.7.8")) == "5.6.7.8"
    assert trusted.client_id(_req("10.0.0.9")) == "10.0.0.9"
    untrusted = AdmissionLimiter(Settings(trust_proxy=False))
    assert untrusted.client_id(_req("10.0.0.9", xff="1.2.3.4, 5.6.7.8")) == "10.0.0.9"
