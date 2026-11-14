#!/usr/bin/env python3
"""chunk_plan.py - ClauGravity Module Chunk Planner

Partitions a repository into risk-ranked review chunks for token-efficient
auditing of large repositories.

Usage:
    python scripts/chunk_plan.py [path] [--max-chunks N] [--json]

Examples:
    python scripts/chunk_plan.py .
    python scripts/chunk_plan.py tests/fixture-project --max-chunks 5 --json
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from scripts.common import (
        LOCKFILES, BINARY_EXTENSIONS,
        load_ignore_patterns, is_ignored, count_lines
    )
except ImportError:
    from common import (
        LOCKFILES, BINARY_EXTENSIONS,
        load_ignore_patterns, is_ignored, count_lines
    )

RISK_WEIGHTS = {
    "auth": 100,
    "payment": 90,
    "db": 75,
    "security": 70,
    "routes": 60,
    "queue": 55,
    "io": 50
}

KEYWORD_MAP = {
    "auth": ["auth", "session", "jwt", "user", "login", "token", "permission", "rbac", "oauth", "password", "credential"],
    "payment": ["pay", "billing", "stripe", "invoice", "subscript", "checkout", "wallet", "balance", "pric", "fee", "cost", "money", "currency", "tax"],
    "db": ["db", "model", "schema", "repositor", "database", "store", "migrat", "entity", "query", "sql"],
    "security": ["crypto", "cipher", "secret", "cert", "hash", "sign", "sanitize", "guard", "firewall", "cors"],
    "routes": ["route", "controller", "api", "endpoint", "handler", "view", "router"],
    "queue": ["queue", "worker", "job", "celery", "bull", "kafka", "rabbit", "task", "consumer", "producer"],
    "io": ["upload", "file", "process", "exec", "download", "storage", "fs", "stream"]
}

def get_recent_churn(root_dir):
    churn = {}
    try:
        # Determine git root to strip subdirectory prefix if needed
        git_root_out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root_dir,
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        git_root = Path(git_root_out).resolve()
        target_root = Path(root_dir).resolve()

        rel_prefix = ""
        try:
            diff_rel = target_root.relative_to(git_root)
            if str(diff_rel) != ".":
                rel_prefix = str(diff_rel).replace(os.sep, "/") + "/"
        except ValueError:
            pass

        out = subprocess.check_output(
            ["git", "log", "--since=6.months", "--name-only", "--pretty=format:"],
            cwd=root_dir,
            text=True,
            stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            line = line.strip().replace(os.sep, "/")
            if not line:
                continue
            if rel_prefix and line.startswith(rel_prefix):
                sub_line = line[len(rel_prefix):]
                churn[sub_line] = churn.get(sub_line, 0) + 1
            churn[line] = churn.get(line, 0) + 1
    except Exception:
        pass
    return churn

def calculate_file_risk(rel_path, loc, churn_count):
    lower = rel_path.lower()
    score = 0
    matched_reasons = []

    for cat, weight in RISK_WEIGHTS.items():
        words = KEYWORD_MAP[cat]
        if any(w in lower for w in words):
            score += weight
            matched_reasons.append(cat)

    # Churn weight
    if churn_count > 0:
        score += min(churn_count * 5, 50)
        matched_reasons.append(f"churn({churn_count})")

    # LOC scale
    score += min(loc // 50, 30)

    return score, matched_reasons

def generate_chunks(target_path, max_chunks=8, max_files_per_chunk=25):
    root = Path(target_path).resolve()
    if not root.is_dir():
        sys.exit(f"Error: Target path {root} is not a directory.")

    patterns = load_ignore_patterns(root)
    churn = get_recent_churn(root)

    # Group files by immediate logical module/directory
    module_files = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_ignored(Path(dirpath) / d, root, patterns)]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if is_ignored(fpath, root, patterns) or fname in LOCKFILES:
                continue
            if fpath.suffix.lower() in BINARY_EXTENSIONS or fname.endswith(".min.js"):
                continue

            rel_str = str(fpath.relative_to(root)).replace(os.sep, "/")
            rel_parts = Path(rel_str).parts

            if len(rel_parts) == 1:
                module_name = "root"
            elif rel_parts[0] in {"src", "lib", "app", "pkg"} and len(rel_parts) > 2:
                module_name = f"{rel_parts[0]}/{rel_parts[1]}"
            elif rel_parts[0] in {"packages", "apps", "services", "modules"} and len(rel_parts) > 2:
                module_name = f"{rel_parts[0]}/{rel_parts[1]}"
            else:
                module_name = rel_parts[0]

            loc = count_lines(fpath)
            file_churn = churn.get(rel_str, 0)
            risk, reasons = calculate_file_risk(rel_str, loc, file_churn)

            module_files.setdefault(module_name, []).append({
                "path": rel_str,
                "loc": loc,
                "churn": file_churn,
                "risk_score": risk,
                "reasons": reasons
            })

    chunks = []
    chunk_id = 1

    for mod_name, files in module_files.items():
        files.sort(key=lambda x: x["risk_score"], reverse=True)

        # Subdivide large modules exceeding max_files_per_chunk
        for i in range(0, len(files), max_files_per_chunk):
            sub_files = files[i:i + max_files_per_chunk]
            name = mod_name if len(files) <= max_files_per_chunk else f"{mod_name} (part {i//max_files_per_chunk + 1})"
            sub_risk = sum(f["risk_score"] for f in sub_files)
            chunks.append({
                "chunk_id": chunk_id,
                "name": name,
                "module": mod_name,
                "file_count": len(sub_files),
                "total_loc": sum(f["loc"] for f in sub_files),
                "risk_score": sub_risk,
                "files": [f["path"] for f in sub_files]
            })
            chunk_id += 1

    chunks.sort(key=lambda c: c["risk_score"], reverse=True)
    if max_chunks and len(chunks) > max_chunks:
        chunks = chunks[:max_chunks]

    # Re-assign sequential IDs in priority order
    for idx, c in enumerate(chunks, start=1):
        c["chunk_id"] = idx

    return {
        "target": str(root),
        "total_chunks": len(chunks),
        "chunks": chunks
    }

def generate_markdown_plan(data):
    lines = [
        f"# ClauGravity Audit Chunk Plan",
        f"**Target:** `{data['target']}` | **Total Chunks:** {data['total_chunks']}\n",
        "| Chunk | Module / Scope | Risk Score | Files | LOC | Primary Files |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for c in data["chunks"]:
        top_files = ", ".join(f"`{f}`" for f in c["files"][:3])
        if len(c["files"]) > 3:
            top_files += f" (+{len(c['files']) - 3} more)"
        lines.append(f"| #{c['chunk_id']:02d} | `{c['name']}` | **{c['risk_score']}** | {c['file_count']} | {c['total_loc']} | {top_files} |")

    lines.append("\n## Audit Sequence Guidance")
    lines.append("Audit each chunk strictly in priority order. After auditing each chunk, record confirmed findings and update `.claugravity/notes.md`.")
    return "\n".join(lines) + "\n"

def print_plan(data):
    print("=" * 70)
    print(f"CLAUGRAVITY AUDIT CHUNK PLAN: {data['target']}")
    print(f"Planned Chunks: {data['total_chunks']}")
    print("=" * 70)

    for c in data["chunks"]:
        print(f"\n[CHUNK {c['chunk_id']:02d}] {c['name']} (Risk Score: {c['risk_score']})")
        print(f"  Summary: {c['file_count']} files, {c['total_loc']} LOC")
        print("  Suggested Reading:")
        for f in c["files"][:8]:
            print(f"    - {f}")
        if len(c["files"]) > 8:
            print(f"    ... and {len(c['files']) - 8} more files")
    print("\n" + "=" * 70)
    print("Execution Guidance: Audit chunk-by-chunk in this exact priority order.")
    print("Record progress and summarize notes into .claugravity/notes.md.")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Partition repository into risk-weighted audit chunks.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory of repository (default: .)")
    parser.add_argument("--max-chunks", type=int, default=8, help="Maximum number of review chunks to output (default: 8)")
    parser.add_argument("--json", action="store_true", help="Output plan in JSON format")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format (default: text)")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output destination file path")
    args = parser.parse_args()

    plan = generate_chunks(args.path, max_chunks=args.max_chunks)
    fmt = "json" if args.json else args.format

    if fmt == "json":
        output_str = json.dumps(plan, indent=2)
    elif fmt == "markdown":
        output_str = generate_markdown_plan(plan)
    else:
        output_str = None

    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if output_str is not None:
            out_p.write_text(output_str, encoding="utf-8")
        else:
            import io
            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                print_plan(plan)
            finally:
                sys.stdout = old_stdout
            out_p.write_text(buf.getvalue(), encoding="utf-8")
        print(f"Chunk plan written to {args.output}")
    else:
        if output_str is not None:
            print(output_str)
        else:
            print_plan(plan)

if __name__ == "__main__":
    main()
