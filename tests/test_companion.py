"""Companion session security and TLS smoke tests."""
import http.client
import json
import ssl
import threading

from jervis.companion import CompanionServer, PairingRegistry
from jervis.paths import Paths


def _paths(tmp_path):
    result = Paths(tmp_path, tmp_path / "config", tmp_path / "data",
                   tmp_path / "logs", tmp_path / "cache")
    result.ensure()
    return result


def test_pairing_code_is_single_use_and_tokens_are_scoped():
    registry = PairingRegistry()
    assert registry.pair("00000000" if registry.code != "00000000" else "99999999") is None
    token = registry.pair(registry.code)
    assert token and registry.authorized(token)
    assert registry.pair("anything") is None
    assert not registry.authorized("wrong")
    registry.revoke_all()
    assert not registry.authorized(token)


def test_repeated_bad_codes_lock_out_registry():
    registry = PairingRegistry()
    good = registry.code
    for _ in range(5):
        assert registry.pair("wrong") is None
    assert registry.pair(good) is None


def test_server_requires_tls_and_pairing(tmp_path):
    server = CompanionServer(paths=_paths(tmp_path))
    worker = threading.Thread(target=server.serve, daemon=True)
    worker.start()
    try:
        assert server.http.server_address[0] == "127.0.0.1"
        assert len(server.fingerprint) == 64
        ctx = ssl._create_unverified_context()  # Test only: production clients pin cert.
        def call(method, path, body=None, headers=None):
            conn = http.client.HTTPSConnection("127.0.0.1", server.port,
                                               context=ctx, timeout=4)
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            content = resp.read()
            conn.close()
            return resp.status, content
        assert call("GET", "/api/status")[0] == 401
        body = json.dumps({"code": server.registry.code})
        code, raw = call("POST", "/pair", body, {
            "Content-Type": "application/json"
        })
        assert code == 200
        token = json.loads(raw)["token"]
        status, data = call("GET", "/api/status",
                            headers={"Authorization": "Bearer " + token})
        assert status == 200
        result = json.loads(data)
        assert "version" in result
        assert "config_present" in result
        assert "credentials" not in result
        assert call("POST", "/command", "{}", {
            "Content-Type": "application/json"
        })[0] == 404
    finally:
        server.close()
        worker.join(timeout=5)
