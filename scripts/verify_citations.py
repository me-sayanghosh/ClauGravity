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

LOCATION_REGEX = re.compile(r"""\*\*Location:\*\*\s*(?:\[`?|[`"<])?([a-zA-Z0-9_./\\-]+(?::\s*L?\d+(?:\s*-\s*L?\d+)?)?)(?:`?\](?:\([^)]*\))?|[`">])?""")
EVIDENCE_REGEX = re.compile(r"""\*\*Evidence:\*\*(?:[^\n`]*\r?\n\s*)*?(`{3,4})[a-zA-Z0-9_-]*[ \t]*\r?\n(.*?)\1""", re.DOTALL)
FINDING_HEADER_REGEX = re.compile(r"""^#{2,4}\s+(?:\[?([A-Za-z0-9_-]+)\]?:?|([A-Za-z0-9_-]+:))\s*(.*)$""", re.M)

def normalize_text(text):
    lines = [re.sub(r"""\s+""", " ", line).strip() for line in text.splitlines()]
    return "\n".join([line for line in lines if line])

def parse_findings(report_text):
    findings = []
    for block in re.split(r"""(?=^#{2,4}\s+)""", report_text, flags=re.M):
        loc_m = LOCATION_REGEX.search(block)
        evi_m = EVIDENCE_REGEX.search(block)
        if loc_m and evi_m:
            hdr_m = re.search(r"""^#{2,4}\s+(.*)$""", block, re.M)
            groups = evi_m.groups()
            findings.append({
                "title": hdr_m.group(1).strip() if hdr_m else "Unknown Finding",
                "raw_location": loc_m.group(1).strip(),
                "evidence": groups[1] if len(groups) >= 2 else groups[0]
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
    line_part = line_part.replace(" ", "")
    if "-" in line_part:
        parts = [p.strip().lstrip("Ll") for p in line_part.split("-", 1)]
        try:
            return file_part, int(parts[0]), int(parts[1])
        except ValueError:
            return file_part, None, None
    try:
        val = int(line_part.lstrip("Ll"))
        return file_part, val, val
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

    # Search the broader file to report actionable diagnostics if line numbers drifted
    full_text = normalize_text("".join(file_lines))
    if norm_evidence in full_text:
        first_evi = evidence_lines[0] if evidence_lines else norm_evidence
        for idx, fl in enumerate(file_lines, start=1):
            if first_evi in normalize_text(fl):
                return False, f"Excerpt text not found in lines {search_start}-{search_end} (candidate found near line {idx}; adjust citation range)"

    return False, f"Excerpt text not found in lines {search_start}-{search_end}"

def verify_report(report_path, root_path=".", tolerance=5, as_json=False, output_path=None):
    report_file = Path(report_path).resolve()
    root_dir = Path(root_path).resolve()

    if not report_file.is_file():
        sys.exit(f"Error: Report file not found at {report_file}")
    if not root_dir.is_dir():
        sys.exit(f"Error: Project root directory not found at {root_dir}")

    with open(report_file, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    findings = parse_findings(text)

    if not as_json and not output_path:
        print("=" * 70)
        print(f"CLAUGRAVITY CITATION VERIFIER")
        print(f"Report: {report_file}")
        print(f"Target Root: {root_dir}")
        print(f"Total Cited Findings Parsed: {len(findings)}")
        print("=" * 70)

    if not findings:
        res_data = {
            "report": str(report_file),
            "root": str(root_dir),
            "total_citations": 0,
            "passed": 0,
            "failed": 0,
            "all_passed": False,
            "citations": [],
            "error": "No finding citations matching template layout were found in report."
        }
        if as_json or output_path:
            out_str = json.dumps(res_data, indent=2)
            if output_path:
                Path(output_path).resolve().write_text(out_str, encoding="utf-8")
            if as_json:
                print(out_str)
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
            if not as_json and not output_path:
                print(f"[{status}] Finding #{idx}: {f['raw_location']}")
                print(f"       {f['title']}")
        else:
            fail_count += 1
            all_passed = False
            if not as_json and not output_path:
                print(f"[{status}] Finding #{idx}: {f['raw_location']}")
                print(f"       {f['title']}")
                print(f"       Reason: {reason}")

    summary_data = {
        "report": str(report_file),
        "root": str(root_dir),
        "total_citations": len(findings),
        "passed": pass_count,
        "failed": fail_count,
        "all_passed": all_passed,
        "citations": results
    }

    if output_path:
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
        if not as_json:
            print(f"Verification results written to {output_path}")

    if as_json:
        print(json.dumps(summary_data, indent=2))
    elif not output_path:
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
    parser.add_argument("--output", "-o", type=str, default=None, help="Save verification report JSON to file")
    args = parser.parse_args()

    passed = verify_report(args.report, root_path=args.root, tolerance=args.tolerance, as_json=args.json, output_path=args.output)
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
