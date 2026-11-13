#!/usr/bin/env python3
"""diff_audit.py - ClauGravity Pull Request & Diff Review Auditor

Extracts modified files and lines from git diff or patch files, runs risk pattern
scanners on changed files, and filters findings specifically to modified lines.

Usage:
    python scripts/diff_audit.py [git-ref] [options]

Examples:
    python scripts/diff_audit.py                       # Audit uncommitted changes vs HEAD
    python scripts/diff_audit.py --staged              # Audit staged changes
    python scripts/diff_audit.py main...HEAD           # Audit branch PR changes against main
    python scripts/diff_audit.py --patch change.diff   # Audit changes from a patch file
    python scripts/diff_audit.py --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Add script directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import find_risk_patterns

HUNK_REGEX = re.compile(r"""^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@""")

def parse_diff_hunks(diff_text):
    """Parses a unified git diff into a mapping of {filepath: set(changed_line_numbers)}."""
    file_changes = {}
    current_file = None
    current_line = 0

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("+++ b/"):
            current_file = line[6:].strip()
            if current_file not in file_changes:
                file_changes[current_file] = set()
            continue
        if line.startswith("+++ /dev/null"):
            current_file = None
            continue

        if not current_file:
            continue

        hunk_match = HUNK_REGEX.match(line)
        if hunk_match:
            start_line = int(hunk_match.group(1))
            current_line = start_line
            continue

        if line.startswith("+") and not line.startswith("+++"):
            file_changes[current_file].add(current_line)
            current_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            # Deletions do not advance the new file line counter
            continue
        elif not line.startswith("\\"):
            # Context line
            current_line += 1

    return file_changes

def get_git_diff(ref=None, staged=False, cwd="."):
    """Executes git diff command and returns raw diff string."""
    cmd = ["git", "diff", "--unified=0"]
    if staged:
        cmd.append("--cached")
    elif ref:
        cmd.append(ref)
    else:
        cmd.append("HEAD")

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        return proc.stdout
    except subprocess.CalledProcessError as e:
        sys.exit(f"Git diff error ({e.returncode}): {e.stderr.strip()}")
    except FileNotFoundError:
        sys.exit("Error: 'git' command not found in PATH.")

def audit_diff(target_dir=".", diff_text=None, ref=None, staged=False):
    root = Path(target_dir).resolve()
    if diff_text is None:
        diff_text = get_git_diff(ref=ref, staged=staged, cwd=root)

    changed_lines_map = parse_diff_hunks(diff_text)
    modified_files = [f for f, lines in changed_lines_map.items() if lines]

    diff_hits = []
    total_unfiltered_hits = 0

    for rel_path in modified_files:
        full_path = root / rel_path
        if not full_path.is_file():
            continue

        file_hits = find_risk_patterns.scan_file(
            full_path,
            root,
            find_risk_patterns.RULES
        )
        total_unfiltered_hits += len(file_hits)

        modified_set = changed_lines_map.get(rel_path, set())
        for hit in file_hits:
            hit_line = hit["line_number"]
            # Check if hit is in or directly adjacent (+- 1 line) to a modified line
            if any(abs(hit_line - m_line) <= 1 for m_line in modified_set):
                hit["in_diff"] = True
                diff_hits.append(hit)

    # Determine PR Verdict
    severities = [h["severity"] for h in diff_hits]
    if any(s == "Critical" for s in severities) or sum(1 for s in severities if s == "High") >= 1:
        verdict = "BLOCK"
        rationale = "Critical or High severity risks detected in touched lines. Requires resolution before merging."
    elif any(s == "Medium" for s in severities):
        verdict = "FIX BEFORE MERGE"
        rationale = "Medium severity reliability or correctness defects found in diff."
    elif any(s in ("Low", "Info") for s in severities):
        verdict = "OK WITH NITS"
        rationale = "Minor cosmetic or low-risk observations identified; merge acceptable."
    else:
        verdict = "APPROVE"
        rationale = "No risk pattern violations detected in modified code diff."

    return {
        "root": str(root),
        "modified_files": modified_files,
        "total_modified_files": len(modified_files),
        "total_diff_leads": len(diff_hits),
        "verdict": verdict,
        "rationale": rationale,
        "hits": diff_hits
    }

def format_pr_review_markdown(result):
    lines = [
        "# ClauGravity Pull Request / Diff Review",
        f"**Verdict:** `{result['verdict']}`",
        f"**Rationale:** {result['rationale']}",
        f"**Modified Files Inspected:** {result['total_modified_files']}\n",
        "## Touched Files",
    ]
    for f in result["modified_files"]:
        lines.append(f"- `{f}`")

    lines.append(f"\n## Findings in Diff ({result['total_diff_leads']})")
    if not result["hits"]:
        lines.append("No defects detected in modified code diff. Clean review.")
    else:
        lines.append("| Severity | Rule ID | Location | Summary |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for h in result["hits"]:
            lines.append(f"| **{h['severity']}** | `{h['rule_id']}` | `{h['location']}` | {h['explanation']} |")

    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser(description="Audit pull requests and git diffs against ClauGravity risk patterns.")
    parser.add_argument("ref", nargs="?", default=None, help="Git revision or branch diff specifier (e.g. HEAD~1, main...HEAD)")
    parser.add_argument("--root", default=".", help="Root directory of the git repository (default: .)")
    parser.add_argument("--staged", action="store_true", help="Audit staged/cached changes only")
    parser.add_argument("--patch", type=str, default=None, help="Read diff from a patch file instead of git")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--output", "-o", type=str, default=None, help="Save review to output file")
    args = parser.parse_args()

    diff_text = None
    if args.patch:
        patch_file = Path(args.patch).resolve()
        if not patch_file.is_file():
            sys.exit(f"Error: Patch file not found at {patch_file}")
        diff_text = patch_file.read_text(encoding="utf-8", errors="ignore")

    audit_res = audit_diff(target_dir=args.root, diff_text=diff_text, ref=args.ref, staged=args.staged)

    if args.json:
        output_str = json.dumps(audit_res, indent=2)
    else:
        output_str = format_pr_review_markdown(audit_res)

    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output_str, encoding="utf-8")
        print(f"Diff review written to {args.output}")
    else:
        print(output_str)

if __name__ == "__main__":
    main()
