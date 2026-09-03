"""Proof that the verification path makes no network calls (restricted-network requirement).

Every socket connection attempt raises during the test; a full verify must still succeed.
"""

from __future__ import annotations

import socket

import pytest

from tests.integration.conftest import app_json, image_files

pytestmark = pytest.mark.integration


class _NoNetworkError(Exception):
    pass


def test_verify_completes_with_all_network_access_blocked(client, manifest, monkeypatch):
    def refuse(self, *args, **kwargs):
        raise _NoNetworkError(f"outbound connection attempted: {args[:1]}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    app = manifest["applications"][0]
    r = client.post(
        "/api/v1/verify",
        data={"application": app_json(app)},
        files=image_files("APP-001_front_clean.png", "APP-001_back_clean.png"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "ready_for_approval"
