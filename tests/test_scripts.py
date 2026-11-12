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

    def test_location_in_markdown_link(self):
        report_text = """### [CG-002]: Link Test

**Location:** [src/routes/orders.js:13-20](src/routes/orders.js)

**Evidence:**
```js
order.save();
```
"""
        findings = verify_citations.parse_findings(report_text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["raw_location"], "src/routes/orders.js:13-20")

    def test_location_with_spaces_in_range(self):
        file_p, start, end = verify_citations.parse_location("src/server.js: 10 - 20 ")
        self.assertEqual(file_p, "src/server.js")
        self.assertEqual(start, 10)
        self.assertEqual(end, 20)

    def test_heading_level_two_and_four(self):
        report_text = """## [CG-001]: Level Two Finding

**Location:** `test.js:1`

**Evidence:**
```js
console.log("hi");
```

#### [CG-002]: Level Four Finding

**Location:** `test.js:2`

**Evidence:**
```js
console.log("bye");
```
"""
        findings = verify_citations.parse_findings(report_text)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["title"], "[CG-001]: Level Two Finding")
        self.assertEqual(findings[1]["title"], "[CG-002]: Level Four Finding")


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

    def test_circleci_and_bitbucket_detection(self):
        circle_dir = self.root / ".circleci"
        circle_dir.mkdir(parents=True)
        (circle_dir / "config.yml").write_text("version: 2.1\n", encoding="utf-8")
        (self.root / "bitbucket-pipelines.yml").write_text("pipelines:\n", encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertIn(".circleci/config.yml", data["ci_docker"])
        self.assertIn("bitbucket-pipelines.yml", data["ci_docker"])

    def test_pipfile_and_setup_manifest_detection(self):
        (self.root / "Pipfile").write_text("[packages]\ndjango = '*'\n", encoding="utf-8")
        (self.root / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertIn("Pipfile", data["manifests"])
        self.assertIn("setup.py", data["manifests"])
        self.assertIn("Django", data["frameworks"])

    def test_fastify_and_svelte_framework_detection(self):
        pkg = self.root / "package.json"
        pkg.write_text(json.dumps({
            "dependencies": {
                "@fastify/cors": "^8.0.0",
                "@sveltejs/kit": "^1.0.0"
            }
        }), encoding="utf-8")

        data = map_repo.analyze_repo(self.root)
        self.assertIn("Fastify", data["frameworks"])
        self.assertIn("Svelte", data["frameworks"])


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

    def test_single_file_scan_preserves_relative_path(self):
        sub = self.root / "src" / "controllers"
        sub.mkdir(parents=True)
        target = sub / "auth.js"
        target.write_text("const u = await User.findOne(req.body);\n", encoding="utf-8")
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.root)
            res = find_risk_patterns.run_scan("src/controllers/auth.js", find_risk_patterns.RULES)
            self.assertEqual(len(res["hits"]), 1)
            self.assertTrue(res["hits"][0]["location"].startswith("src/controllers/auth.js"))
        finally:
            os.chdir(orig_cwd)

    def test_real_token_containing_test_substring_not_dropped(self):
        test_file = self.root / "keys.py"
        test_file.write_text("token = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZtest123456'\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GEN-SEC-GITHUB-TOKEN", rule_ids)

    def test_empty_catch_block_comment_multi_line(self):
        test_file = self.root / "multi_swallow.js"
        test_file.write_text("try { run(); } catch (err) { /* ignore */\n}\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-BUG-EMPTY-CATCH", rule_ids)

    def test_client_secret_leak_with_suffixes(self):
        test_file = self.root / ".env"
        test_file.write_text("NEXT_PUBLIC_STRIPE_SECRET_KEY=sk_live_12345\nVITE_ADMIN_PASSWORD_HASH=secret123\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertEqual(rule_ids.count("JS-SEC-CLIENT-SECRET-LEAK"), 2)

    def test_unguarded_route_standard_function(self):
        test_file = self.root / "api.js"
        test_file.write_text("router.post('/submit', function(req, res) {});\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-UNGUARDED-ROUTE", rule_ids)

    def test_floating_promise_with_nested_call(self):
        test_file = self.root / "save.js"
        test_file.write_text("    order.save({ session: getSession() });\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-CONC-FLOATING-PROMISE", rule_ids)

    def test_logger_warn_secrets(self):
        test_file = self.root / "log.js"
        test_file.write_text("logger.warn('User password attempt failed:', pwd);\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JS-SEC-LOG-SECRETS", rule_ids)

    def test_python_debug_lowercase(self):
        test_file = self.root / "app.py"
        test_file.write_text("app.run(debug=True)\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("PY-SEC-DEBUG-TRUE", rule_ids)

    def test_python_subprocess_nested_parens(self):
        test_file = self.root / "runner.py"
        test_file.write_text("subprocess.run(get_cmd(), shell=True)\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("PY-SEC-SUBPROCESS-SHELL", rule_ids)

    def test_go_ignored_error_single_assignment(self):
        test_file = self.root / "main.go"
        test_file.write_text("    _ = json.Unmarshal(data, &v)\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GO-BUG-IGNORED-ERROR", rule_ids)

    def test_go_exec_command_context(self):
        test_file = self.root / "cmd.go"
        test_file.write_text("cmd := exec.CommandContext(ctx, req.URL.Path)\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("GO-SEC-EXEC-CMD", rule_ids)

    def test_java_sql_execute(self):
        test_file = self.root / "Dao.java"
        test_file.write_text("stmt.execute(\"DELETE FROM \" + table);\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_file, self.root, find_risk_patterns.RULES)
        rule_ids = [h["rule_id"] for h in hits]
        self.assertIn("JAVA-SEC-SQL-CONCAT", rule_ids)

    def test_generic_weak_hash_java_and_go(self):
        test_java = self.root / "Hash.java"
        test_java.write_text("MessageDigest md = MessageDigest.getInstance(\"MD5\");\n", encoding="utf-8")
        hits = find_risk_patterns.scan_file(test_java, self.root, find_risk_patterns.RULES)
        self.assertIn("GEN-SEC-WEAK-HASH", [h["rule_id"] for h in hits])

        test_go = self.root / "hash.go"
        test_go.write_text("h := md5.New()\n", encoding="utf-8")
        hits_go = find_risk_patterns.scan_file(test_go, self.root, find_risk_patterns.RULES)
        self.assertIn("GEN-SEC-WEAK-HASH", [h["rule_id"] for h in hits_go])


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

    def test_pipfile_triggers_python_checks(self):
        (self.root / "Pipfile").write_text("[packages]\n", encoding="utf-8")
        report = run_checks.execute_checks(self.root)
        linter_checks = [c for c in report["checks"] if "linter" in c["name"].lower() or "ruff" in c["name"].lower() or "flake8" in c["name"].lower()]
        self.assertTrue(len(linter_checks) > 0)


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
