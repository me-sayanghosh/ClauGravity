#!/usr/bin/env python3
"""find_risk_patterns.py - ClauGravity Heuristic Risk Pattern Scanner

Scans source code for potential security flaws, concurrency hazards, and bugs.
Outputs a prioritized list of candidate LEADS for subsequent verification.

Usage:
    python scripts/find_risk_patterns.py [path] [options]

Options:
    --json                Output results in JSON format
    --category CATEGORY   Filter by category (Security, Concurrency, Secrets, etc.)
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

SEVERITY_ORDER = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Info": 0
}

PLACEHOLDERS = {
    "changeme", "your-api-key", "example", "placeholder", "secret",
    "password", "123456", "my-secret-key", "xxx", "todo", "test"
}

# Master Rule Registry
RULES = [
    # --- JavaScript / TypeScript / Node / React / Mongo ---
    {
        "id": "JS-SEC-EVAL",
        "category": "Security",
        "regex": re.compile(r"""\b(?:eval\s*\(|new\s+Function\s*\(|(?:child_process|cp)\.(?:exec|execSync)\s*\(|\bexecSync\s*\(|(?<!\.)\bexec\s*\(\s*`|(?<!\.)\bexec\s*\(\s*[^"'\`\s)]+)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
        "severity_hint": "Critical",
        "explanation": "Dynamic code or shell execution with variable input allows arbitrary code execution."
    },
    {
        "id": "JS-SEC-SQL",
        "category": "Security",
        "regex": re.compile(r"""(?:query|execute)\s*\(\s*(?:`[^`]*\$\{[^}]+\}|["'][^"']*(?:SELECT|INSERT|UPDATE|DELETE)[^"']*["']\s*\+)""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Critical",
        "explanation": "SQL query built via string interpolation or concatenation instead of parameterization."
    },
    {
        "id": "JS-SEC-NOSQL",
        "category": "Security",
        "regex": re.compile(r"""\.(?:find|findOne|update|updateOne|updateMany|delete|deleteOne|deleteMany)\s*\(\s*(?:\{?\s*\.{3}\s*req\.(?:body|query)|req\.(?:body|query)|{[^}]*\$where)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Passing unvalidated request body/query directly to MongoDB queries or using $where."
    },
    {
        "id": "JS-SEC-XSS",
        "category": "Security",
        "regex": re.compile(r"""(?:dangerouslySetInnerHTML|innerHTML\s*=)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Direct insertion of unescaped HTML into the DOM risks Cross-Site Scripting (XSS)."
    },
    {
        "id": "JS-CONC-FOREACH-ASYNC",
        "category": "Concurrency",
        "regex": re.compile(r"""\.forEach\s*\(\s*async\b"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Array.forEach with an async callback does not await promises, causing out-of-order execution."
    },
    {
        "id": "JS-CONC-FLOATING-PROMISE",
        "category": "Concurrency",
        "regex": re.compile(r"""^\s*(?:[a-zA-Z0-9_]+Async|[a-zA-Z0-9_]+Service\.[a-zA-Z0-9_]+|[a-zA-Z0-9_]+\.(?:save|update|delete|create|insert|remove|send)|save[a-zA-Z0-9_]*|write[a-zA-Z0-9_]*)\s*\([^)]*\)\s*;?\s*(?://.*)?$"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Asynchronous function called without await or .catch(), creating an unhandled floating promise."
    },
    {
        "id": "JS-BUG-UNGUARDED-JSON-PARSE",
        "category": "Correctness",
        "regex": re.compile(r"""\bJSON\.parse\s*\(\s*(?:req\.|body|payload|data|raw|input|msg)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "JSON.parse on external input without try/catch wrapper causes uncaught exception and crash."
    },
    {
        "id": "JS-BUG-LOOSE-EQUALITY",
        "category": "Correctness",
        "regex": re.compile(r"""(?<![!=])==(?!=)|(?<![!=])!=(?!=)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Low",
        "explanation": "Loose equality (== or !=) permits unexpected type coercion; prefer strict === or !==."
    },
    {
        "id": "JS-SEC-DYNAMIC-REGEX",
        "category": "Security",
        "regex": re.compile(r"""new\s+RegExp\s*\(\s*(?:req\.|params\.|query\.|input|pattern|val)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Instantiating RegExp with user-controlled input can enable Regular Expression Denial of Service (ReDoS)."
    },
    {
        "id": "JS-SEC-CORS-PERMISSIVE",
        "category": "Security",
        "regex": re.compile(r"""(?:cors\s*\(\s*\{[^}]*origin\s*:\s*(?:["']\*["']|true)|origin\s*:\s*["']\*["'])"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Overly permissive CORS configuration allows arbitrary third-party origins to access responses."
    },
    {
        "id": "JS-SEC-JWT-FLAW",
        "category": "Security",
        "regex": re.compile(r"""(?:jwt\.sign\s*\([^)]*(?:process\.env\.[A-Z0-9_]+\s*\|\||algorithm\s*:\s*["']none["']|["']secret["']|["']default["'])|process\.env\.(?:[A-Z0-9_]*(?:JWT|SECRET|KEY|TOKEN|AUTH)[A-Z0-9_]*)\s*\|\|\s*["'][^"']*["'])"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "JWT signed with fallback default secret or insecure default value in source."
    },
    {
        "id": "JS-BUG-EMPTY-CATCH",
        "category": "Correctness",
        "regex": re.compile(r"""\bcatch\s*(?:\([^)]*\))?\s*\{\s*(?://[^\n]*)?\}"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Empty or comment-only catch block silently swallows exceptions, obscuring critical runtime errors."
    },
    {
        "id": "JS-BUG-FLOAT-MONEY",
        "category": "Correctness",
        "regex": re.compile(r"""(?:==|===)\s*0\.0\b|\b0\.0\s*(?:==|===)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Direct floating-point equality check with 0.0 risks precision failure in financial calculations."
    },
    {
        "id": "JS-SEC-LOG-SECRETS",
        "category": "Security",
        "regex": re.compile(r"""(?:console\.(?:log|info|warn|error)|logger\.(?:info|debug|error))\s*\([^)]*(?:password|token|secret|apiKey|authorization)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Logging credentials or tokens risks leaking secrets into log aggregation systems."
    },
    {
        "id": "JS-SEC-MATH-RANDOM-TOKEN",
        "category": "Security",
        "regex": re.compile(r"""(?:Math\.random\s*\(\s*\).*?(?:token|secret|password|nonce|key|session)|(?:token|secret|password|nonce|key|session).*?Math\.random\s*\(\s*\))""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Math.random() is pseudo-random and predictable; use crypto.randomBytes() for tokens."
    },
    {
        "id": "JS-DATA-UNBOUNDED-FIND",
        "category": "Data/API",
        "regex": re.compile(r"""\.(?:find|findAll)\s*\(\s*(?:\{\s*\}|\s*)\)(?!\s*\.(?:limit|count|select\(["']_id))"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Database find() without explicit limit risks high memory consumption on large collections."
    },
    {
        "id": "JS-SEC-TLS-DISABLED",
        "category": "Security",
        "regex": re.compile(r"""rejectUnauthorized\s*:\s*false"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Disabling TLS certificate validation exposes connections to Man-In-The-Middle (MITM) attacks."
    },
    {
        "id": "JS-SEC-PATH-TRAVERSAL",
        "category": "Security",
        "regex": re.compile(r"""(?:res\.sendFile|fs\.(?:readFile|createReadStream))\s*\([^)]*(?:req\.|params\.|query\.)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Filesystem operation with user-supplied parameter risks directory path traversal."
    },
    {
        "id": "JS-REACT-STALE-CLOSURE",
        "category": "Correctness",
        "regex": re.compile(r"""useEffect\s*\(.*?,\s*\[\s*\]\)"""),
        "languages": [".jsx", ".tsx", ".js", ".ts"],
        "severity_hint": "Low",
        "explanation": "Empty dependency array in useEffect referencing props/state can create stale closures."
    },
    {
        "id": "JS-SEC-CLIENT-SECRET-LEAK",
        "category": "Secrets",
        "regex": re.compile(r"""(?:NEXT_PUBLIC_|VITE_)[A-Z0-9_]*(?:SECRET|PRIVATE_KEY|PASSWORD)\s*="""),
        "languages": [".env", ".env.local", ".env.production", ".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Critical",
        "explanation": "Exposing secret keys or passwords via frontend environment prefixes leaks credentials to clients."
    },
    {
        "id": "JS-SEC-UNGUARDED-ROUTE",
        "category": "Security",
        "regex": re.compile(r"""(?:app|router)\.(?:post|put|delete|patch)\s*\(\s*["'`][^"'`]+["'`]\s*,\s*async\s*\("""),
        "languages": [".js", ".ts"],
        "severity_hint": "Medium",
        "explanation": "State-changing HTTP route registered directly with async handler without inline auth middleware."
    },

    # --- Python Rules ---
    {
        "id": "PY-SEC-EVAL-EXEC",
        "category": "Security",
        "regex": re.compile(r"""\b(?:eval|exec)\s*\("""),
        "languages": [".py"],
        "severity_hint": "Critical",
        "explanation": "Python eval() or exec() allows execution of arbitrary code."
    },
    {
        "id": "PY-SEC-PICKLE",
        "category": "Security",
        "regex": re.compile(r"""\bpickle\.loads?\s*\("""),
        "languages": [".py"],
        "severity_hint": "Critical",
        "explanation": "Unpickling untrusted data leads directly to remote code execution."
    },
    {
        "id": "PY-SEC-YAML",
        "category": "Security",
        "regex": re.compile(r"""yaml\.load\s*\((?:(?!Loader\s*=\s*(?:yaml\.)?SafeLoader)[^)])*\)"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "Calling yaml.load() without SafeLoader allows arbitrary Python object instantiation."
    },
    {
        "id": "PY-SEC-SUBPROCESS-SHELL",
        "category": "Security",
        "regex": re.compile(r"""subprocess\.(?:Popen|run|call|check_call|check_output)\s*\([^)]*shell\s*=\s*True"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "Executing subprocess with shell=True permits command injection via unescaped shell metacharacters."
    },
    {
        "id": "PY-SEC-SQL-FSTRING",
        "category": "Security",
        "regex": re.compile(r"""\.(?:execute|raw)\s*\(\s*f["']"""),
        "languages": [".py"],
        "severity_hint": "Critical",
        "explanation": "SQL query formatted via Python f-string directly introduces SQL injection."
    },
    {
        "id": "PY-SEC-SSL-DISABLED",
        "category": "Security",
        "regex": re.compile(r"""verify\s*=\s*False"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "HTTP client TLS certificate verification disabled (verify=False)."
    },
    {
        "id": "PY-BUG-BARE-EXCEPT",
        "category": "Correctness",
        "regex": re.compile(r"""except\s*:"""),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "Bare except catches system exit and KeyboardInterrupt, concealing fatal defects."
    },
    {
        "id": "PY-BUG-MUTABLE-DEFAULT",
        "category": "Correctness",
        "regex": re.compile(r"""def\s+[a-zA-Z0-9_]+\s*\([^)]*=\s*(?:\[\]|\{\})"""),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "Mutable default arguments ([] or {}) in Python retain state across invocations."
    },
    {
        "id": "PY-SEC-DEBUG-TRUE",
        "category": "Security",
        "regex": re.compile(r"""DEBUG\s*=\s*True"""),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "DEBUG mode enabled exposes detailed tracebacks and interactive debuggers."
    },

    # --- Go Rules ---
    {
        "id": "GO-BUG-IGNORED-ERROR",
        "category": "Correctness",
        "regex": re.compile(r"""(?:,\s*_\s*:=|,\s*_\s*=\s*)\s*[a-zA-Z0-9_.]+\s*\("""),
        "languages": [".go"],
        "severity_hint": "Medium",
        "explanation": "Explicitly ignoring return error with blank identifier (_) masks failures."
    },
    {
        "id": "GO-SEC-TLS-DISABLED",
        "category": "Security",
        "regex": re.compile(r"""InsecureSkipVerify\s*:\s*true"""),
        "languages": [".go"],
        "severity_hint": "High",
        "explanation": "InsecureSkipVerify: true disables TLS certificate validation in Go."
    },
    {
        "id": "GO-SEC-EXEC-CMD",
        "category": "Security",
        "regex": re.compile(r"""exec\.Command\s*\(\s*(?:r\.|req\.|input|cmd|name)"""),
        "languages": [".go"],
        "severity_hint": "High",
        "explanation": "Spawning system command from variable or user request enables command injection."
    },
    {
        "id": "GO-SEC-SQL-FORMAT",
        "category": "Security",
        "regex": re.compile(r"""(?:Query|QueryContext|Exec|ExecContext|QueryRow|QueryRowContext)\s*\([^)]*fmt\.Sprintf\s*\("""),
        "languages": [".go"],
        "severity_hint": "Critical",
        "explanation": "SQL query constructed via fmt.Sprintf instead of prepared statements."
    },

    # --- Java Rules ---
    {
        "id": "JAVA-SEC-SQL-CONCAT",
        "category": "Security",
        "regex": re.compile(r"""(?:executeQuery|executeUpdate)\s*\(\s*["'].*?["']\s*\+"""),
        "languages": [".java"],
        "severity_hint": "Critical",
        "explanation": "Building SQL queries by concatenating strings instead of using PreparedStatement."
    },
    {
        "id": "JAVA-SEC-OBJECT-INPUT",
        "category": "Security",
        "regex": re.compile(r"""new\s+ObjectInputStream\s*\("""),
        "languages": [".java"],
        "severity_hint": "High",
        "explanation": "Java ObjectInputStream deserializes arbitrary object graphs, causing RCE."
    },
    {
        "id": "JAVA-SEC-RUNTIME-EXEC",
        "category": "Security",
        "regex": re.compile(r"""Runtime\.getRuntime\s*\(\s*\)\.exec\s*\("""),
        "languages": [".java"],
        "severity_hint": "High",
        "explanation": "Direct shell execution via Runtime.getRuntime().exec() with untrusted arguments."
    },
    {
        "id": "JAVA-BUG-PRINT-STACK-TRACE",
        "category": "Correctness",
        "regex": re.compile(r"""\.printStackTrace\s*\(\s*\)"""),
        "languages": [".java"],
        "severity_hint": "Low",
        "explanation": "Printing stack traces directly to stdout rather than using structured logging."
    },

    # --- Generic Secrets & Cryptography ---
    {
        "id": "GEN-SEC-AWS-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""\b(AKIA[0-9A-Z]{16})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded Amazon Web Services (AWS) Access Key ID detected."
    },
    {
        "id": "GEN-SEC-GITHUB-TOKEN",
        "category": "Secrets",
        "regex": re.compile(r"""\b(gh[pousr]_[0-9a-zA-Z]{36})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded GitHub personal access or OAuth token detected."
    },
    {
        "id": "GEN-SEC-STRIPE-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""\b(sk_live_[0-9a-zA-Z]{24,})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded Stripe live API secret key detected."
    },
    {
        "id": "GEN-SEC-SLACK-TOKEN",
        "category": "Secrets",
        "regex": re.compile(r"""\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded Slack Bot or User token detected."
    },
    {
        "id": "GEN-SEC-PRIVATE-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Cryptographic private key header committed in plaintext."
    },
    {
        "id": "GEN-SEC-HARDCODED-PASSWORD",
        "category": "Secrets",
        "regex": re.compile(r"""(?:password|passwd|pwd|secret)["']?\s*[:=]\s*["']([^"'\s]{6,})["']""", re.I),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Plaintext password or secret credential literal assigned in source."
    },
    {
        "id": "GEN-BUG-TODO-COMMENT",
        "category": "Correctness",
        "regex": re.compile(r"""(?://|#|/\*)\s*(?:TODO|FIXME|HACK|XXX)\b"""),
        "languages": [],
        "severity_hint": "Info",
        "explanation": "Developer reminder or unfinished work marker (TODO/FIXME)."
    },
    {
        "id": "GEN-SEC-WEAK-HASH",
        "category": "Security",
        "regex": re.compile(r"""(?:crypto\.createHash\s*\(\s*["'](?:md5|sha1)["']|hashlib\.(?:md5|sha1)\s*\()"""),
        "languages": [],
        "severity_hint": "Medium",
        "explanation": "Use of cryptographically broken hash algorithm (MD5 or SHA1)."
    },
    {
        "id": "GEN-SEC-ECB-MODE",
        "category": "Security",
        "regex": re.compile(r"""(?:AES/ECB/|Cipher\.getInstance\s*\([^)]*ECB)"""),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Electronic Codebook (ECB) cipher mode does not provide semantic security."
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

def redact_secrets(snippet, rule):
    if rule["category"] == "Secrets" or "TOKEN" in rule["id"] or "KEY" in rule["id"] or "PASSWORD" in rule["id"]:
        def repl(match):
            val = match.group(0)
            val_lower = val.lower().strip("\"'\t ")
            if val_lower in PLACEHOLDERS or val_lower.startswith("example"):
                return val
            if len(val) > 4:
                return val[:4] + "****"
            return "****"

        snippet = re.sub(r"""\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[0-9a-zA-Z]{36}|sk_live_[0-9a-zA-Z]{24,}|xox[baprs]-[0-9a-zA-Z]{10,48})\b""", repl, snippet)
        snippet = re.sub(r"""((?:password|passwd|pwd|secret)["']?\s*[:=]\s*["'])([^"'\s]{6,})(["'])""",
                         lambda m: m.group(1) + (m.group(2)[:4] + "****" if m.group(2).lower() not in PLACEHOLDERS and not m.group(2).lower().startswith("example") else m.group(2)) + m.group(3),
                         snippet, flags=re.I)
    return snippet

def is_placeholder_secret(match, rule):
    if rule["id"] == "GEN-SEC-HARDCODED-PASSWORD":
        groups = match.groups()
        if groups:
            val = groups[0].lower().strip("\"'\t ")
            if val in PLACEHOLDERS or val.startswith("example"):
                return True
        return False
    if rule["category"] == "Secrets":
        val = match.group(0).lower()
        if any(ph in val for ph in PLACEHOLDERS) or "example" in val:
            return True
    return False

def is_empty_catch(lines, i):
    line = lines[i]
    m = re.search(r"""\bcatch\s*(?:\([^)]*\))?\s*\{""", line)
    if not m:
        return False
    after_brace = line[m.end():].strip()
    if after_brace == "}" or re.match(r"""^(?://.*|/\*.*?\*/|\s*)*\}$""", after_brace):
        return True
    if after_brace and not after_brace.startswith("//"):
        return False
    for j in range(i + 1, min(len(lines), i + 20)):
        sub = lines[j].strip()
        if not sub or sub.startswith("//") or sub.startswith("*") or sub.startswith("/*"):
            continue
        if sub == "}" or sub.startswith("}"):
            return True
        return False
    return False

def scan_file(file_path, root_dir, rules, category_filter=None, min_sev_score=0):
    hits = []
    ext = file_path.suffix.lower()
    applicable_rules = [
        r for r in rules
        if (not r.get("languages") or ext in r["languages"] or file_path.name.startswith(".env"))
        and (not category_filter or r["category"].lower() == category_filter.lower())
        and SEVERITY_ORDER.get(r["severity_hint"], 0) >= min_sev_score
    ]

    if not applicable_rules:
        return hits

    try:
        rel_path = str(file_path.relative_to(root_dir)).replace(os.sep, "/")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        for line_no, line in enumerate(lines, start=1):
            if len(line) > 1000:
                continue
            for rule in applicable_rules:
                if rule["id"] == "JS-BUG-EMPTY-CATCH":
                    if not is_empty_catch(lines, line_no - 1):
                        continue
                    clean_line = redact_secrets(line.strip()[:160], rule)
                    hits.append({
                        "rule_id": rule["id"],
                        "category": rule["category"],
                        "severity": rule["severity_hint"],
                        "location": f"{rel_path}:{line_no}",
                        "line_number": line_no,
                        "file": rel_path,
                        "line_snippet": clean_line,
                        "explanation": rule["explanation"]
                    })
                    continue

                if rule["id"] == "JS-REACT-STALE-CLOSURE":
                    if not re.search(r"""\buseEffect\s*\(""", line):
                        continue
                    has_empty_deps = False
                    for j in range(line_no - 1, min(len(lines), line_no + 35)):
                        if re.search(r"""\}\s*,\s*\[\s*\]\s*\)""", lines[j]) or re.search(r"""useEffect\s*\(.*?,\s*\[\s*\]\s*\)""", lines[j]):
                            has_empty_deps = True
                            break
                    if not has_empty_deps:
                        continue
                    clean_line = redact_secrets(line.strip()[:160], rule)
                    hits.append({
                        "rule_id": rule["id"],
                        "category": rule["category"],
                        "severity": rule["severity_hint"],
                        "location": f"{rel_path}:{line_no}",
                        "line_number": line_no,
                        "file": rel_path,
                        "line_snippet": clean_line,
                        "explanation": rule["explanation"]
                    })
                    continue

                m = rule["regex"].search(line)
                if m:
                    if is_placeholder_secret(m, rule):
                        continue
                    clean_line = redact_secrets(line.strip()[:160], rule)
                    hits.append({
                        "rule_id": rule["id"],
                        "category": rule["category"],
                        "severity": rule["severity_hint"],
                        "location": f"{rel_path}:{line_no}",
                        "line_number": line_no,
                        "file": rel_path,
                        "line_snippet": clean_line,
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
    parser.add_argument("--category", type=str, default=None, help="Filter by category (Security, Concurrency, Secrets, etc.)")
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
