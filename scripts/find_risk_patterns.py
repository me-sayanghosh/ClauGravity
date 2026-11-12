#!/usr/bin/env python3
"""find_risk_patterns.py - ClauGravity Heuristic Risk Pattern Scanner

Scans source code for potential security flaws, concurrency hazards, and bugs.
Outputs a prioritized list of candidate LEADS for subsequent verification.

Usage:
    python scripts/find_risk_patterns.py [path] [options]

Options:
    --json                Output results in JSON format
    --category CATEGORY   Filter by category (Security, Concurrency, etc.)
    --min-severity SEV    Filter by minimum severity (Critical, High, Medium, Low, Info)
    --max-hits N          Limit total displayed hits (default: 100)

Examples:
    python scripts/find_risk_patterns.py .
    python scripts/find_risk_patterns.py src/ --category Security --min-severity High
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_IGNORES = {
    ".git", "node_modules", "dist", "build", ".next", "out", "coverage",
    "venv", ".venv", "__pycache__", "vendor", "target", ".idea", ".vscode",
    ".claugravity", ".pytest_cache", ".mypy_cache", ".ruff_cache"
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock",
    "poetry.lock", "composer.lock", "Pipfile.lock", "Gemfile.lock"
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".zip", ".tar", ".gz", ".7z", ".pdf", ".exe", ".bin",
    ".so", ".dylib", ".dll", ".pyc", ".class", ".jar", ".war", ".docx", ".xlsx"
}

SEVERITY_ORDER = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Info": 0
}

# Base Rule Registry
RULES = [
    {
        "id": "SAMPLE-SEC-01",
        "category": "Security",
        "regex": re.compile(r"""\beval\s*\(""", re.I),
        "languages": [".js", ".ts", ".py", ".php", ".rb"],
        "severity_hint": "Critical",
        "explanation": "Use of eval() introduces immediate risk of arbitrary code execution."
    },
    {
        "id": "SAMPLE-CONC-01",
        "category": "Concurrency",
        "regex": re.compile(r"""\.forEach\s*\(\s*async\b"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Array.forEach with an async callback does not await promises, causing unmanaged concurrency."
    }
]

def load_ignore_patterns(root_dir):
    patterns = set(DEFAULT_IGNORES)
    ignore_file = Path(root_dir) / ".claugravityignore"
    if ignore_file.is_file():
        try:
            with open(ignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.add(line)
        except Exception:
            pass
    return patterns

def is_ignored(path, root_dir, patterns):
    try:
        rel = path.relative_to(root_dir)
    except ValueError:
        return False
    parts = rel.parts
    for p in parts:
        if p in patterns:
            return True
        for pat in patterns:
            if fnmatch.fnmatch(p, pat):
                return True
    rel_str = str(rel).replace(os.sep, "/")
    for pat in patterns:
        if fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(path.name, pat):
            return True
    return False

def scan_file(file_path, root_dir, rules, category_filter=None, min_sev_score=0):
    hits = []
    ext = file_path.suffix.lower()
    applicable_rules = [
        r for r in rules
        if (not r.get("languages") or ext in r["languages"])
        and (not category_filter or r["category"].lower() == category_filter.lower())
        and SEVERITY_ORDER.get(r["severity_hint"], 0) >= min_sev_score
    ]

    if not applicable_rules:
        return hits

    try:
        rel_path = str(file_path.relative_to(root_dir)).replace(os.sep, "/")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                if len(line) > 1000:
                    continue
                for rule in applicable_rules:
                    if rule["regex"].search(line):
                        hits.append({
                            "rule_id": rule["id"],
                            "category": rule["category"],
                            "severity": rule["severity_hint"],
                            "location": f"{rel_path}:{line_no}",
                            "line_number": line_no,
                            "file": rel_path,
                            "line_snippet": line.strip()[:160],
                            "explanation": rule["explanation"]
                        })
    except Exception:
        pass
    return hits

def run_scan(target_path, rules, category=None, min_severity=None, max_hits=100, max_file_bytes=2*1024*1024):
    root = Path(target_path).resolve()
    if not root.exists():
        sys.exit(f"Error: Path {root} does not exist.")

    patterns = load_ignore_patterns(root if root.is_dir() else root.parent)
    min_sev_score = SEVERITY_ORDER.get(min_severity, 0) if min_severity else 0

    all_hits = []

    if root.is_file():
        all_hits.extend(scan_file(root, root.parent, rules, category, min_sev_score))
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not is_ignored(Path(dirpath) / d, root, patterns)]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                if is_ignored(fpath, root, patterns) or fname in LOCKFILES:
                    continue
                if fpath.suffix.lower() in BINARY_EXTENSIONS or fname.endswith(".min.js"):
                    continue
                try:
                    if fpath.stat().st_size > max_file_bytes:
                        continue
                except OSError:
                    continue

                hits = scan_file(fpath, root, rules, category, min_sev_score)
                all_hits.extend(hits)

    all_hits.sort(key=lambda h: SEVERITY_ORDER.get(h["severity"], 0), reverse=True)
    capped_hits = all_hits[:max_hits]

    return {
        "target": str(root),
        "total_hits": len(all_hits),
        "displayed_hits": len(capped_hits),
        "hits": capped_hits
    }

def print_text_report(scan_res):
    print("=" * 70)
    print("CLAUGRAVITY RISK PATTERN SCANNER")
    print("These are LEADS to verify, not confirmed bugs.")
    print("=" * 70)
    print(f"Target: {scan_res['target']}")
    print(f"Total Leads Identified: {scan_res['total_hits']} (showing top {scan_res['displayed_hits']})")
    print("-" * 70)

    if not scan_res["hits"]:
        print("No risk pattern leads detected.")
        print("=" * 70)
        return

    by_category = {}
    for h in scan_res["hits"]:
        by_category.setdefault(h["category"], []).append(h)

    for cat, items in by_category.items():
        print(f"\n[{cat.upper()}] ({len(items)} leads)")
        for item in items:
            print(f"  [{item['severity']:8}] {item['rule_id']}: {item['location']}")
            print(f"             Snippet: {item['line_snippet']}")
            print(f"             Hint   : {item['explanation']}")

    print("\n" + "=" * 70)
    print("Next step: Run the Disprove Pass to verify or eliminate each lead.")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Scan repository for candidate bug and vulnerability patterns.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory or file to scan (default: .)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (Security, Concurrency, etc.)")
    parser.add_argument("--min-severity", type=str, default=None, choices=["Critical", "High", "Medium", "Low", "Info"], help="Minimum severity")
    parser.add_argument("--max-hits", type=int, default=100, help="Maximum number of hits to display (default: 100)")
    args = parser.parse_args()

    results = run_scan(args.path, RULES, category=args.category, min_severity=args.min_severity, max_hits=args.max_hits)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_text_report(results)

if __name__ == "__main__":
    main()
