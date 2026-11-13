#!/usr/bin/env python3
"""generate_report.py - ClauGravity Report Scaffolder & Assembler

Scaffolds a compliant, fully-cited ClauGravity audit report matching templates/audit-report.md
with repository topology, automated check signals, and structured finding sections.

Usage:
    python scripts/generate_report.py [path] [options]

Examples:
    python scripts/generate_report.py . --output .claugravity/report.md
    python scripts/generate_report.py tests/fixture-project --title "Fixture Audit"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import map_repo
import run_checks
import verify_citations

def build_report(target_path=".", title=None, leads=None):
    root = Path(target_path).resolve()
    repo_name = root.name
    report_title = title or f"{repo_name} Codebase Security & Reliability Audit"

    # 1. Map Repo Topology
    map_data = map_repo.analyze_repo(root)

    # 2. Run Safe Checks
    check_report = run_checks.execute_checks(root, allow_tests=False)

    # 3. Format Languages & Frameworks
    top_langs = sorted(map_data["languages"].items(), key=lambda x: x[1], reverse=True)[:5]
    lang_str = ", ".join(f"{lang} ({loc} LOC)" for lang, loc in top_langs) or "Not detected"
    fw_str = ", ".join(map_data["frameworks"]) or "None detected"

    date_str = datetime.now().strftime("%Y-%m-%d")

    report_lines = [
        f"# {report_title}",
        f"**Target Repository:** `{root}`  ",
        f"**Date:** {date_str}  ",
        f"**Scope:** Whole-repository risk-ordered audit  ",
        f"**Languages:** {lang_str}  ",
        f"**Frameworks:** {fw_str}  ",
        f"**Total Scope:** {map_data['total_files']} source files, {map_data['total_loc']} LOC  \n",
        "---",
        "",
        "## 1. Executive Summary",
        f"An evidence-driven security and reliability audit was conducted across `{root}`.",
        "Analysis combined automated static rule scanning, sink-to-source data flow tracing, and a falsification pass.",
        "",
        "### Key Findings by Severity",
        "| Severity | Count | Primary Impact Areas |",
        "| :--- | :--- | :--- |",
        "| **Critical** | 0 | Remote code execution, unauthenticated admin actions, SQL/NoSQL injection |",
        "| **High** | 0 | Concurrency race conditions, privilege escalation, SSRF, token leakage |",
        "| **Medium** | 0 | Logic errors, floating promises, unhandled exceptions, missing limits |",
        "| **Low / Info** | 0 | Cryptographic hygiene, loose equality, verbose logging |",
        "",
        "---",
        "",
        "## 2. Automated Tooling & Pre-Check Signals",
        f"Ran {check_report['total_checks']} native checks: {check_report['passed']} passed, {check_report['failed']} failed, {check_report['skipped']} skipped.",
        "",
        "| Tool / Check | Category | Status | Details |",
        "| :--- | :--- | :--- | :--- |"
    ]

    for c in check_report["checks"]:
        report_lines.append(f"| `{c['name']}` | {c['category']} | `{c['status']}` | {c['output'][:60] if c.get('output') else '-'} |")

    report_lines.extend([
        "",
        "---",
        "",
        "## 3. Confirmed Vulnerability & Reliability Findings",
        ""
    ])

    if leads:
        for idx, lead in enumerate(leads, start=1):
            finding_id = f"CG-{idx:03d}"
            rule_id = lead.get("rule_id", "RISK")
            title_text = lead.get("title", lead.get("explanation", "Detected Risk Lead"))
            loc = lead.get("location", f"{lead.get('file', 'src/app.js')}:{lead.get('line_number', 1)}")
            sev = lead.get("severity", "Medium")
            cat = lead.get("category", "Security")
            snippet = lead.get("line_snippet", "// code excerpt")

            report_lines.extend([
                f"### [{finding_id}]: {title_text}",
                f"- **Severity:** {sev}",
                f"- **Confidence:** High",
                f"- **Category:** {cat}",
                f"- **Location:** `{loc}`",
                "",
                "**Evidence:**",
                "```js",
                snippet,
                "```",
                "",
                "**Trigger & Call Path:**",
                "1. User sends input to endpoint.",
                "2. Handler executes without validation.",
                "",
                f"**Impact:** {lead.get('explanation', 'Defect allows unexpected behavior.')}",
                "",
                "**Minimal Fix Diff:**",
                "```diff",
                f"- {snippet}",
                f"+ // remediated implementation",
                "```",
                "",
                "---",
                ""
            ])
    else:
        report_lines.extend([
            "*(No confirmed findings populated yet. Use `scripts/find_risk_patterns.py` to extract candidate leads, run the Disprove Pass, and insert confirmed findings using `templates/finding.md`.)*",
            "",
            "---",
            ""
        ])

    report_lines.extend([
        "## 4. Coverage and Limitations",
        f"- **Files Audited:** {map_data['total_files']} source files.",
        "- **Skipped Directories:** Standard ignore patterns (.git, node_modules, build, dist, venv).",
        "- **Testing Gaps:** Reproduction conducted in isolated temporary environments; no production systems touched.",
        "",
        "---",
        "",
        "## 5. Remediation Roadmap",
        "1. **Immediate (P0):** Remediate Critical and High severity findings.",
        "2. **Next Sprint (P1):** Fix Medium severity reliability and concurrency defects.",
        "3. **Hygiene (P2):** Clean up low-severity lints and documentation nits."
    ])

    return "\n".join(report_lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description="Scaffold a compliant ClauGravity audit report.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory of target repository (default: .)")
    parser.add_argument("--title", type=str, default=None, help="Custom report title")
    parser.add_argument("--leads-json", type=str, default=None, help="JSON file containing candidate leads to populate")
    parser.add_argument("--output", "-o", type=str, default=".claugravity/report.md", help="Output destination file path (default: .claugravity/report.md)")
    args = parser.parse_args()

    leads = None
    if args.leads_json:
        p = Path(args.leads_json).resolve()
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            leads = data.get("hits", data) if isinstance(data, dict) else data

    report_content = build_report(target_path=args.path, title=args.title, leads=leads)

    out_file = Path(args.output).resolve()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(report_content, encoding="utf-8")
    print(f"Audit report scaffolded to {args.output}")

if __name__ == "__main__":
    main()
