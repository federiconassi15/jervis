"""Control Center isolation and authentication tests."""
import http.client
import threading

from jervis.control_center import ControlCenter
from jervis.paths import Paths


def _paths(tmp_path):
    p = Paths(tmp_path, tmp_path / "config", tmp_path / "data",
              tmp_path / "logs", tmp_path / "cache")
    p.ensure()
    return p


def test_loopback_center_rejects_unauthorized_and_dns_rebinding(tmp_path):
    server = ControlCenter(_paths(tmp_path))
    worker = threading.Thread(target=server.serve, daemon=True)
    worker.start()
    try:
        client = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
        client.request("GET", "/api/overview")
        response = client.getresponse()
        assert response.status == 401
        response.read()
        client.close()

        client = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
        client.request("GET", "/", headers={"Host": "attacker.invalid"})
        response = client.getresponse()
        assert response.status == 403
        response.read()
        client.close()

        cookie = server.url.rsplit("/", 1)[-1]
        client = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
        client.request("GET", "/api/overview", headers={
            "Cookie": "jervis_session=" + cookie,
            "Origin": "https://attacker.invalid",
        })
        response = client.getresponse()
        assert response.status == 403
        response.read()
        client.close()
    finally:
        server.close()
        worker.join(timeout=5)


def test_control_center_private_unlock_and_read_only_json(tmp_path):
    server = ControlCenter(_paths(tmp_path))
    worker = threading.Thread(target=server.serve, daemon=True)
    worker.start()
    try:
        secret = server.url.rsplit("/", 1)[-1]
        def get(route, headers=None):
            client = http.client.HTTPConnection("127.0.0.1", server.port, timeout=3)
            client.request("GET", route, headers=headers or {})
            response = client.getresponse()
            body = response.read().decode()
            code = response.status
            hdrs = dict(response.getheaders())
            client.close()
            return code, body, hdrs
        code, _, hdr = get("/unlock/" + secret)
        assert code == 302 and hdr["Location"] == "/"
        assert "HttpOnly" in hdr["Set-Cookie"]
        cookie = {"Cookie": "jervis_session=" + secret}
        assert get("/", cookie)[0] == 200
        code, body, _ = get("/api/overview", cookie)
        assert code == 200 and "recovery_snapshots" in body
        assert "version" in body
        assert get("/api/secrets", cookie)[0] == 404
    finally:
        server.close()
        worker.join(timeout=5)


def test_port_is_always_bound_to_loopback(tmp_path):
    server = ControlCenter(_paths(tmp_path))
    try:
        assert server.http.server_address[0] == "127.0.0.1"
        assert server.port > 0
    finally:
        # No serve_forever loop started; shutdown() would block.
        server.http.server_close()
