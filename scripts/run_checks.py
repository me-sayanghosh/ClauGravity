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

    def add(name, tool, cat, cmd=None, status=None, msg=""):
        if cmd:
            results.append({"name": name, "tool": tool, "category": cat, **run_cmd(cmd, cwd=root, timeout=timeout)})
        else:
            results.append({"name": name, "tool": tool, "category": cat, "status": status, "exit_code": 0, "output": msg})

    # Detect Node.js package manager
    pm = "npm"
    if (root / "bun.lockb").is_file() or (root / "bun.lock").is_file():
        pm = "bun" if is_tool_available("bun") else "npm"
    elif (root / "pnpm-lock.yaml").is_file():
        pm = "pnpm" if is_tool_available("pnpm") else "npm"
    elif (root / "yarn.lock").is_file():
        pm = "yarn" if is_tool_available("yarn") else "npm"

    # 1. Node.js / JavaScript Checks
    pkg_json = root / "package.json"
    if pkg_json.is_file():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                scripts = json.load(f).get("scripts", {})

            if "lint" in scripts and is_tool_available(pm):
                add(f"{pm} run lint", pm, "Linter", cmd=[pm, "run", "lint", "--silent"])
            elif "lint" not in scripts and is_tool_available("eslint"):
                add("eslint", "eslint", "Linter", cmd=["eslint", "."])

            if "typecheck" in scripts and is_tool_available(pm):
                add(f"{pm} run typecheck", pm, "Typechecker", cmd=[pm, "run", "typecheck", "--silent"])

            if "test" in scripts:
                if allow_tests and is_tool_available(pm):
                    add(f"{pm} test", pm, "Tests", cmd=[pm, "test"] if pm == "yarn" else [pm, "test", "--silent"])
                else:
                    add(f"{pm} test", pm, "Tests", status="available, not run", msg="Tests available in package.json; rerun with --allow-tests to execute.")
        except Exception:
            pass

        # Production audit
        if (root / "yarn.lock").is_file() and is_tool_available("yarn"):
            add("yarn audit (prod)", "yarn", "Security", cmd=["yarn", "audit", "--groups", "dependencies"])
        elif (root / "pnpm-lock.yaml").is_file() and is_tool_available("pnpm"):
            add("pnpm audit (prod)", "pnpm", "Security", cmd=["pnpm", "audit", "--prod"])
        elif (root / "package-lock.json").is_file() or (root / "npm-shrinkwrap.json").is_file():
            if is_tool_available("npm"):
                add("npm audit (prod)", "npm", "Security", cmd=["npm", "audit", "--omit=dev"])
        elif is_tool_available("npm"):
            add("npm audit (prod)", "npm", "Security", status="skipped: no lockfile", msg="Skipped: npm audit requires an existing package-lock.json.")

    if (root / "tsconfig.json").is_file():
        if is_tool_available("tsc"):
            add("tsc --noEmit", "tsc", "Typechecker", cmd=["tsc", "--noEmit"])
        else:
            add("tsc --noEmit", "tsc", "Typechecker", status="skipped: not installed")

    # 2. Python Checks
    has_python = (
        any((root / m).is_file() for m in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile"))
        or ((root / "requirements").is_dir() and any((root / "requirements").glob("*.txt")))
        or any(root.glob("*.py")) or any(root.glob("*/*.py")) or any(root.glob("*/*/*.py"))
    )

    if has_python:
        if is_tool_available("ruff"):
            add("ruff check", "ruff", "Linter", cmd=["ruff", "check", "."])
        elif is_tool_available("flake8"):
            add("flake8", "flake8", "Linter", cmd=["flake8", "."])
        else:
            add("python linter", "ruff/flake8", "Linter", status="skipped: not installed")

        if is_tool_available("mypy"):
            add("mypy", "mypy", "Typechecker", cmd=["mypy", "."])

        if is_tool_available("bandit"):
            add("bandit", "bandit", "Security", cmd=["bandit", "-r", ".", "-ll", "-q"])

        if is_tool_available("pip-audit"):
            add("pip-audit", "pip-audit", "Security", cmd=["pip-audit"])

        # Test runner (pytest with fallback to python unittest)
        has_tests = any(root.glob("**/test_*.py")) or any(root.glob("**/*_test.py")) or (root / "tests").is_dir()
        if is_tool_available("pytest"):
            if allow_tests:
                add("pytest", "pytest", "Tests", cmd=["pytest", "-q"])
            else:
                add("pytest", "pytest", "Tests", status="available, not run", msg="Tests available; rerun with --allow-tests to execute.")
        elif has_tests:
            if allow_tests:
                add("python unittest", "unittest", "Tests", cmd=[sys.executable, "-m", "unittest", "discover", "-s", "."])
            else:
                add("python unittest", "unittest", "Tests", status="available, not run", msg="Unit tests detected; rerun with --allow-tests to execute.")

    # 3. Go Checks
    if (root / "go.mod").is_file():
        if is_tool_available("go"):
            add("go vet", "go", "Linter", cmd=["go", "vet", "./..."])
            if allow_tests:
                add("go test", "go", "Tests", cmd=["go", "test", "-short", "./..."])
            else:
                add("go test", "go", "Tests", status="available, not run", msg="Tests available; rerun with --allow-tests to execute.")
        else:
            add("go tools", "go", "Tooling", status="skipped: not installed")

    # 4. Rust Checks
    if (root / "Cargo.toml").is_file():
        if is_tool_available("cargo"):
            add("cargo check", "cargo", "Typechecker", cmd=["cargo", "check", "--quiet"])
        else:
            add("cargo", "cargo", "Tooling", status="skipped: not installed")

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
    parser.add_argument("--output", "-o", type=str, default=None, help="Save report to file path")
    args = parser.parse_args()

    report = execute_checks(args.path, timeout=args.timeout, allow_tests=args.allow_tests)

    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if args.json:
            out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
        else:
            import io
            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                print_text_summary(report)
            finally:
                sys.stdout = old_stdout
            out_p.write_text(buf.getvalue(), encoding="utf-8")
        print(f"Check results written to {args.output}")
    else:
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_text_summary(report)

if __name__ == "__main__":
    main()
