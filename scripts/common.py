#!/usr/bin/env python3
"""common.py - Shared ClauGravity Core Utilities and Constants"""

import fnmatch
import os
from pathlib import Path

DEFAULT_IGNORES = {
    ".git", "node_modules", "dist", "build", ".next", "out", "coverage",
    "venv", ".venv", "__pycache__", "vendor", "target", ".idea", ".vscode",
    ".claugravity", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".DS_Store", "Thumbs.db"
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock",
    "poetry.lock", "composer.lock", "Pipfile.lock", "Gemfile.lock",
    "bun.lockb", "bun.lock", "flake.lock", "packages.lock.json", "mix.lock"
}

BINARY_EXTENSIONS = {
    # Media & fonts
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".avif", ".bmp", ".tiff", ".psd",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp4", ".mp3", ".mov", ".avi", ".webm", ".wav",
    # Archives & installers
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".zst", ".iso", ".dmg", ".deb", ".rpm", ".apk", ".ipa",
    # Documents
    ".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls",
    # Binaries, libraries, models & maps
    ".exe", ".bin", ".so", ".dylib", ".dll", ".pyc", ".class", ".jar", ".war", ".wasm", ".o", ".obj", ".a", ".lib",
    ".sqlite", ".sqlite3", ".db", ".parquet", ".arrow", ".avro", ".pt", ".pth", ".onnx", ".pkl", ".pickle", ".safetensors", ".map"
}

def load_ignore_patterns(root_dir):
    """Loads default ignores plus custom patterns from .claugravityignore."""
    patterns = set(p.rstrip("/") for p in DEFAULT_IGNORES)
    ignore_file = Path(root_dir) / ".claugravityignore"
    if ignore_file.is_file():
        try:
            with open(ignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.add(line.rstrip("/"))
                        if line.endswith("/"):
                            patterns.add(line)
        except Exception:
            pass
    return patterns

def is_ignored(path, root_dir, patterns):
    """Checks whether a given file or directory path matches any ignore pattern."""
    try:
        rel = path.relative_to(root_dir)
    except ValueError:
        return False
    parts = rel.parts
    rel_str = str(rel).replace(os.sep, "/")
    for p in parts:
        if p in patterns:
            return True
        for pat in patterns:
            clean = pat.rstrip("/")
            if p == clean or fnmatch.fnmatch(p, clean):
                return True
    for pat in patterns:
        clean = pat.rstrip("/")
        if rel_str == clean or rel_str.startswith(clean + "/"):
            return True
        if (fnmatch.fnmatch(rel_str, pat)
            or fnmatch.fnmatch(rel_str, clean)
            or fnmatch.fnmatch(rel_str, clean + "/*")
            or fnmatch.fnmatch(path.name, pat)
            or fnmatch.fnmatch(path.name, clean)):
            return True
    return False

def count_lines(file_path):
    """Counts lines in a file quickly using binary chunking."""
    try:
        with open(file_path, "rb") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0
