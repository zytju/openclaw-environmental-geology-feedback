import copy
import http.client
import json
import secrets
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from egtool import midterm
from egtool.contracts import ContractError, DIMENSIONS
from egtool.student_portal import (Portal, PortalServer, PortalError, TextModelBackend,
                                   NoRedirect, handler_for, secret_hash)


def report(marker="同一报告"):
    return {"report_title": "三峡库区滑坡与灾害链分析", "report_text":
            "树坪滑坡的变形应结合库水位下降、降雨和地下水响应讨论。" + marker}


class MaterialTests(unittest.TestCase):
    def test_all_four_optional_combinations_keep_full_feedback(self):
        for a in ("", "我的原始机制分析草图说明"):
            for c in ("", "论文来源及位置、证据摘录和自己的解释"):
                r = dict(report(), raw_analysis=a, evidence_cards=c)
                g = midterm.material_gate(r)
                self.assertEqual(g["status"], "eligible")
                self.assertEqual(g["assessed_dimensions"], DIMENSIONS)
                self.assertEqual(len(g["optional_missing"]), (not a) + (not c))
                self.assertEqual(len(midterm.check_feedback(midterm.DemoBackend().generate(r, g), r)["dimensions"]), 6)

    def test_no_references_short_report_or_revision_records_still_eligible(self):
        g = midterm.material_gate(report())
        self.assertEqual(g["status"], "eligible")
        self.assertGreaterEqual(len(g["warnings"]), 4)
        self.assertFalse(g["sources_verified"])
        self.assertFalse(g["authorship_proven"])

    def test_unknown_references_not_claimed_verified(self):
        g = midterm.material_gate(dict(report(), references="未经核验的自选研究论文"))
        self.assertFalse(g["sources_verified"])

    def test_identity_is_not_sent_to_backend(self):
        with self.assertRaisesRegex(ContractError, "REMOVE_PERSONAL_INFORMATION"):
            midterm.material_gate(report("姓名：测试学生"))

    def test_unrelated_topic_and_empty_report(self):
        for r in ({"report_title": "一般生活问题", "report_text": "请回答其他领域的问题"},
                  {"report_title": "新丰江库区滑坡", "report_text": "分析当地滑坡及灾害链"},
                  {"report_title": "三峡滑坡", "report_text": ""}):
            with self.assertRaises(ContractError):
                midterm.material_gate(r)

    def test_student_cannot_supply_server_policy_identity_or_controls(self):
        for key in ("policy", "student_id", "agent", "tools", "config", "session_id", "approved_for_feedback"):
            with self.assertRaises(ContractError):
                midterm.material_gate(dict(report(), **{key: "attacker"}))

    def test_reject_incomplete_duplicate_dimensions_and_forged_quotes(self):
        r = report(); v = midterm.DemoBackend().generate(r, midterm.material_gate(r))
        for kind in ("missing", "duplicate", "quote", "teacher_field"):
            out = copy.deepcopy(v)
            if kind == "missing": out["dimensions"].pop()
            if kind == "duplicate": out["dimensions"][1] = out["dimensions"][0]
            if kind == "quote": out["dimensions"][0]["quote"] = "报告中不存在的句子"
            if kind == "teacher_field": out["teacher_approved"] = True
            with self.assertRaises(ContractError):
                midterm.check_feedback(out, r)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secrets = {"S%03d" % i: secrets.token_urlsafe(32) for i in range(1, 67)}
        cls.roster = {k: secret_hash(v) for k, v in cls.secrets.items()}
        cls.server = PortalServer(("127.0.0.1", 0), http.client.HTTPConnection)  # handler replaced below
        cls.port = cls.server.server_address[1]; cls.origin = "http://127.0.0.1:%d" % cls.port
        cls.portal = Portal(cls.roster, midterm.DemoBackend(), cls.origin, demo=True, cooldown=0)
        cls.server.portal = cls.portal
        cls.server.RequestHandlerClass = handler_for(cls.portal)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def call(self, path, method="GET", data=None, cookie=None, origin=None, raw=None, host=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Origin": origin or self.origin, "Host": host or "127.0.0.1:%d" % self.port}
        if cookie: headers["Cookie"] = cookie
        body = raw if raw is not None else json.dumps(data) if data is not None else None
        if body is not None: headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse(); content = response.read(); status = response.status; hs = dict(response.getheaders())
        connection.close()
        return status, json.loads(content) if "application/json" in hs.get("Content-Type", "") else content, hs

    def login(self, code):
        status, data, headers = self.call("/api/login", "POST", {"student_code": code, "secret": self.secrets[code], "consent": True})
        self.assertEqual(status, 200)
        return data, headers["Set-Cookie"].split(";", 1)[0]

    def test_66_distinct_sessions_and_every_cross_owner_pair(self):
        sessions = []
        for i in range(1, 67):
            code = "S%03d" % i; s, cookie = self.login(code)
            marker = "唯一合成标记%03d" % i
            status, value, _ = self.call("/api/feedback", "POST", dict(report(marker), conversation_id=s["conversation_id"]), cookie)
            self.assertEqual(status, 200)
            self.assertEqual(len(value["feedback"]["dimensions"]), 6)
            self.assertTrue(value["is_demo"])
            self.assertIn(marker, value["feedback"]["dimensions"][0]["quote"])
            sessions.append((s, cookie))
        self.assertEqual(len({s["conversation_id"] for s, _ in sessions}), 66)
        # All 4290 cross-owner pairs at the service authorization boundary.
        for a, _ in sessions:
            for b, _ in sessions:
                if a["student_code"] == b["student_code"]: continue
                with self.assertRaises(PortalError) as caught:
                    self.portal.owned({"owner": a["student_code"]}, b["conversation_id"])
                self.assertEqual(caught.exception.status, 404)
        # Exercise actual HTTP read/write/delete denial, then verify victim data survives.
        a, ac = sessions[0]; b, bc = sessions[1]
        for method in ("GET", "DELETE"):
            self.assertEqual(self.call("/api/sessions/" + b["conversation_id"], method, cookie=ac)[0], 404)
        self.assertEqual(self.call("/api/feedback", "POST", dict(report(), conversation_id=b["conversation_id"]), ac)[0], 404)
        status, value, _ = self.call("/api/sessions/" + b["conversation_id"], cookie=bc)
        self.assertEqual(status, 200); self.assertIn("唯一合成标记002", str(value))

    def test_unauthenticated_and_teacher_management_file_routes_denied(self):
        self.assertEqual(self.call("/api/me")[0], 401)
        _, cookie = self.login("S003")
        for path in ("/api/agents/eg-teacher-review", "/api/config", "/api/tools/exec", "/api/files/read",
                     "/api/sessions", "/v1/chat/completions", "/gateway", "/../.openclaw/openclaw.json"):
            self.assertEqual(self.call(path, cookie=cookie)[0], 404)

    def test_server_control_fields_rejected_over_http(self):
        s, cookie = self.login("S004")
        for key in ("agent", "tools", "config", "teacher_approved", "role_rules", "validated_material_gate"):
            data = dict(report(), conversation_id=s["conversation_id"], **{key: "unauthorized"})
            self.assertEqual(self.call("/api/feedback", "POST", data, cookie)[0], 422)

    def test_origin_host_cookies_and_json_boundaries(self):
        status, _, h = self.call("/api/login", "POST", {"student_code": "S005", "secret": self.secrets["S005"], "consent": True})
        self.assertEqual(status, 200); self.assertIn("HttpOnly", h["Set-Cookie"]); self.assertIn("SameSite=Strict", h["Set-Cookie"])
        self.assertEqual(h["Cache-Control"], "no-store")
        self.assertEqual(self.call("/api/login", "POST", {}, origin="https://evil.example")[0], 403)
        self.assertEqual(self.call("/", host="evil.example")[0], 421)
        self.assertEqual(self.call("/api/login", "POST", raw='{"secret":"a","secret":"b"}')[0], 422)
        self.assertEqual(self.call("/api/login", "POST", raw='{"x":"' + "a"*180000 + '"}')[0], 413)

    def test_logout_deletes_feedback_and_invalidates_cookie(self):
        s, cookie = self.login("S006")
        self.assertEqual(self.call("/api/feedback", "POST", dict(report(), conversation_id=s["conversation_id"]), cookie)[0], 200)
        self.assertEqual(self.call("/api/logout", "POST", {}, cookie)[0], 200)
        self.assertEqual(self.call("/api/me", cookie=cookie)[0], 401)
        self.assertNotIn(s["conversation_id"], self.portal.conversations)

    def test_html_script_in_report_is_data(self):
        s, cookie = self.login("S007")
        r = report("<script>fetch('/api/config')</script>")
        self.assertEqual(self.call("/api/feedback", "POST", dict(r, conversation_id=s["conversation_id"]), cookie)[0], 200)
        status, js, _ = self.call("/app.js")
        self.assertEqual(status, 200); self.assertNotIn(b"innerHTML", js)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.roster = {"S%03d" % i: secret_hash("a" * 43 + str(i)) for i in range(1, 67)}

    def test_no_insecure_production_or_accidental_demo(self):
        with self.assertRaises(ContractError): Portal(self.roster, object(), "http://127.0.0.1:12345")
        with self.assertRaises(ContractError): Portal(self.roster, midterm.DemoBackend(), "https://course.example")
        with self.assertRaises(ContractError): Portal(self.roster, midterm.DemoBackend(), "http://0.0.0.0:12345", demo=True)
        with self.assertRaises(ContractError): TextModelBackend("http://example/v1", "model", "secret")

    def test_expiry_and_bounded_private_sessions(self):
        p = Portal(self.roster, midterm.DemoBackend(), "http://127.0.0.1:12345", demo=True, ttl=1)
        tokens = [p.login({"student_code": "S001", "secret": "a"*43+"1", "consent": True}) for _ in range(3)]
        self.assertEqual(len(p.sessions), 2); self.assertEqual(len(p.conversations), 2)
        with self.assertRaises(PortalError): p.authenticate(tokens[0])
        p._prune(time.monotonic()+2)
        self.assertFalse(p.sessions); self.assertFalse(p.conversations)

    def test_expiry_purge_runs_without_student_request(self):
        p = Portal(self.roster, midterm.DemoBackend(), "http://127.0.0.1:12345", demo=True, ttl=1)
        s = p.authenticate(p.login({"student_code":"S001","secret":"a"*43+"1","consent":True}))
        for session in p.sessions.values(): session["created"] -= 2
        server = object.__new__(PortalServer); server.portal = p
        server.service_actions()
        self.assertNotIn(s["conversation_id"], p.conversations); self.assertFalse(p.sessions)

    def test_parallel_call_capacity_and_per_owner_exclusion(self):
        entered = threading.Barrier(5); release = threading.Event()
        class BlockBackend:
            def generate(self, r, g):
                entered.wait(timeout=5); release.wait(timeout=5)
                return midterm.DemoBackend().generate(r, g)
        p = Portal(self.roster, BlockBackend(), "https://course.example", cooldown=0)
        sessions = [p.authenticate(p.login({"student_code": "S%03d" % i, "secret": "a"*43+str(i), "consent": True})) for i in range(1, 6)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(p.feedback, s, dict(report(), conversation_id=s["conversation_id"])) for s in sessions[:4]]
            entered.wait(timeout=5)
            for s in (sessions[0], sessions[4]):
                with self.assertRaises(PortalError) as exc:
                    p.feedback(s, dict(report(), conversation_id=s["conversation_id"]))
                self.assertEqual(exc.exception.status, 429)
            release.set()
            self.assertTrue(all(len(f.result()["feedback"]["dimensions"]) == 6 for f in futures))

    def test_quota_cooldown_and_invalid_login(self):
        p = Portal(self.roster, midterm.DemoBackend(), "http://127.0.0.1:12345", demo=True)
        with self.assertRaises(PortalError): p.login({"student_code":"S001","secret":"wrong","consent":True})
        with self.assertRaises(PortalError): p.login({"student_code":"S001","secret":"a"*43+"1","consent":False})
        s = p.authenticate(p.login({"student_code":"S001","secret":"a"*43+"1","consent":True}))
        data = dict(report(), conversation_id=s["conversation_id"])
        p.feedback(s, data)
        with self.assertRaises(PortalError): p.feedback(s, data)
        p.last_call.clear(); p.usage["S001"] = 20
        with self.assertRaises(PortalError): p.feedback(s, data)

    def test_clear_during_generation_cannot_restore_or_return_feedback(self):
        entered, release = threading.Event(), threading.Event()
        class SlowBackend:
            def generate(self, r, g):
                entered.set(); release.wait(timeout=5)
                return midterm.DemoBackend().generate(r, g)
        p = Portal(self.roster, SlowBackend(), "https://course.example", cooldown=0)
        s = p.authenticate(p.login({"student_code":"S001","secret":"a"*43+"1","consent":True}))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(p.feedback, s, dict(report(), conversation_id=s["conversation_id"]))
            self.assertTrue(entered.wait(timeout=5)); p.clear(s, s["conversation_id"]); release.set()
            with self.assertRaises(PortalError) as error: future.result()
            self.assertEqual(error.exception.code, "FEEDBACK_CLEARED")
        self.assertIsNone(p.owned(s, s["conversation_id"])["latest"])

    def test_text_backend_no_history_no_tools_and_rejects_function_calls(self):
        backend = TextModelBackend("https://model.example/v1/chat/completions", "teacher-model", "private-test-key")
        r = report(); valid = midterm.DemoBackend().generate(r, midterm.material_gate(r))
        sent = []
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps(valid)}}]}).encode()
        class Opener:
            def open(self, request, timeout): sent.append(json.loads(request.data)); return Response()
        with patch("egtool.student_portal.build_opener", return_value=Opener()):
            self.assertEqual(backend.generate(r, midterm.material_gate(r)), valid)
        self.assertEqual(len(sent), 1); self.assertEqual(sent[0]["tools"], []); self.assertEqual(sent[0]["tool_choice"], "none")
        self.assertEqual([m["role"] for m in sent[0]["messages"]], ["system", "user"])
        self.assertNotIn("S001", sent[0]["messages"][1]["content"])

    def test_provider_function_calls_and_truncated_output_rejected_without_retry(self):
        backend = TextModelBackend("https://model.example/v1/chat/completions", "teacher-model", "private-test-key")
        for message, reason in (({"content":"{}", "tool_calls":[{"name":"exec"}]}, "stop"),
                                ({"content":"{}", "function_call":{"name":"read"}}, "stop"),
                                ({"content":"{}"}, "length")):
            calls = []
            class Response:
                def __enter__(self): return self
                def __exit__(self,*a): pass
                def read(self, n): return json.dumps({"choices":[{"finish_reason":reason,"message":message}]}).encode()
            class Opener:
                def open(self, request, timeout): calls.append(request); return Response()
            with patch("egtool.student_portal.build_opener", return_value=Opener()):
                with self.assertRaises(ContractError): backend.generate(report(), midterm.material_gate(report()))
            self.assertEqual(len(calls), 1)
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example"))


if __name__ == "__main__": unittest.main()
