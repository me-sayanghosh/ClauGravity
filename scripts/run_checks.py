#!/usr/bin/env python3
"""run_checks.py - ClauGravity Safe Tooling & Check Runner

Detects and safely executes available local linters, type-checkers, and security
advisories without installing packages or executing unsafe commands.

Usage:
    python scripts/run_checks.py [path] [--timeout S] [--allow-tests] [--json]

Examples:
    python scripts/run_checks.py .
    python scripts/run_checks.py tests/fixture-project --allow-tests --json
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def is_tool_available(name):
    return shutil.which(name) is not None

def run_cmd(cmd, cwd, timeout=30):
    try:
        exec_cmd = list(cmd)
        if sys.platform == "win32":
            resolved = shutil.which(exec_cmd[0])
            if resolved:
                exec_cmd[0] = resolved
            if exec_cmd[0].lower().endswith((".cmd", ".bat")):
                exec_cmd = ["cmd.exe", "/c"] + exec_cmd
        proc = subprocess.run(
            exec_cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return {
            "status": "passed" if proc.returncode == 0 else "failed",
            "exit_code": proc.returncode,
            "output": output[:2000] if len(output) > 2000 else output
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timed_out",
            "exit_code": -1,
            "output": f"Command timed out after {timeout} seconds."
        }
    except Exception as e:
        return {
            "status": "error",
            "exit_code": -1,
            "output": str(e)
        }

def execute_checks(target_path, timeout=30, allow_tests=False):
    root = Path(target_path).resolve()
    if not root.is_dir():
        sys.exit(f"Error: Target path {root} is not a directory.")

    results = []

    # 1. Node.js / JavaScript Checks
    pkg_json = root / "package.json"
    tsconfig = root / "tsconfig.json"

    if pkg_json.is_file():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                pkg_data = json.load(f)
            scripts = pkg_data.get("scripts", {})

            if "lint" in scripts and is_tool_available("npm"):
                res = run_cmd(["npm", "run", "lint", "--silent"], cwd=root, timeout=timeout)
                results.append({"name": "npm run lint", "tool": "npm", "category": "Linter", **res})

            if "typecheck" in scripts and is_tool_available("npm"):
                res = run_cmd(["npm", "run", "typecheck", "--silent"], cwd=root, timeout=timeout)
                results.append({"name": "npm run typecheck", "tool": "npm", "category": "Typechecker", **res})

            if "test" in scripts:
                if allow_tests and is_tool_available("npm"):
                    res = run_cmd(["npm", "test", "--silent"], cwd=root, timeout=timeout)
                    results.append({"name": "npm test", "tool": "npm", "category": "Tests", **res})
                else:
                    results.append({"name": "npm test", "tool": "npm", "category": "Tests", "status": "available, not run", "exit_code": 0, "output": "Tests available; rerun with --allow-tests to execute."})
        except Exception:
            pass

        if "lint" not in scripts and is_tool_available("eslint"):
            res = run_cmd(["eslint", "."], cwd=root, timeout=timeout)
            results.append({"name": "eslint", "tool": "eslint", "category": "Linter", **res})

        # Production audit
        if (root / "yarn.lock").is_file() and is_tool_available("yarn"):
            res = run_cmd(["yarn", "audit", "--groups", "dependencies"], cwd=root, timeout=timeout)
            results.append({"name": "yarn audit (prod)", "tool": "yarn", "category": "Security", **res})
        elif (root / "pnpm-lock.yaml").is_file() and is_tool_available("pnpm"):
            res = run_cmd(["pnpm", "audit", "--prod"], cwd=root, timeout=timeout)
            results.append({"name": "pnpm audit (prod)", "tool": "pnpm", "category": "Security", **res})
        elif (root / "package-lock.json").is_file() or (root / "npm-shrinkwrap.json").is_file():
            if is_tool_available("npm"):
                res = run_cmd(["npm", "audit", "--omit=dev"], cwd=root, timeout=timeout)
                results.append({"name": "npm audit (prod)", "tool": "npm", "category": "Security", **res})
        elif is_tool_available("npm"):
            results.append({"name": "npm audit (prod)", "tool": "npm", "category": "Security", "status": "skipped: no lockfile", "exit_code": 0, "output": "Skipped: npm audit requires an existing package-lock.json."})

    if tsconfig.is_file():
        if is_tool_available("tsc"):
            res = run_cmd(["tsc", "--noEmit"], cwd=root, timeout=timeout)
            results.append({"name": "tsc --noEmit", "tool": "tsc", "category": "Typechecker", **res})
        else:
            results.append({"name": "tsc --noEmit", "tool": "tsc", "category": "Typechecker", "status": "skipped: not installed", "exit_code": 0, "output": ""})

    # 2. Python Checks
    pyproject = root / "pyproject.toml"
    setup_py = root / "setup.py"
    setup_cfg = root / "setup.cfg"
    req_txt = root / "requirements.txt"
    pipfile = root / "Pipfile"
    req_dir = root / "requirements"
    has_python = (
        pyproject.is_file()
        or setup_py.is_file()
        or setup_cfg.is_file()
        or req_txt.is_file()
        or pipfile.is_file()
        or (req_dir.is_dir() and any(req_dir.glob("*.txt")))
        or any(root.glob("*.py"))
        or any(root.glob("*/*.py"))
        or any(root.glob("*/*/*.py"))
    )

    if has_python:
        if is_tool_available("ruff"):
            res = run_cmd(["ruff", "check", "."], cwd=root, timeout=timeout)
            results.append({"name": "ruff check", "tool": "ruff", "category": "Linter", **res})
        elif is_tool_available("flake8"):
            res = run_cmd(["flake8", "."], cwd=root, timeout=timeout)
            results.append({"name": "flake8", "tool": "flake8", "category": "Linter", **res})
        else:
            results.append({"name": "python linter", "tool": "ruff/flake8", "category": "Linter", "status": "skipped: not installed", "exit_code": 0, "output": ""})

        if is_tool_available("mypy"):
            res = run_cmd(["mypy", "."], cwd=root, timeout=timeout)
            results.append({"name": "mypy", "tool": "mypy", "category": "Typechecker", **res})

        if is_tool_available("pip-audit"):
            res = run_cmd(["pip-audit"], cwd=root, timeout=timeout)
            results.append({"name": "pip-audit", "tool": "pip-audit", "category": "Security", **res})

        if is_tool_available("pytest"):
            if allow_tests:
                res = run_cmd(["pytest", "-q"], cwd=root, timeout=timeout)
                results.append({"name": "pytest", "tool": "pytest", "category": "Tests", **res})
            else:
                results.append({"name": "pytest", "tool": "pytest", "category": "Tests", "status": "available, not run", "exit_code": 0, "output": "Tests available; rerun with --allow-tests to execute."})

    # 3. Go Checks
    if (root / "go.mod").is_file():
        if is_tool_available("go"):
            res = run_cmd(["go", "vet", "./..."], cwd=root, timeout=timeout)
            results.append({"name": "go vet", "tool": "go", "category": "Linter", **res})
            if allow_tests:
                res = run_cmd(["go", "test", "-short", "./..."], cwd=root, timeout=timeout)
                results.append({"name": "go test", "tool": "go", "category": "Tests", **res})
            else:
                results.append({"name": "go test", "tool": "go", "category": "Tests", "status": "available, not run", "exit_code": 0, "output": "Tests available; rerun with --allow-tests to execute."})
        else:
            results.append({"name": "go tools", "tool": "go", "category": "Tooling", "status": "skipped: not installed", "exit_code": 0, "output": ""})

    # 4. Rust Checks
    if (root / "Cargo.toml").is_file():
        if is_tool_available("cargo"):
            res = run_cmd(["cargo", "check", "--quiet"], cwd=root, timeout=timeout)
            results.append({"name": "cargo check", "tool": "cargo", "category": "Typechecker", **res})
        else:
            results.append({"name": "cargo", "tool": "cargo", "category": "Tooling", "status": "skipped: not installed", "exit_code": 0, "output": ""})

    return {
        "target": str(root),
        "total_checks": len(results),
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "skipped": sum(1 for r in results if "skipped" in r["status"] or "available" in r["status"]),
        "checks": results
    }

def print_text_summary(report):
    print("=" * 70)
    print(f"CLAUGRAVITY SAFE CHECK RUNNER: {report['target']}")
    print(f"Total Checks: {report['total_checks']} | Passed: {report['passed']} | Failed: {report['failed']} | Skipped: {report['skipped']}")
    print("=" * 70)

    if not report["checks"]:
        print("No automated tool checks detected or executed for this project.")
        print("=" * 70)
        return

    for c in report["checks"]:
        badge = c["status"].upper()
        print(f"\n[{badge:18}] {c['name']} ({c['category']})")
        if c["output"]:
            for line in c["output"].splitlines()[:5]:
                print(f"    {line}")
            if len(c["output"].splitlines()) > 5:
                print("    ...")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Safely run native repository linters, type checks, and audits.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory of repository (default: .)")
    parser.add_argument("--timeout", type=int, default=30, help="Per-command timeout in seconds (default: 30)")
    parser.add_argument("--allow-tests", action="store_true", help="Allow running unit test commands")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    report = execute_checks(args.path, timeout=args.timeout, allow_tests=args.allow_tests)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_summary(report)

if __name__ == "__main__":
    main()
