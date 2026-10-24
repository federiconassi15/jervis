"""Jervis 8.1 Companion Mode: explicitly enabled TLS LAN status pairing.

Read-only remote capabilities only. No audio, transcripts, credentials, remote
commands or privileged repair endpoints are exposed. Devices pair with a
short-lived one-use code over TLS, with an independent bearer token.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import ssl
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .paths import Paths

_MAX_BODY = 512


class PairingRegistry:
    """Ephemeral capability grants: one-time pairing, revocable and expiring."""

    def __init__(self):
        self.code = f"{secrets.randbelow(100_000_000):08d}"
        self.expires_at = time.monotonic() + 300
        self.failures = 0
        self._tokens: dict[str, float] = {}
        self._lock = threading.Lock()

    def pair(self, supplied: str) -> str | None:
        with self._lock:
            if (self.code is None or time.monotonic() > self.expires_at
                    or self.failures >= 5):
                return None
            if not isinstance(supplied, str) or not hmac.compare_digest(
                supplied, self.code
            ):
                self.failures += 1
                return None
            self.code = None
            token = secrets.token_urlsafe(32)
            self._tokens[hashlib.sha256(token.encode()).hexdigest()] = (
                time.monotonic() + 8 * 3600
            )
            return token

    def authorized(self, token: str) -> bool:
        if not isinstance(token, str) or len(token) > 256:
            return False
        identifier = hashlib.sha256(token.encode()).hexdigest()
        with self._lock:
            expiry = self._tokens.get(identifier)
            return expiry is not None and time.monotonic() < expiry

    def revoke_all(self) -> None:
        with self._lock:
            self._tokens.clear()
            self.code = None


def _tls_material(directory: Path) -> tuple[Path, Path, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Jervis Companion")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=2))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                           critical=False)
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path = directory / "companion.crt"
    key_path = directory / "companion.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    key_path.chmod(0o600)
    fingerprint = hashlib.sha256(
        cert.public_bytes(serialization.Encoding.DER)
    ).hexdigest()
    return cert_path, key_path, fingerprint


def _summary(paths: Paths) -> dict:
    from .evolve import health_summary
    from .version import __version__

    status = health_summary(paths)
    return {
        "version": __version__,
        "config_present": bool(status.get("config_present")),
        "database_present": bool(status.get("database_present")),
        "recovery_snapshots": int(status.get("recovery_snapshots", 0)),
        "invalid_snapshots": int(status.get("invalid_snapshots", 0)),
    }


class CompanionServer:
    def __init__(self, *, lan: bool = False, port: int = 0, paths: Paths | None = None):
        if not 0 <= port <= 65535:
            raise ValueError("Invalid port")
        self.paths = paths or Paths.resolve()
        self.registry = PairingRegistry()
        self.lan = bool(lan)
        self._temp = tempfile.TemporaryDirectory(prefix="jervis-companion-tls-")
        cert, key, self.fingerprint = _tls_material(Path(self._temp.name))
        self._cert_pem = cert.read_bytes()
        outer = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "JervisCompanion/8"
            sys_version = ""
            def log_message(self, _format, *_args):
                return

            def _send(self, code, data, mime="application/json"):
                raw = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Content-Type", mime)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                if self.path != "/pair":
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                if self.headers.get("Content-Type") != "application/json":
                    self._send(HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                               {"error": "JSON required"})
                    return
                count = self.headers.get("Content-Length", "")
                if not count.isdigit() or not 1 <= int(count) <= _MAX_BODY:
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid length"})
                    return
                try:
                    request = json.loads(self.rfile.read(int(count)))
                    code = request.get("code") if isinstance(request, dict) else ""
                except (ValueError, UnicodeError):
                    code = ""
                token = outer.registry.pair(code)
                if token is None:
                    self._send(HTTPStatus.FORBIDDEN, {"error": "pairing denied"})
                else:
                    self._send(HTTPStatus.OK, {"token": token,
                                               "expires_in_seconds": 28800,
                                               "scope": "status.read"})

            def do_GET(self):
                if self.path == "/certificate":
                    # Fingerprint must still be compared with the local CLI.
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/x-pem-file")
                    self.send_header("Content-Length", str(len(outer._cert_pem)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(outer._cert_pem)
                    return
                if self.path != "/api/status":
                    self._send(HTTPStatus.NOT_FOUND, {"error": "not found"})
                    return
                prefix = "Bearer "
                header = self.headers.get("Authorization", "")
                if not header.startswith(prefix) or not outer.registry.authorized(
                    header[len(prefix):]
                ):
                    self._send(HTTPStatus.UNAUTHORIZED, {"error": "pairing required"})
                    return
                self._send(HTTPStatus.OK, _summary(outer.paths))

        host = "0.0.0.0" if lan else "127.0.0.1"
        self.http = ThreadingHTTPServer((host, port), Handler)
        self.http.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        self.http.socket = context.wrap_socket(self.http.socket, server_side=True)

    @property
    def port(self) -> int:
        return self.http.server_port

    def serve(self) -> None:
        self.http.serve_forever(poll_interval=0.2)

    def close(self) -> None:
        self.registry.revoke_all()
        self.http.shutdown()
        self.http.server_close()
        self._temp.cleanup()
