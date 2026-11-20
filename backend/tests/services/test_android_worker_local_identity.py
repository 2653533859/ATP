"""Tests for the loopback-only Android Worker local identity server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.services.android_worker_local_identity import AndroidWorkerLocalIdentityServer


def test_local_identity_server_serves_identity_cors_and_404():
    server = AndroidWorkerLocalIdentityServer(
        worker_id="android-win-pc1",
        queues=["android.android-win-pc1", "mobile_special.android-win-pc1"],
        port=0,
        hostname="PC1",
        generation_fn=lambda: 123456,
        adb_ok_fn=lambda: True,
    )
    assert server.start() is True
    assert server.bound_port is not None and server.bound_port > 0
    base_url = f"http://127.0.0.1:{server.bound_port}"

    try:
        # 1) GET /identity returns non-sensitive worker identity with CORS + PNA headers
        req = urllib.request.Request(
            f"{base_url}/identity",
            headers={"Origin": "http://192.168.3.196:8080"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://192.168.3.196:8080"
            assert resp.headers.get("Access-Control-Allow-Private-Network") == "true"
            assert resp.headers.get("Cache-Control") == "no-store"
            payload = json.loads(resp.read().decode("utf-8"))
            assert payload == {
                "worker_id": "android-win-pc1",
                "hostname": "PC1",
                "adb_ok": True,
                "instance_generation": 123456,
                "queues": ["android.android-win-pc1", "mobile_special.android-win-pc1"],
            }

        # 2) OPTIONS /identity answers browser Private Network Access preflight
        preflight = urllib.request.Request(
            f"{base_url}/identity",
            headers={
                "Origin": "http://192.168.3.196:8080",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Private-Network": "true",
            },
            method="OPTIONS",
        )
        with urllib.request.urlopen(preflight, timeout=3) as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://192.168.3.196:8080"
            assert resp.headers.get("Access-Control-Allow-Private-Network") == "true"

        # 3) Unknown path returns 404
        try:
            urllib.request.urlopen(f"{base_url}/unknown", timeout=3)
            raise AssertionError("Expected 404 for unknown path")
        except urllib.error.HTTPError as err:
            assert err.code == 404
    finally:
        server.stop()

    assert server.bound_port is None
    # stop() is idempotent
    server.stop()


def test_local_identity_server_skips_gracefully_when_port_occupied():
    first = AndroidWorkerLocalIdentityServer(
        worker_id="android-win-first",
        queues=["android.android-win-first"],
        port=0,
    )
    assert first.start() is True
    assert first.bound_port is not None
    try:
        second = AndroidWorkerLocalIdentityServer(
            worker_id="android-win-second",
            queues=["android.android-win-second"],
            port=first.bound_port,
        )
        assert second.start() is False
        assert second.bound_port is None
        second.stop()
    finally:
        first.stop()
