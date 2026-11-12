#!/usr/bin/env python3
"""verify_citations.py - ClauGravity Citation Verification Gate

Mechanically validates that all code locations and excerpts cited in an audit report
or PR review exist verbatim in the target repository.

Usage:
    python scripts/verify_citations.py <report.md> [--root PATH]

Examples:
    python scripts/verify_citations.py .claugravity/report.md --root .
    python scripts/verify_citations.py tests/fixture-report-iteration-1.md --root tests/fixture-project
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

LOCATION_REGEX = re.compile(r"""\*\*Location:\*\*\s*[`"]?([^\s`"]+)[`"]?""")
EVIDENCE_REGEX = re.compile(r"""\*\*Evidence:\*\*\s*```[a-zA-Z0-9_-]*[ \t]*\r?\n(.*?)```""", re.DOTALL)
FINDING_HEADER_REGEX = re.compile(r"""^###\s+(?:\[?([A-Za-z0-9_-]+)\]?:?|([A-Za-z0-9_-]+:))\s*(.*)$""", re.M)

def normalize_text(text):
    lines = [re.sub(r"""\s+""", " ", line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])

def parse_findings(report_text):
    findings = []
    # Split by finding blocks or scan sequentially
    # We look for finding sections containing **Location:** and **Evidence:**
    blocks = re.split(r"""(?=^###\s+)""", report_text, flags=re.M)

    for block in blocks:
        loc_match = LOCATION_REGEX.search(block)
        evi_match = EVIDENCE_REGEX.search(block)
        if not loc_match or not evi_match:
            continue

        header_match = re.search(r"""^###\s+(.*)$""", block, re.M)
        title = header_match.group(1).strip() if header_match else "Unknown Finding"

        loc_str = loc_match.group(1).strip()
        evidence_str = evi_match.group(1)

        findings.append({
            "title": title,
            "raw_location": loc_str,
            "evidence": evidence_str
        })
    return findings

def parse_location(loc_str):
    loc_clean = loc_str.strip().replace("\\", "/")
    if loc_clean.startswith("./"):
        loc_clean = loc_clean[2:]

    # Check if colon is just a Windows drive letter (e.g. C:/file.js)
    is_windows_drive = bool(re.match(r"^[a-zA-Z]:", loc_clean))
    colon_count = loc_clean.count(":")
    if colon_count == 0 or (is_windows_drive and colon_count == 1):
        return loc_clean, None, None

    file_part, line_part = loc_clean.rsplit(":", 1)
    if "-" in line_part:
        start_s, end_s = line_part.split("-", 1)
        start_s = start_s.strip().lstrip("Ll")
        end_s = end_s.strip().lstrip("Ll")
        try:
            return file_part, int(start_s), int(end_s)
        except ValueError:
            return file_part, None, None
    else:
        line_part = line_part.strip().lstrip("Ll")
        try:
            line_num = int(line_part)
            return file_part, line_num, line_num
        except ValueError:
            return file_part, None, None

def verify_single_citation(finding, root_dir, tolerance=5):
    raw_loc = finding["raw_location"]
    file_path_str, start_line, end_line = parse_location(raw_loc)

    target_file = Path(root_dir) / file_path_str
    if not target_file.is_file():
        return False, f"File not found: {file_path_str}"

    try:
        with open(target_file, "r", encoding="utf-8", errors="ignore") as f:
            file_lines = f.readlines()
    except Exception as e:
        return False, f"Could not read file {file_path_str}: {e}"

    total_lines = len(file_lines)

    if start_line is None or end_line is None:
        return False, f"Invalid line range syntax in: {raw_loc}"

    if start_line < 1 or start_line > total_lines + tolerance or start_line > end_line or end_line > total_lines + tolerance:
        return False, f"Line range {start_line}-{end_line} out of bounds (file has {total_lines} lines)"

    # Expand range by tolerance
    search_start = max(1, start_line - tolerance)
    search_end = min(total_lines, end_line + tolerance)

    window_text = "".join(file_lines[search_start - 1 : search_end])
    norm_window = normalize_text(window_text)
    norm_evidence = normalize_text(finding["evidence"])

    if not norm_evidence:
        return False, "Evidence excerpt is empty"

    if norm_evidence in norm_window:
        return True, "Verified exact match"

    # Line-by-line subset check
    evidence_lines = [l for l in norm_evidence.splitlines() if l]
    window_lines = [l for l in norm_window.splitlines() if l]

    if evidence_lines and all(any(el in wl for wl in window_lines) for el in evidence_lines):
        return True, "Verified line subset match"

    return False, f"Excerpt text not found in lines {search_start}-{search_end}"

def verify_report(report_path, root_path=".", tolerance=5, as_json=False):
    report_file = Path(report_path).resolve()
    root_dir = Path(root_path).resolve()

    if not report_file.is_file():
        sys.exit(f"Error: Report file not found at {report_file}")
    if not root_dir.is_dir():
        sys.exit(f"Error: Project root directory not found at {root_dir}")

    with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    findings = parse_findings(text)

    if not as_json:
        print("=" * 70)
        print(f"CLAUGRAVITY CITATION VERIFIER")
        print(f"Report: {report_file}")
        print(f"Target Root: {root_dir}")
        print(f"Total Cited Findings Parsed: {len(findings)}")
        print("=" * 70)

    if not findings:
        if as_json:
            print(json.dumps({
                "report": str(report_file),
                "root": str(root_dir),
                "total_citations": 0,
                "passed": 0,
                "failed": 0,
                "all_passed": False,
                "citations": [],
                "error": "No finding citations matching template layout were found in report."
            }, indent=2))
        else:
            print("Warning: No finding citations matching template layout were found in report.")
            print("Expected format: **Location:** `path:line` followed by **Evidence:** and fenced code block.")
        return False

    all_passed = True
    pass_count = 0
    fail_count = 0
    results = []

    for idx, f in enumerate(findings, start=1):
        ok, reason = verify_single_citation(f, root_dir, tolerance=tolerance)
        status = "PASS" if ok else "FAIL"
        results.append({
            "id": idx,
            "title": f["title"],
            "location": f["raw_location"],
            "status": status,
            "reason": reason
        })
        if ok:
            pass_count += 1
            if not as_json:
                print(f"[{status}] Finding #{idx}: {f['raw_location']}")
                print(f"       {f['title']}")
        else:
            fail_count += 1
            all_passed = False
            if not as_json:
                print(f"[{status}] Finding #{idx}: {f['raw_location']}")
                print(f"       {f['title']}")
                print(f"       Reason: {reason}")

    if as_json:
        print(json.dumps({
            "report": str(report_file),
            "root": str(root_dir),
            "total_citations": len(findings),
            "passed": pass_count,
            "failed": fail_count,
            "all_passed": all_passed,
            "citations": results
        }, indent=2))
    else:
        print("-" * 70)
        print(f"SUMMARY: {pass_count} Passed | {fail_count} Failed")
        print("=" * 70)

    return all_passed

def main():
    parser = argparse.ArgumentParser(description="Verify that all citations in an audit report exist verbatim in code.")
    parser.add_argument("report", help="Path to markdown audit report or PR review")
    parser.add_argument("--root", default=".", help="Root directory of audited project (default: .)")
    parser.add_argument("--tolerance", type=int, default=5, help="Line search tolerance window (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    passed = verify_report(args.report, root_path=args.root, tolerance=args.tolerance, as_json=args.json)
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
