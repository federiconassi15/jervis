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



def test_control_center_logs_are_auth_scoped_and_sanitized(tmp_path):
    from jervis.observability import EventJournal, read_events
    from jervis.control_center import ControlCenter
    import http.client
    import threading
    import json

    paths = _paths(tmp_path)
    with_logs = EventJournal(paths.logs)
    with_logs.emit("runtime.started")
    with_logs.close()
    center = ControlCenter(paths=paths)
    worker = threading.Thread(target=center.serve, daemon=True)
    worker.start()
    try:
        client = http.client.HTTPConnection("127.0.0.1", center.port, timeout=3)
        client.request("GET", "/api/logs")
        assert client.getresponse().status == 401
        client.close()
        client = http.client.HTTPConnection("127.0.0.1", center.port, timeout=3)
        # Existing authenticated session bootstrap, same as the UI.
        client.request("GET", center.url.split("127.0.0.1:" + str(center.port))[-1])
        reply = client.getresponse()
        assert reply.status == 302
        cookie = reply.getheader("Set-Cookie").split(";", 1)[0]
        reply.read()
        client.request("GET", "/api/logs", headers={"Cookie": cookie})
        log_response = client.getresponse()
        assert log_response.status == 200
        data = json.loads(log_response.read())
        assert data[0]["code"] == "runtime.started"
        client.close()
    finally:
        center.close()
        worker.join(timeout=3)



def test_control_center_operations_is_private_and_only_reports_counts(tmp_path):
    import json
    import sqlite3

    from jervis.control_center import ControlCenter
    from jervis.mission_engine import MissionStore, MissionStep
    from jervis.capabilities import Principal

    p = _paths(tmp_path)
    missions = MissionStore(p.data / "missions.sqlite3")
    try:
        owner = Principal("owner", "owner", True)
        mission = missions.create(owner, (
            MissionStep("read", "system.status.read", "", {}, True),
        ))
        assert mission
    finally:
        missions.close()
    with sqlite3.connect(p.data / "automation.sqlite3") as db:
        db.execute("CREATE TABLE pending_actions(status TEXT, private_user TEXT)")
        db.execute("INSERT INTO pending_actions VALUES('waiting_approval','sensitive')")
    center = ControlCenter(p)
    worker = threading.Thread(target=center.serve, daemon=True)
    worker.start()
    try:
        def query(cookie=None):
            client = http.client.HTTPConnection("127.0.0.1", center.port, timeout=3)
            header = {"Cookie": "jervis_session=" + cookie} if cookie else {}
            client.request("GET", "/api/operations", headers=header)
            result = client.getresponse()
            payload = result.read().decode()
            status = result.status
            client.close()
            return status, payload
        assert query()[0] == 401
        code, raw = query(center.url.rsplit("/", 1)[-1])
        assert code == 200
        assert "sensitive" not in raw and "owner" not in raw
        data = json.loads(raw)
        assert data["missions"]["queued"] == 1
        assert data["automations"]["pending_approval"] == 1
    finally:
        center.close()
        worker.join(timeout=5)
