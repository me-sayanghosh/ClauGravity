#!/usr/bin/env python3
"""test_scripts.py - Automated Unit & Regression Test Suite for ClauGravity Scripts"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import chunk_plan
import find_risk_patterns
import map_repo
import run_checks
import verify_citations


class TestVerifyCitations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_location_standard(self):
        file_p, start, end = verify_citations.parse_location("src/server.js:10-20")
        self.assertEqual(file_p, "src/server.js")
        self.assertEqual(start, 10)
        self.assertEqual(end, 20)

    def test_parse_location_single_line(self):
        file_p, start, end = verify_citations.parse_location("src/server.js:15")
        self.assertEqual(file_p, "src/server.js")
        self.assertEqual(start, 15)
        self.assertEqual(end, 15)

    def test_parse_location_with_l_prefix(self):
        file_p, start, end = verify_citations.parse_location("src/server.js:L10-L20")
        self.assertEqual(file_p, "src/server.js")
        self.assertEqual(start, 10)
        self.assertEqual(end, 20)

    def test_parse_location_windows_path(self):
        file_p, start, end = verify_citations.parse_location(r"C:\project\src\server.js:10-20")
        self.assertEqual(file_p, "C:/project/src/server.js")
        self.assertEqual(start, 10)
        self.assertEqual(end, 20)

    def test_parse_location_windows_path_no_line(self):
        file_p, start, end = verify_citations.parse_location(r"C:\project\src\server.js")
        self.assertEqual(file_p, "C:/project/src/server.js")
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_exact_citation_match(self):
        target_file = self.root / "example.js"
        target_file.write_text("line 1\nconst x = 42;\nline 3\n", encoding="utf-8")

        finding = {
            "title": "Test Finding",
            "raw_location": "example.js:2",
            "evidence": "const x = 42;"
        }
        ok, reason = verify_citations.verify_single_citation(finding, self.root)
        self.assertTrue(ok)
        self.assertIn("Verified exact match", reason)

    def test_tolerance_citation_match(self):
        # Line is at line 4, but cited as line 2 (offset by 2 lines)
        target_file = self.root / "example.js"
        target_file.write_text("header 1\nheader 2\nheader 3\nconst secret = 'xyz';\nfooter\n", encoding="utf-8")

        finding = {
            "title": "Offset Finding",
            "raw_location": "example.js:2",
            "evidence": "const secret = 'xyz';"
        }
        ok, reason = verify_citations.verify_single_citation(finding, self.root, tolerance=3)
        self.assertTrue(ok)

    def test_trailing_space_on_code_fence(self):
        report_text = """### [CG-001]: Test Issue

**Location:** `test.js:1-2`

**Evidence:**
```js 
const a = 1;
const b = 2;
```
"""
        findings = verify_citations.parse_findings(report_text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["raw_location"], "test.js:1-2")
        self.assertIn("const a = 1;", findings[0]["evidence"])


class TestMapRepo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ci_docker_detection(self):
        wf_dir = self.root / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "ci.yml").write_text("name: CI\n", encoding="utf-8")
        (self.root / "Dockerfile").write_text("FROM alpine\n", encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertIn(".github/workflows/ci.yml", data["ci_docker"])
        self.assertIn("Dockerfile", data["ci_docker"])

    def test_framework_detection_nestjs_and_angular(self):
        pkg = self.root / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {
                "@nestjs/core": "^10.0.0",
                "@angular/core": "^17.0.0"
            }
        }), encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertIn("Nestjs", data["frameworks"])
        self.assertIn("Angular", data["frameworks"])

    def test_route_detection_backticks(self):
        route_file = self.root / "routes.js"
        route_file.write_text("router.get(`/api/items`, (req, res) => {});\n", encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(data["routes"][0]["path"], "/api/items")
        self.assertEqual(data["routes"][0]["method"], "GET")


class TestFindRiskPatterns(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sql_lowercase_regex(self):
        test_file = self.root / "query.js"
        test_file.write_text("const res = await db.query(\"select * from users where id = \" + id);\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-SQL", rule_ids)

    def test_nosql_spread_injection(self):
        test_file = self.root / "auth.js"
        test_file.write_text("const user = await User.find({ ...req.body });\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-NOSQL", rule_ids)

    def test_floating_promise_without_semicolon(self):
        test_file = self.root / "order.js"
        test_file.write_text("    order.save()\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-CONC-FLOATING-PROMISE", rule_ids)

    def test_jwt_fallback_secret_with_spaces(self):
        test_file = self.root / "jwt.js"
        test_file.write_text("const s = process.env.JWT_SECRET || \"my fallback secret key\";\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-JWT-FLAW", rule_ids)

    def test_empty_catch_single_line_with_block_comment(self):
        test_file = self.root / "swallow.js"
        test_file.write_text("try { doWork(); } catch (err) { /* ignore */ }\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-BUG-EMPTY-CATCH", rule_ids)

    def test_math_random_camelcase_token(self):
        test_file = self.root / "token.js"
        test_file.write_text("const csrfToken = Math.random().toString(36);\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-MATH-RANDOM-TOKEN", rule_ids)

    def test_unguarded_patch_route(self):
        test_file = self.root / "patch_route.js"
        test_file.write_text("router.patch('/users/:id', async (req, res) => {});\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-UNGUARDED-ROUTE", rule_ids)

    def test_python_pickle_load(self):
        test_file = self.root / "deser.py"
        test_file.write_text("obj = pickle.load(file_handle)\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("PY-SEC-PICKLE", rule_ids)

    def test_go_query_context(self):
        test_file = self.root / "db.go"
        test_file.write_text("rows, err := db.QueryContext(ctx, fmt.Sprintf(\"SELECT * FROM %s\", table))\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GO-SEC-SQL-FORMAT", rule_ids)

    def test_password_in_json_or_object(self):
        test_file = self.root / "creds.js"
        test_file.write_text("const config = { password: \"supersecret123\" };\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GEN-SEC-HARDCODED-PASSWORD", rule_ids)
        self.assertIn("supe****", hits[0]["line_snippet"])


class TestRunChecks(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_missing_lockfile_skips_npm_audit(self):
        (self.root / "package.json").write_text(json.dumps({
            "name": "test-pkg",
            "scripts": {}
        }), encoding="utf-8")
        report = run_checks.execute_checks(self.root)
        audit_checks = [c for c in report["checks"] if "audit" in c["name"]]
        self.assertTrue(len(audit_checks) > 0)
        self.assertEqual(audit_checks[0]["status"], "skipped: no lockfile")
        self.assertEqual(report["failed"], 0)


class TestChunkPlan(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chunk_generation_and_ranking(self):
        routes_dir = self.root / "src" / "routes"
        routes_dir.mkdir(parents=True)
        (routes_dir / "auth.js").write_text("// auth login session\n" * 20, encoding="utf-8")
        (routes_dir / "orders.js").write_text("// orders checkout\n" * 15, encoding="utf-8")

        docs_dir = self.root / "docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "readme.txt").write_text("documentation\n", encoding="utf-8")

        plan = chunk_plan.generate_chunks(self.root, max_chunks=5)
        self.assertTrue(plan["total_chunks"] >= 1)
        self.assertEqual(plan["chunks"][0]["name"], "src/routes")


if __name__ == "__main__":
    unittest.main()
