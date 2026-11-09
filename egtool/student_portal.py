"""Loopback student web adapter. No OpenClaw RPC proxy, tools, or teacher routes.

The portal runs the same student Agent/Skill rules using stateless text completion.
Production requires a trusted HTTPS reverse proxy and an approved model provider.
Reports and sessions stay in memory, expire, and disappear on process restart.
"""
from __future__ import annotations
import argparse
from collections import deque
import csv
import hashlib
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .contracts import ContractError, loads, require, validate
from . import midterm

STATIC = Path(__file__).resolve().parents[1] / "web/student"
MAX_BODY = 180_000


class PortalError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def secret_hash(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def provision(out):
    out = Path(out).absolute()
    require(not out.resolve().is_relative_to(midterm.ROOT), "PRIVATE_ROSTER_OUTSIDE_REPO")
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    rows = [{"student_code": "S%03d" % i, "secret": secrets.token_urlsafe(32)} for i in range(1, 67)]
    for filename in ("roster.json", "individual-access.csv"):
        fd = os.open(out / filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            if filename.endswith("json"):
                json.dump({r["student_code"]: secret_hash(r["secret"]) for r in rows}, f)
            else:
                writer = csv.DictWriter(f, fieldnames=["student_code", "secret"])
                writer.writeheader(); writer.writerows(rows)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class TextModelBackend:
    name = "stateless-text-model"

    def __init__(self, endpoint, model, key):
        u = urlsplit(endpoint)
        require(u.scheme == "https" and u.hostname and not u.username and not u.password
                and not u.query and not u.fragment, "HTTPS_PROVIDER_ENDPOINT_REQUIRED")
        require(bool(model) and bool(key), "EXPLICIT_MODEL_CREDENTIALS_REQUIRED")
        self.endpoint, self.model, self.key = endpoint, model, key
        self.context = midterm.system_context()

    def generate(self, report, gate):
        body = {"model": self.model, "messages": [
            {"role": "system", "content": json.dumps(self.context, ensure_ascii=False)},
            {"role": "user", "content": json.dumps({"submission": report,
                "paragraphs": midterm.paragraphs(report), "validated_material_gate": gate}, ensure_ascii=False)}],
            "tools": [], "tool_choice": "none", "response_format": {"type": "json_object"}, "max_tokens": 5000}
        request = Request(self.endpoint, json.dumps(body).encode(),
                          {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}, method="POST")
        # Never follow a provider redirect with credentials, never retry uncertain calls.
        with build_opener(NoRedirect).open(request, timeout=180) as response:
            data = response.read(100_001)
        require(len(data) <= 100_000, "PROVIDER_OUTPUT_OVERSIZE")
        envelope = loads(data.decode())
        choices = envelope.get("choices", [])
        require(len(choices) == 1 and choices[0].get("finish_reason") == "stop", "PROVIDER_INCOMPLETE")
        message = choices[0]["message"]
        require(not message.get("tool_calls") and not message.get("function_call"), "PROVIDER_TOOLS_FORBIDDEN")
        return loads(message["content"])


class Portal:
    def __init__(self, roster, backend, origin, *, demo=False, cooldown=20, ttl=4*3600):
        u = urlsplit(origin)
        require(u.scheme in ("http", "https") and u.netloc and u.path == "" and not u.query
                and not u.fragment and not u.username, "EXACT_ORIGIN_REQUIRED")
        require((demo and u.scheme == "http" and u.hostname == "127.0.0.1") or
                (not demo and u.scheme == "https"), "HTTPS_REQUIRED_EXCEPT_LOOPBACK_DEMO")
        require(demo == isinstance(backend, midterm.DemoBackend), "DEMO_BACKEND_MISMATCH")
        require(set(roster) == {"S%03d" % i for i in range(1, 67)} and all(
            re.fullmatch(r"[a-f0-9]{64}", x) for x in roster.values()), "EXACT_66_ACCOUNT_ROSTER_REQUIRED")
        self.roster, self.backend, self.origin, self.demo = dict(roster), backend, origin, demo
        self.host, self.cooldown, self.ttl = u.netloc, cooldown, ttl
        self.cookie = "eg_demo_session" if demo else "__Host-eg_session"
        self.sessions, self.conversations, self.usage, self.last_call = {}, {}, {}, {}
        self.input_times = {code: deque() for code in roster}
        self.busy, self.login_times = set(), deque()
        self.lock, self.capacity = threading.RLock(), threading.BoundedSemaphore(4)

    def _prune(self, now):
        for key, s in list(self.sessions.items()):
            if now - s["created"] >= self.ttl:
                del self.sessions[key]
                self.conversations.pop(s["conversation_id"], None)

    def login(self, data):
        if set(data) != {"student_code", "secret", "consent"} or data.get("consent") is not True:
            raise PortalError(400, "LOGIN_FIELDS_OR_CONSENT")
        code, secret = data["student_code"], data["secret"]
        if not isinstance(code, str) or not isinstance(secret, str) or len(secret) > 100:
            raise PortalError(400, "LOGIN_FIELDS")
        now = time.monotonic()
        with self.lock:
            self._prune(now)
            while self.login_times and now - self.login_times[0] > 60:
                self.login_times.popleft()
            if len(self.login_times) >= 200:
                raise PortalError(429, "LOGIN_RATE_LIMIT")
            self.login_times.append(now)
            expected = self.roster.get(code, "0" * 64)
            if not secrets.compare_digest(secret_hash(secret), expected) or code not in self.roster:
                raise PortalError(401, "LOGIN_FAILED")
            # At most two browsers per account; never unbounded private histories.
            own = [(k, s) for k, s in self.sessions.items() if s["owner"] == code]
            if len(own) >= 2:
                k, s = min(own, key=lambda x: x[1]["created"])
                del self.sessions[k]; self.conversations.pop(s["conversation_id"], None)
            token, cid = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
            s = {"owner": code, "created": now, "conversation_id": cid}
            self.sessions[secret_hash(token)] = s
            self.conversations[cid] = {"owner": code, "latest": None, "epoch": 0}
            return token

    def authenticate(self, token):
        with self.lock:
            self._prune(time.monotonic())
            s = self.sessions.get(secret_hash(token))
            if not s:
                raise PortalError(401, "LOGIN_REQUIRED")
            return dict(s)

    def owned(self, session, cid):
        if not isinstance(cid, str):
            raise PortalError(404, "SESSION_NOT_FOUND")
        with self.lock:
            c = self.conversations.get(cid)
            # Ownership is checked on every read/write/delete, never inferred from a URL.
            if not c or c["owner"] != session["owner"]:
                raise PortalError(404, "SESSION_NOT_FOUND")
            return c

    def public_session(self, s):
        return {"student_code": s["owner"], "conversation_id": s["conversation_id"],
                "agent": "eg-student-feedback", "is_demo": self.demo,
                "storage_notice": "报告和反馈仅暂存在本服务内存，会话4小时到期；重启会清除。模型服务商的数据规则以教师告知为准。"}

    def clear(self, session, cid):
        with self.lock:
            conversation = self.owned(session, cid)
            conversation["latest"] = None
            conversation["epoch"] += 1

    def feedback(self, session, data):
        report = dict(data)
        cid = report.pop("conversation_id", None)
        with self.lock:
            epoch = self.owned(session, cid)["epoch"]
            times, now = self.input_times[session["owner"]], time.monotonic()
            while times and now - times[0] > 60: times.popleft()
            if len(times) >= 30: raise PortalError(429, "INPUT_RATE_LIMIT")
            times.append(now)
        gate = midterm.material_gate(report)
        owner, now = session["owner"], time.monotonic()
        with self.lock:
            if owner in self.busy or now - self.last_call.get(owner, -1e9) < self.cooldown:
                raise PortalError(429, "PLEASE_WAIT")
            if self.usage.get(owner, 0) >= 20:
                raise PortalError(429, "COURSE_CALL_LIMIT_CONTACT_TEACHER")
            if not self.capacity.acquire(blocking=False):
                raise PortalError(429, "SERVICE_BUSY")
            self.busy.add(owner); self.last_call[owner] = now
            self.usage[owner] = self.usage.get(owner, 0) + 1
        try:
            result = midterm.check_feedback(self.backend.generate(report, gate), report)
            output = {"agent": "eg-student-feedback", "is_demo": self.demo, "report_title": report["report_title"],
                      "material_check": gate, "feedback": result,
                      "notice": "AI形成性建议，未经教师专业复核，不代表成绩。"}
            with self.lock:
                conversation = self.owned(session, cid)
                if conversation["epoch"] != epoch:
                    raise PortalError(409, "FEEDBACK_CLEARED")
                conversation["latest"] = output
            return output
        finally:
            with self.lock:
                self.busy.discard(owner); self.capacity.release()


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128

    def service_actions(self):
        # Called by serve_forever even while idle; expiry does not depend on a later login.
        with self.portal.lock:
            self.portal._prune(time.monotonic())


def handler_for(portal):
    class Handler(BaseHTTPRequestHandler):
        server_version = "CoursePortal"

        def setup(self):
            super().setup(); self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # No URLs, cookies, report text, credentials, or identities in access logs.

        def send(self, code, value, content_type="application/json; charset=utf-8", cookie=None):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(code)
            for k, v in {"Content-Type": content_type, "Content-Length": str(len(body)),
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer", "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
                self.send_header(k, v)
            if not portal.demo:
                self.send_header("Strict-Transport-Security", "max-age=31536000")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers(); self.wfile.write(body)

        def session(self):
            try:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                token = cookie[portal.cookie].value
            except Exception:
                raise PortalError(401, "LOGIN_REQUIRED")
            return token, portal.authenticate(token)

        def cookie_value(self, token, logout=False):
            return "%s=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d%s" % (
                portal.cookie, token, 0 if logout else portal.ttl, "" if portal.demo else "; Secure")

        def dispatch(self):
            if self.headers.get("Host") != portal.host:
                raise PortalError(421, "HOST_REJECTED")
            path = self.path
            if self.command == "GET" and path in ("/", "/app.js", "/app.css"):
                name = {"/": "index.html", "/app.js": "app.js", "/app.css": "app.css"}[path]
                mime = {"/": "text/html", "/app.js": "text/javascript", "/app.css": "text/css"}[path]
                return self.send(200, (STATIC / name).read_bytes(), mime + "; charset=utf-8")
            if self.command in ("POST", "DELETE"):
                if self.headers.get("Origin") != portal.origin:
                    raise PortalError(403, "ORIGIN_REJECTED")
            if self.command == "POST":
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise PortalError(415, "JSON_REQUIRED")
                if self.headers.get("Transfer-Encoding"):
                    raise PortalError(400, "TRANSFER_ENCODING_REJECTED")
                length = self.headers.get("Content-Length", "")
                if not length.isdecimal() or not 0 < int(length) <= MAX_BODY:
                    raise PortalError(413, "BODY_SIZE")
                raw = self.rfile.read(int(length))
                if len(raw) != int(length):
                    raise PortalError(400, "INCOMPLETE_BODY")
                data = loads(raw.decode("utf-8"))
                if not isinstance(data, dict):
                    raise PortalError(400, "JSON_OBJECT_REQUIRED")
                if path == "/api/login":
                    token = portal.login(data)
                    return self.send(200, portal.public_session(portal.authenticate(token)), cookie=self.cookie_value(token))
                token, s = self.session()
                if path == "/api/logout":
                    if data:
                        raise PortalError(400, "NO_LOGOUT_FIELDS")
                    with portal.lock:
                        portal.sessions.pop(secret_hash(token), None)
                        portal.conversations.pop(s["conversation_id"], None)
                    return self.send(200, {"logged_out": True}, cookie=self.cookie_value("", True))
                if path == "/api/feedback":
                    return self.send(200, portal.feedback(s, data))
            if self.command in ("GET", "DELETE"):
                _, s = self.session()
                if self.command == "GET" and path == "/api/me":
                    return self.send(200, portal.public_session(s))
                if re.fullmatch(r"/api/sessions/[A-Za-z0-9_-]{32}", path):
                    cid = path.rsplit("/", 1)[1]
                    with portal.lock:
                        c = portal.owned(s, cid)
                        if self.command == "DELETE":
                            portal.clear(s, cid)
                            return self.send(200, {"cleared": True})
                        return self.send(200, {"latest": c["latest"]})
            raise PortalError(404, "ROUTE_NOT_FOUND")

        def run_safe(self):
            try:
                self.dispatch()
            except PortalError as e:
                self.send(e.status, {"error": e.code})
            except ContractError as e:
                safe = str(e) if str(e) in ("REMOVE_PERSONAL_INFORMATION", "COURSE_SCOPE_REQUIRED") else "INPUT_OR_OUTPUT_INVALID"
                self.send(422, {"error": safe})
            except Exception:
                self.send(502, {"error": "PROVIDER_OR_SERVICE_ERROR_NO_AUTOMATIC_RETRY"})
            finally:
                self.close_connection = True

        do_GET = do_POST = do_DELETE = do_PUT = do_PATCH = do_OPTIONS = run_safe
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("provision"); p.add_argument("--out", required=True)
    p = commands.add_parser("serve")
    p.add_argument("--roster", required=True); p.add_argument("--origin", required=True)
    p.add_argument("--port", type=int, default=18894); p.add_argument("--demo", action="store_true")
    p.add_argument("--provider-approved", action="store_true")
    args = parser.parse_args()
    if args.command == "provision":
        provision(args.out); print("66 private account credentials created; distribute individually."); return
    roster_path = Path(args.roster).resolve(strict=True)
    require(not roster_path.is_relative_to(midterm.ROOT) and not Path(args.roster).is_symlink(), "PRIVATE_ROSTER_REQUIRED")
    require(roster_path.stat().st_mode & 0o077 == 0, "PRIVATE_ROSTER_PERMISSIONS_REQUIRED")
    if args.demo:
        require(args.origin == "http://127.0.0.1:%d" % args.port, "LOOPBACK_DEMO_ONLY")
        backend = midterm.DemoBackend()
    else:
        require(args.provider_approved, "TEACHER_PROVIDER_DATA_POLICY_CONFIRMATION_REQUIRED")
        backend = TextModelBackend(os.environ.get("EG_MODEL_URL", ""), os.environ.get("EG_MODEL_ID", ""),
                                   os.environ.get("EG_MODEL_KEY", ""))
    portal = Portal(loads(roster_path.read_text()), backend, args.origin, demo=args.demo)
    server = PortalServer(("127.0.0.1", args.port), handler_for(portal))
    server.portal = portal
    print("Loopback adapter ready; %s. This is not proof of public availability." % backend.name, flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
