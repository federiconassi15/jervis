"""Authenticated, read-only, loopback-only Jervis Control Center for 8.1.

Never binds to LAN interfaces. No JS bundles, remote assets or privileged API
routes. Startup is explicit from the CLI; authentication is per server process.
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .paths import Paths

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>Jervis • Control Center</title>
<style>
:root{color-scheme:dark;--bg:#0c0f12;--panel:#141b21;--muted:#8a9aa7;--line:#283640;--accent:#83e2bd}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 10% -5%,#203c34 0%,var(--bg) 60%);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;color:#e8f0f1}
main{max-width:1030px;margin:auto;padding:32px 20px 60px}
header{display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap;margin-bottom:40px}
.logo{font-size:24px;font-weight:800;letter-spacing:.09em}.logo span{color:var(--accent)}
.small{color:var(--muted);font-size:13px}h1{font-size:clamp(30px,5vw,48px);line-height:1.1;margin:0 0 10px}p{color:var(--muted)}
.pill{padding:8px 13px;border:1px solid #355748;border-radius:100px;background:#163527;color:var(--accent);font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(225px,1fr));gap:14px;margin-top:28px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;min-height:122px}
.label{font-size:13px;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
.value{font-size:30px;font-weight:750;margin-top:13px;overflow-wrap:anywhere}
.detail{font-size:13px;color:var(--muted);margin-top:7px}
section{margin:32px 0}code{background:#203038;padding:2px 6px;border-radius:5px}
footer{color:var(--muted);border-top:1px solid var(--line);padding-top:20px;font-size:13px}
</style></head><body><main>
<header><div class="logo">JERVIS<span> / CONTROL</span></div>
<div class="pill" id="network">● Local only</div></header>
<h1>System overview.</h1><p>Read-only health information for this machine. Nothing is shared over the internet.</p>
<div class="tiles">
<div class="card"><div class="label">Installed Jervis</div><div class="value" id="version">Checking…</div></div>
<div class="card"><div class="label">Configuration</div><div class="value" id="config">Checking…</div></div>
<div class="card"><div class="label">Database</div><div class="value" id="database">Checking…</div></div>
<div class="card"><div class="label">Verified snapshots</div><div class="value" id="snapshots">Checking…</div><div class="detail" id="invalid"></div></div>
<div class="card"><div class="label">Plugin manifests</div><div class="value" id="plugins">Checking…</div><div class="detail">Discovered only; no code executed</div></div>
<div class="card"><div class="label">Last voice response</div><div class="value" id="latency">—</div><div class="detail">Benchmark median, if recorded</div></div>
</div>
<section><h2>Operational events</h2>
<p>Private, sanitized runtime events. No transcripts, credentials or device identifiers.</p>
<pre id="events" style="white-space:pre-wrap;overflow-wrap:anywhere;color:#b7e6d7">No events yet.</pre>
</section>
<section><h2>Quick commands</h2>
<p>Run <code>jervis doctor</code> for deeper diagnostics, <code>jervis health</code>
for local checks, or <code>jervis repair-center</code> for recovery options.
This dashboard never performs repairs without the operator.</p></section>
<footer>Private loopback dashboard · Temporary session · No remote access ·
Auto-updates while open</footer></main>
<script>
async function refresh(){
try{
const response=await fetch('/api/overview',{credentials:'same-origin',cache:'no-store'});
if(!response.ok)throw Error('Not authorized');
const data=await response.json();
const logResponse=await fetch('/api/logs',{credentials:'same-origin',cache:'no-store'});
if(logResponse.ok){
  const events=await logResponse.json();
  document.getElementById('events').textContent=events.length
    ? events.map(e=>e.time+' ['+e.level+'] '+e.message).join('\n')
    : 'No events yet.';
}
for(const [id,value] of Object.entries({
version:data.version,config:data.config_present?'Present':'Missing',
database:data.database_present?'Present':'Missing',
snapshots:String(data.recovery_snapshots),plugins:String(data.plugins_discovered),
latency:data.latency_ms===null?'—':Math.round(data.latency_ms)+' ms',
invalid:data.invalid_snapshots?'Attention: '+data.invalid_snapshots+' invalid archive(s)':'No invalid archives'
}))document.getElementById(id).textContent=value;
document.getElementById('network').textContent='● Local connection';
}catch(error){document.getElementById('network').textContent='! Connection unavailable';}
}
refresh();setInterval(refresh,15000);
</script></body></html>
"""


def _overview(paths: Paths) -> dict:
    from .evolve import health_summary
    from .status import _latest_benchmark
    from .version import __version__

    health = health_summary(paths)
    stats = (_latest_benchmark(paths) or {}).get("live", {})
    command = stats.get("command_to_reply_ms", {}) if isinstance(stats, dict) else {}
    median = command.get("median") if isinstance(command, dict) else None
    if not isinstance(median, (int, float)) or median < 0 or median > 1e8:
        median = None
    return {"version": __version__, **health, "latency_ms": median}


class ControlCenter:
    """Run a local HTTP dashboard with a one-process capability token."""

    def __init__(self, paths: Paths | None = None, port: int = 0):
        self.paths = paths or Paths.resolve()
        if not 0 <= int(port) <= 65535:
            raise ValueError("port must be 0..65535")
        self._secret = secrets.token_urlsafe(32)
        self._cache_lock = threading.Lock()
        self._cache_until = 0.0
        self._cache = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "JervisControlCenter/8"
            sys_version = ""

            def log_message(self, _format, *_args):
                # Never log paths or session tokens.
                return

            def _headers(self, status, content_type, length, extra=None):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Content-Security-Policy",
                                 "default-src 'none'; script-src 'unsafe-inline'; "
                                 "style-src 'unsafe-inline'; connect-src 'self'; "
                                 "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                for key, value in (extra or {}).items():
                    self.send_header(key, value)
                self.end_headers()

            def _send(self, status, content, mime="text/plain; charset=utf-8", extra=None):
                raw = content.encode("utf-8")
                self._headers(status, mime, len(raw), extra)
                self.wfile.write(raw)

            def _valid_host(self):
                hostname = self.headers.get("Host", "")
                actual = f"127.0.0.1:{outer.port}"
                origin = self.headers.get("Origin")
                return hostname == actual and (not origin or origin == "http://" + actual)

            def _authorized(self):
                cookies = self.headers.get("Cookie", "").split(";")
                for cookie in cookies:
                    key, sep, value = cookie.strip().partition("=")
                    if sep and key == "jervis_session":
                        return hmac.compare_digest(value, outer._secret)
                return False

            def do_GET(self):
                if not self._valid_host():
                    self._send(HTTPStatus.FORBIDDEN, "Invalid local origin")
                    return
                path = urlsplit(self.path).path
                if path == "/unlock/" + outer._secret:
                    self._headers(HTTPStatus.FOUND, "text/plain", 0, {
                        "Location": "/",
                        "Set-Cookie": "jervis_session=" + outer._secret
                        + "; HttpOnly; SameSite=Strict; Path=/",
                    })
                    return
                if not self._authorized():
                    self._send(HTTPStatus.UNAUTHORIZED, "Start from the private Jervis URL.")
                    return
                if path == "/":
                    self._send(HTTPStatus.OK, PAGE, "text/html; charset=utf-8")
                elif path == "/api/logs":
                    # Private localhost session only; source catalog prevents
                    # arbitrary transcripts or provider output reaching the UI.
                    from .observability import read_events

                    self._send(HTTPStatus.OK,
                               json.dumps(read_events(outer.paths.logs, limit=50)),
                               "application/json; charset=utf-8")
                elif path == "/api/overview":
                    now = time.monotonic()
                    with outer._cache_lock:
                        if now >= outer._cache_until:
                            outer._cache = _overview(outer.paths)
                            outer._cache_until = now + 15
                        payload = dict(outer._cache)
                    self._send(HTTPStatus.OK, json.dumps(payload),
                               "application/json; charset=utf-8")
                else:
                    self._send(HTTPStatus.NOT_FOUND, "Not found")

        self.http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.http.daemon_threads = True

    @property
    def port(self) -> int:
        return self.http.server_port

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/unlock/{self._secret}"

    def serve(self) -> None:
        self.http.serve_forever(poll_interval=0.2)

    def close(self) -> None:
        self.http.shutdown()
        self.http.server_close()
