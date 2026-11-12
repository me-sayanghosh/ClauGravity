#!/usr/bin/env python3
"""map_repo.py - ClauGravity Repository Topology Mapper

Analyzes repository structure, entry points, routes, frameworks, and manifests
without reading full source bodies into agent context.

Usage:
    python scripts/map_repo.py [path] [--json] [--max-depth N]

Examples:
    python scripts/map_repo.py .
    python scripts/map_repo.py /path/to/project --json
    python scripts/map_repo.py tests/fixture-project --max-depth 4
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
    ".claugravity", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".DS_Store", "Thumbs.db"
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

EXT_LANG_MAP = {
    ".js": "JavaScript", ".jsx": "JavaScript (React)",
    ".ts": "TypeScript", ".tsx": "TypeScript (React)",
    ".py": "Python", ".go": "Go", ".java": "Java",
    ".kt": "Kotlin", ".cs": "C#", ".php": "PHP",
    ".rb": "Ruby", ".rs": "Rust", ".c": "C", ".cpp": "C++",
    ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".sh": "Shell"
}

ROUTE_REGEXES = [
    # Express / Fastify / Node routers
    re.compile(r"""\b(?:app|router|fastify|server)\.(get|post|put|delete|patch|options|all|route)\s*\(\s*['"`]([^'"`]+)['"`]""", re.I),
    # Flask / FastAPI Python decorators
    re.compile(r"""@(?:app|router|api|bp|blueprint|api_router)\.(route|get|post|put|delete|patch)\s*\(\s*['"`]([^'"`]+)['"`]""", re.I),
    # Django path / re_path
    re.compile(r"""\b(?:path|re_path)\s*\(\s*['"`]([^'"`]+)['"`]"""),
    # Gin Go routes
    re.compile(r"""\b(?:r|router|engine|group|v1|v2|api)\.(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD|Any)\s*\(\s*['"`]([^'"`]+)['"`]"""),
    # Spring Boot Java annotations
    re.compile(r"""@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*\(\s*(?:(?:value|path)\s*=\s*)?['"`]([^'"`]+)['"`]"""),
]

def detect_frameworks(root, manifests):
    frameworks = set()
    for m in manifests:
        mpath = root / m
        if not mpath.is_file():
            continue
        try:
            content = mpath.read_text(encoding="utf-8", errors="ignore").lower()
            if m.endswith("package.json"):
                for fw in ["express", "react", "next", "vue", "fastify", "nestjs", "koa", "angular", "svelte"]:
                    if f'"{fw}"' in content or (fw == "nestjs" and "@nestjs/" in content) or (fw == "angular" and "@angular/" in content):
                        frameworks.add(fw.capitalize() if fw != "next" else "Next.js")
            elif m.endswith((".txt", ".toml")):
                for fw in ["django", "flask", "fastapi", "tornado", "pyramid"]:
                    if fw in content:
                        frameworks.add(fw.capitalize() if fw != "fastapi" else "FastAPI")
            elif m.endswith("go.mod"):
                for fw in ["gin", "fiber", "echo", "chi"]:
                    if fw in content:
                        frameworks.add(fw.capitalize())
            elif m.endswith(("pom.xml", "build.gradle", "build.gradle.kts")):
                if "spring" in content:
                    frameworks.add("Spring Boot")
        except Exception:
            pass
    return sorted(list(frameworks))

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

def count_lines(file_path):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0

def scan_routes(file_path, root_dir):
    routes = []
    try:
        rel_path = str(file_path.relative_to(root_dir)).replace(os.sep, "/")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, start=1):
                for rx in ROUTE_REGEXES:
                    m = rx.search(line)
                    if m:
                        groups = m.groups()
                        if len(groups) >= 2:
                            method = groups[0].upper()
                            endpoint = groups[1]
                        else:
                            method = "ROUTE"
                            endpoint = groups[0]
                        routes.append({
                            "method": method,
                            "path": endpoint,
                            "location": f"{rel_path}:{idx}"
                        })
                        break
    except Exception:
        pass
    return routes

def analyze_repo(target_path, max_depth=6):
    root = Path(target_path).resolve()
    if not root.is_dir():
        sys.exit(f"Error: Target path {root} is not a directory.")

    patterns = load_ignore_patterns(root)

    manifests = []
    configs = []
    ci_docker = []
    test_dirs = set()
    entry_points = []
    all_files = []
    loc_by_top = {}
    routes = []
    lang_counts = {}

    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        if len(rel_dir.parts) > max_depth:
            dirnames.clear()
            continue

        dirnames[:] = [d for d in dirnames if not is_ignored(Path(dirpath) / d, root, patterns)]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if is_ignored(fpath, root, patterns) or fname in LOCKFILES:
                continue

            ext = fpath.suffix.lower()
            if ext in BINARY_EXTENSIONS or fname.endswith(".min.js") or fname.endswith(".min.css"):
                continue

            rel_str = str(fpath.relative_to(root)).replace(os.sep, "/")
            top_dir = rel_dir.parts[0] if rel_dir.parts else "."
            lines = count_lines(fpath)
            loc_by_top[top_dir] = loc_by_top.get(top_dir, 0) + lines

            all_files.append({"path": rel_str, "loc": lines, "ext": ext})

            if ext in EXT_LANG_MAP:
                lang = EXT_LANG_MAP[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + lines

            if fname in {"package.json", "pyproject.toml", "requirements.txt", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts", "Cargo.toml", "Gemfile"}:
                manifests.append(rel_str)

            if fname.startswith(".env") or fname.endswith("config.js") or fname.endswith("config.ts") or fname.endswith("config.py") or fname.endswith("settings.py"):
                configs.append(rel_str)

            if ("docker" in fname.lower()
                or rel_str.startswith(".github")
                or rel_str.startswith(".gitlab")
                or fname.startswith("jenkins")
                or fname in {".travis.yml", "azure-pipelines.yml"}
                or "-ci." in fname.lower()
                or "_ci." in fname.lower()
                or fname.endswith(".ci.yml")
                or fname.endswith(".ci.yaml")
                or fname == "ci.yml"
                or fname == "ci.yaml"):
                ci_docker.append(rel_str)

            if "test" in rel_str.lower() or "spec" in rel_str.lower():
                test_dirs.add(str(fpath.parent.relative_to(root)).replace(os.sep, "/"))

            if (fname in {"server.js", "app.js", "index.js", "main.go", "app.py", "main.py", "wsgi.py", "asgi.py"}
                or fname.startswith("main.")
                or (len(rel_dir.parts) <= 1 and fname.startswith("index."))
                or "cmd" in rel_dir.parts):
                entry_points.append(rel_str)

            if ext in {".js", ".ts", ".jsx", ".tsx", ".py", ".go", ".java"}:
                routes.extend(scan_routes(fpath, root))

    all_files.sort(key=lambda x: x["loc"], reverse=True)
    largest_15 = all_files[:15]
    frameworks = detect_frameworks(root, manifests)

    return {
        "root": str(root),
        "manifests": sorted(manifests),
        "frameworks": frameworks,
        "configs": sorted(configs),
        "ci_docker": sorted(ci_docker),
        "entry_points": sorted(entry_points),
        "test_dirs": sorted(list(test_dirs)),
        "languages": lang_counts,
        "loc_by_top_level": loc_by_top,
        "largest_15": largest_15,
        "routes": routes,
        "total_files": len(all_files),
        "total_loc": sum(f["loc"] for f in all_files)
    }

def print_text_summary(data):
    print("=" * 70)
    print(f"CLAUGRAVITY REPOSITORY MAP: {data['root']}")
    print(f"Total Files: {data['total_files']} | Total LOC: {data['total_loc']}")
    print("=" * 70)

    print("\n[LANGUAGES & FRAMEWORKS]")
    for lang, count in sorted(data["languages"].items(), key=lambda x: x[1], reverse=True):
        print(f"  - {lang:20}: {count:6} LOC")
    if data.get("frameworks"):
        print(f"  - Frameworks Detected : {', '.join(data['frameworks'])}")

    print("\n[LOC BY TOP-LEVEL DIRECTORY]")
    for top, count in sorted(data["loc_by_top_level"].items(), key=lambda x: x[1], reverse=True):
        print(f"  - {top:20}: {count:6} LOC")

    print("\n[MANIFESTS & CONFIGS]")
    for m in data["manifests"][:8]:
        print(f"  - Manifest: {m}")
    for c in data["configs"][:8]:
        print(f"  - Config  : {c}")

    print("\n[ENTRY POINTS & TESTS]")
    for ep in data["entry_points"][:8]:
        print(f"  - Entry Point: {ep}")
    for td in data["test_dirs"][:8]:
        print(f"  - Test Directory: {td}")

    print(f"\n[ROUTES DETECTED ({len(data['routes'])})]")
    for r in data["routes"][:15]:
        print(f"  - {r['method']:6} {r['path']:25} at {r['location']}")
    if len(data["routes"]) > 15:
        print(f"  ... and {len(data['routes']) - 15} more routes")

    print("\n[15 LARGEST SOURCE FILES]")
    for f in data["largest_15"]:
        print(f"  - {f['path']:40} : {f['loc']:5} LOC")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Map repository topology, frameworks, routes, and risk hotspots.")
    parser.add_argument("path", nargs="?", default=".", help="Root directory of the project to analyze (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--max-depth", type=int, default=6, help="Maximum directory traversal depth (default: 6)")
    args = parser.parse_args()

    data = analyze_repo(args.path, max_depth=args.max_depth)

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_text_summary(data)

if __name__ == "__main__":
    main()
