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

try:
    from scripts.common import (
        DEFAULT_IGNORES, LOCKFILES, BINARY_EXTENSIONS,
        load_ignore_patterns, is_ignored
    )
except ImportError:
    from common import (
        DEFAULT_IGNORES, LOCKFILES, BINARY_EXTENSIONS,
        load_ignore_patterns, is_ignored
    )

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
        "regex": re.compile(r"""\b(?:eval\s*\(|new\s+Function\s*\(|(?:child_process|cp)\.(?:exec|execSync)\s*\(|\bexecSync\s*\(|(?<!\.)\bexec\s*\(\s*`|(?<!\.)\bexec\s*\(\s*(?:["'][^"']*["']\s*\+|[^"'\`\s)]+))"""),
        "multiline_regex": re.compile(r"""\b(?:eval\s*\(|new\s+Function\s*\(|(?:child_process|cp)\.(?:exec|execSync)\s*\(\s*`[^`]*\$\{|(?<!\.)\bexec\s*\(\s*`[^`]*\$\{)""", re.DOTALL),
        "multiline_trigger": re.compile(r"""\b(?:eval|new\s+Function|(?:child_process|cp)\.(?:exec|execSync)|exec|execSync)\s*\("""),
        "languages": [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"],
        "severity_hint": "Critical",
        "explanation": "Dynamic code or shell execution with variable input allows arbitrary code execution."
    },
    {
        "id": "JS-SEC-SQL",
        "category": "Security",
        "regex": re.compile(r"""(?:query|execute)\s*\(\s*(?:`[^`]*\$\{[^}]+\}|["'][^"']*(?:SELECT|INSERT|UPDATE|DELETE)[^"']*["']\s*\+)""", re.I),
        "multiline_regex": re.compile(r"""(?:query|execute)\s*\(\s*(?:`[^`]*\$\{[^}]+\}|["'][^"']*(?:SELECT|INSERT|UPDATE|DELETE)[^"']*["']\s*\+)""", re.I | re.DOTALL),
        "multiline_trigger": re.compile(r"""\b(?:query|execute)\s*\(""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Critical",
        "explanation": "SQL query built via string interpolation or concatenation instead of parameterization."
    },
    {
        "id": "JS-SEC-NOSQL",
        "category": "Security",
        "regex": re.compile(r"""\.(?:find|findOne|findOneAndUpdate|findOneAndDelete|findOneAndReplace|countDocuments|update|updateOne|updateMany|delete|deleteOne|deleteMany)\s*\(\s*(?:\{?\s*\.{3}\s*req\.(?:body|query)|req\.(?:body|query)|{[^}]*\$where)"""),
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
        "regex": re.compile(r"""^\s*(?!(?:app|router)\.)(?:[a-zA-Z0-9_]+Async|[a-zA-Z0-9_]+Service\.[a-zA-Z0-9_]+|[a-zA-Z0-9_]+\.(?:save|update|delete|create|insert|remove|send)|save[a-zA-Z0-9_]*|write[a-zA-Z0-9_]*)\s*(?![^;\n]*\.(?:then|catch|finally))\([^;\n]*\)\s*;?\s*(?://[^\n]*)?$"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Asynchronous function called without await or .catch(), creating an unhandled floating promise."
    },
    {
        "id": "JS-CONC-RACE-CHECK-THEN-ACT",
        "category": "Concurrency",
        "regex": re.compile(r"""\b(?:[a-zA-Z0-9_.]+\.)?(?:stock|balance|quantity|inventory|count|amount|seats)\s*=\s*(?:[a-zA-Z0-9_.]+\.)?(?:stock|balance|quantity|inventory|count|amount|seats)\s*[-+]\s*[a-zA-Z0-9_.]+"""),
        "languages": [".js", ".ts", ".jsx", ".tsx", ".py"],
        "severity_hint": "High",
        "explanation": "Non-atomic read-modify-write pattern causes race conditions and oversell/double-spend under concurrent requests."
    },
    {
        "id": "JS-BUG-UNGUARDED-JSON-PARSE",
        "category": "Correctness",
        "regex": re.compile(r"""\bJSON\.parse\s*\(\s*(?:req\.|request\.|event\.|body|payload|data|raw|input|msg|content|text)"""),
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
        "regex": re.compile(r"""(?:cors\s*\(\s*\{[^}]*origin\s*:\s*(?:["']\*["']|true)|origin\s*:\s*["']\*["']|Access-Control-Allow-Origin['"]?\s*,\s*['"]\*)"""),
        "multiline_regex": re.compile(r"""cors\s*\(\s*\{[^}]*origin\s*:\s*(?:["']\*["']|true)""", re.DOTALL),
        "multiline_trigger": re.compile(r"""\bcors\s*\("""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Overly permissive CORS configuration allows arbitrary third-party origins to access responses."
    },
    {
        "id": "JS-SEC-JWT-FLAW",
        "category": "Security",
        "regex": re.compile(r"""(?:jwt\.(?:sign|verify)\s*\([^)]*(?:process\.env\.[A-Z0-9_]+\s*\|\||algorithm\s*:\s*["']none["']|["']secret["']|["']default["'])|process\.env\.(?:[A-Z0-9_]*(?:JWT|SECRET|KEY|TOKEN|AUTH)[A-Z0-9_]*)\s*\|\|\s*["'][^"']*["'])"""),
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
        "regex": re.compile(r"""(?:console\.(?:log|info|warn|error)|logger\.(?:info|debug|warn|error|fatal|trace|log))\s*\([^\n;]*(?:password|token|secret|apiKey|authorization|auth)""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Logging credentials or tokens risks leaking secrets into log aggregation systems."
    },
    {
        "id": "JS-SEC-MATH-RANDOM-TOKEN",
        "category": "Security",
        "regex": re.compile(r"""(?:Math\.random\s*\(\s*\).*?(?:token|secret|password|nonce|key|session|uuid|\bid\b)|(?:token|secret|password|nonce|key|session|uuid|\bid\b).*?Math\.random\s*\(\s*\))""", re.I),
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
        "id": "JS-PERF-LISTENER-LEAK",
        "category": "Reliability",
        "regex": re.compile(r"""\b(?:\w+\.)?(?:addListener|on)\s*\(\s*['"`](?:message|data|connection|response|close)['"`]\s*,\s*(?:async\s+)?(?:function|\([^)]*\)\s*=>)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "Registering event listeners repeatedly inside handlers or scopes without cleanup causes memory leaks."
    },
    {
        "id": "GEN-PERF-UNBOUNDED-CACHE",
        "category": "Reliability",
        "regex": re.compile(r"""(?:(?:const|let|var)\s+(?:cache|memoStore|sessionCache|userCache)\s*=\s*(?:\{\s*\}|new\s+Map\(\)))"""),
        "languages": [".js", ".ts", ".jsx", ".tsx", ".py"],
        "severity_hint": "Medium",
        "explanation": "Unbounded in-memory cache/Map without size limits or TTL eviction leads to Process Out-Of-Memory (OOM)."
    },
    {
        "id": "JS-SEC-TLS-DISABLED",
        "category": "Security",
        "regex": re.compile(r"""(?:rejectUnauthorized\s*:\s*false|NODE_TLS_REJECT_UNAUTHORIZED\s*=\s*["']?0)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Disabling TLS certificate validation exposes connections to Man-In-The-Middle (MITM) attacks."
    },
    {
        "id": "JS-SEC-PATH-TRAVERSAL",
        "category": "Security",
        "regex": re.compile(r"""(?:res\.sendFile|fs(?:\.promises)?\.(?:readFile|readFileSync|createReadStream|writeFile|writeFileSync))\s*\([^\n;]*(?:req\.|params\.|query\.)"""),
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
        "regex": re.compile(r"""(?:NEXT_PUBLIC_|VITE_)[A-Z0-9_]*(?:SECRET|PRIVATE_KEY|PASSWORD|TOKEN|AUTH_KEY)[A-Z0-9_]*\s*=""", re.I),
        "languages": [".env", ".env.local", ".env.production", ".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Critical",
        "explanation": "Exposing secret keys or passwords via frontend environment prefixes leaks credentials to clients."
    },
    {
        "id": "JS-SEC-UNGUARDED-ROUTE",
        "category": "Security",
        "regex": re.compile(r"""(?:app|router)\.(?:post|put|delete|patch)\s*\(\s*["'`][^"'`]+["'`]\s*,\s*(?:async\s+)?(?:function\s*\(|\([^)]*\)\s*=>)"""),
        "languages": [".js", ".ts"],
        "severity_hint": "Medium",
        "explanation": "State-changing HTTP route registered directly with async handler without inline auth middleware."
    },
    {
        "id": "JS-SEC-SSRF",
        "category": "Security",
        "regex": re.compile(r"""\b(?:axios(?:\.(?:get|post|put|delete|request))?|fetch|got|needle)\s*\(\s*(?:req\.(?:query|body|params)|url|targetUrl|endpoint|destination)\b""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Outbound HTTP request with user-controlled destination URL risks Server-Side Request Forgery (SSRF)."
    },
    {
        "id": "JS-SEC-OPEN-REDIRECT",
        "category": "Security",
        "regex": re.compile(r"""\bres\.redirect\s*\(\s*(?:req\.(?:query|body|params)|url|target|redirectUrl|returnTo|nextUrl)\b""", re.I),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "Medium",
        "explanation": "HTTP redirect to user-supplied URL allows open redirect phishing and token exfiltration."
    },
    {
        "id": "JS-SEC-PROTO-POLLUTION",
        "category": "Security",
        "regex": re.compile(r"""(?:Object\.assign\s*\(\s*(?:\{\s*\}|[a-zA-Z0-9_]+)\s*,\s*req\.(?:body|query)|\bmerge\s*\([^,]+,\s*req\.(?:body|query)|\[['"`]__proto__['"`]\]|\.__proto__\s*=)"""),
        "languages": [".js", ".ts", ".jsx", ".tsx"],
        "severity_hint": "High",
        "explanation": "Unchecked object assignment or prototype mutation risks Prototype Pollution and property tampering."
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
        "regex": re.compile(r"""\b(?:pickle|_pickle|cPickle)\.loads?\s*\("""),
        "languages": [".py"],
        "severity_hint": "Critical",
        "explanation": "Unpickling untrusted data leads directly to remote code execution."
    },
    {
        "id": "PY-SEC-YAML",
        "category": "Security",
        "regex": re.compile(r"""(?:yaml\.load\s*\((?:(?!Loader\s*=\s*(?:yaml\.)?SafeLoader)[^)])*\)|yaml\.unsafe_load\s*\()"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "Calling yaml.load() without SafeLoader allows arbitrary Python object instantiation."
    },
    {
        "id": "PY-SEC-SUBPROCESS-SHELL",
        "category": "Security",
        "regex": re.compile(r"""subprocess\.(?:Popen|run|call|check_call|check_output)\s*\([^\n]*\bshell\s*=\s*True"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "Executing subprocess with shell=True permits command injection via unescaped shell metacharacters."
    },
    {
        "id": "PY-SEC-SQL-FSTRING",
        "category": "Security",
        "regex": re.compile(r"""\.(?:execute|executemany|raw)\s*\(\s*f["']""", re.I),
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
        "regex": re.compile(r"""def\s+[a-zA-Z0-9_]+\s*\([^)]*=\s*(?:\[\s*\]|\{\s*\})"""),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "Mutable default arguments ([] or {}) in Python retain state across invocations."
    },
    {
        "id": "PY-SEC-DEBUG-TRUE",
        "category": "Security",
        "regex": re.compile(r"""(?:\bDEBUG\b|["']DEBUG["']\]?|\bdebug\b)\s*[:=]\s*True""", re.I),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "DEBUG mode enabled exposes detailed tracebacks and interactive debuggers."
    },
    {
        "id": "PY-CONC-GLOBAL-STATE",
        "category": "Concurrency",
        "regex": re.compile(r"""\bglobal\s+[a-zA-Z0-9_]*(?:cache|session|user|state|store|cart|order|requests)\b""", re.I),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "Mutating global state inside web request handlers causes data leaks across concurrent threads/workers."
    },
    {
        "id": "PY-RES-UNCLOSED-FILE",
        "category": "Reliability",
        "regex": re.compile(r"""^\s*[a-zA-Z0-9_]+\s*=\s*open\s*\([^)\n]+\)(?!\s*as\b)"""),
        "languages": [".py"],
        "severity_hint": "Medium",
        "explanation": "Opening file descriptor without context manager (with open(...)) risks file descriptor leakage."
    },
    {
        "id": "PY-SEC-TARFILE-TRAVERSAL",
        "category": "Security",
        "regex": re.compile(r"""\.extractall\s*\((?:(?!filter\s*=\s*['"]data['"]).)*\)"""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "Calling tarfile.extractall() without a safe filter (filter='data') enables arbitrary file overwrite via directory traversal (CVE-2007-4559)."
    },
    {
        "id": "PY-SEC-INSECURE-TEMPFILE",
        "category": "Security",
        "regex": re.compile(r"""tempfile\.mktemp\s*\("""),
        "languages": [".py"],
        "severity_hint": "High",
        "explanation": "tempfile.mktemp() creates race conditions between name generation and file creation; use tempfile.NamedTemporaryFile() instead."
    },
    {
        "id": "PY-SEC-COMMAND-FORMAT",
        "category": "Security",
        "regex": re.compile(r"""os\.(?:system|popen)\s*\(\s*(?:f['"]|['"].*?%|['"].*?\+|[a-zA-Z0-9_]+\b)"""),
        "languages": [".py"],
        "severity_hint": "Critical",
        "explanation": "Executing shell commands via os.system or os.popen with dynamic variables permits command injection."
    },

    # --- Go Rules ---
    {
        "id": "GO-CONC-LOOP-CLOSURE",
        "category": "Concurrency",
        "regex": re.compile(r"""\bgo\s+func\s*\(\s*\)\s*\{"""),
        "languages": [".go"],
        "severity_hint": "High",
        "explanation": "Goroutine closure launched without parameter passing captures outer scope variable, risking data races."
    },
    {
        "id": "GO-BUG-IGNORED-ERROR",
        "category": "Correctness",
        "regex": re.compile(r"""(?:,\s*_\s*:=|,\s*_\s*=\s*|^\s*_\s*=\s*)\s*[a-zA-Z0-9_.]+\s*\("""),
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
        "regex": re.compile(r"""exec\.(?:Command|CommandContext)\s*\((?:[^,)]*,)?\s*(?:r\.|req\.|input|cmd|name)"""),
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
        "regex": re.compile(r"""(?:executeQuery|executeUpdate|execute)\s*\(\s*["'].*?["']\s*\+"""),
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

    # --- Rust Rules ---
    {
        "id": "RUST-BUG-UNWRAP",
        "category": "Reliability",
        "regex": re.compile(r"""\.(?:unwrap|expect)\s*\("""),
        "languages": [".rs"],
        "severity_hint": "Medium",
        "explanation": "Calling .unwrap() or .expect() panics on None/Err, causing thread crash or denial of service."
    },
    {
        "id": "RUST-SEC-UNSAFE",
        "category": "Security",
        "regex": re.compile(r"""\bunsafe\s*\{"""),
        "languages": [".rs"],
        "severity_hint": "Medium",
        "explanation": "Unsafe Rust block bypasses compiler safety guarantees and requires manual invariant audit."
    },

    # --- C# / .NET Rules ---
    {
        "id": "CS-SEC-SQL-FORMAT",
        "category": "Security",
        "regex": re.compile(r"""(?:ExecuteSqlRaw|FromSqlRaw|SqlCommand)\s*\(\s*\$["']"""),
        "languages": [".cs"],
        "severity_hint": "Critical",
        "explanation": "Interpolating raw strings into SQL commands without parameterization allows SQL injection."
    },
    {
        "id": "CS-SEC-DESERIALIZATION",
        "category": "Security",
        "regex": re.compile(r"""(?:BinaryFormatter|JavaScriptSerializer|TypeNameHandling\s*=\s*TypeNameHandling\.Auto)"""),
        "languages": [".cs"],
        "severity_hint": "High",
        "explanation": "Insecure deserialization via BinaryFormatter or TypeNameHandling enables remote code execution."
    },

    # --- Generic Secrets & Cryptography ---
    {
        "id": "GEN-SEC-AWS-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded Amazon Web Services (AWS) Access Key ID detected."
    },
    {
        "id": "GEN-SEC-GITHUB-TOKEN",
        "category": "Secrets",
        "regex": re.compile(r"""\b(gh[pousr]_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82})\b"""),
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
        "id": "GEN-SEC-GOOGLE-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""\b(AIza[0-9A-Za-z-_]{32,36})\b"""),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Hard-coded Google Cloud or Firebase API key detected."
    },
    {
        "id": "GEN-SEC-OPENAI-KEY",
        "category": "Secrets",
        "regex": re.compile(r"""\b(sk-[a-zA-Z0-9_-]{20,}|sk-proj-[a-zA-Z0-9_-]{20,})\b"""),
        "languages": [],
        "severity_hint": "Critical",
        "explanation": "Hard-coded OpenAI or AI service API secret key detected."
    },
    {
        "id": "GEN-SEC-DATABASE-URI",
        "category": "Secrets",
        "regex": re.compile(r"""\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://[a-zA-Z0-9_.-]+:[^@\s/]{3,}@[a-zA-Z0-9_.-]+""", re.I),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Database connection URI containing hard-coded plaintext password."
    },
    {
        "id": "GEN-SEC-SLACK-WEBHOOK",
        "category": "Secrets",
        "regex": re.compile(r"""https://hooks\.slack\.com/services/T[0-9A-Z_]{8,}/B[0-9A-Z_]{8,}/[0-9a-zA-Z_]{20,}"""),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Hard-coded Slack incoming webhook URL with embedded authentication token."
    },
    {
        "id": "GEN-SEC-JWT-LITERAL",
        "category": "Secrets",
        "regex": re.compile(r"""\b(eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\b"""),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Hard-coded signed JSON Web Token (JWT) committed in source."
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
        "regex": re.compile(r"""(?:crypto\.createHash\s*\(\s*["'](?:md5|sha1)["']|hashlib\.(?:md5|sha1)\s*\(|MessageDigest\.getInstance\s*\(\s*["'](?:MD5|SHA-?1)["']|\b(?:md5|sha1)\.New\s*\(|(?<![a-zA-Z0-9_])(?:md5|sha1)\s*\()""", re.I),
        "languages": [],
        "severity_hint": "Medium",
        "explanation": "Use of cryptographically broken hash algorithm (MD5 or SHA1)."
    },
    {
        "id": "GEN-SEC-ECB-MODE",
        "category": "Security",
        "regex": re.compile(r"""(?:AES/ECB/|Cipher\.getInstance\s*\([^)]*ECB|modes\.ECB\s*\(|\bMODE_ECB\b)""", re.I),
        "languages": [],
        "severity_hint": "High",
        "explanation": "Electronic Codebook (ECB) cipher mode does not provide semantic security."
    },
    {
        "id": "GEN-SEC-XXE",
        "category": "Security",
        "regex": re.compile(r"""(?:resolve_entities\s*=\s*True|XMLReaderFactory|DocumentBuilderFactory\.newInstance\s*\(\s*\)|SAXParserFactory\.newInstance)"""),
        "languages": [".py", ".java", ".js", ".ts"],
        "severity_hint": "High",
        "explanation": "XML parser configured without disabling external entity resolution enables XML External Entity (XXE) attacks."
    },
    {
        "id": "GEN-SEC-REDOS-VULN",
        "category": "Security",
        "regex": re.compile(r"""(?:re\.compile|RegExp)\s*\(\s*r?['"`][^'"`]*\([^)]*[\+\*][^)]*\)[\+\*]"""),
        "languages": [".py", ".js", ".ts"],
        "severity_hint": "High",
        "explanation": "Regular expression with nested quantifiers triggers Catastrophic Backtracking and ReDoS."
    }
]

def redact_secrets(snippet, rule):
    rule_id = rule.get("id", "")
    rule_cat = rule.get("category", "")
    if rule_cat == "Secrets" or any(k in rule_id for k in ("TOKEN", "KEY", "PASSWORD", "SECRET", "CRED", "AUTH")):
        def repl(match):
            val = match.group(0)
            val_lower = val.lower().strip("\"'\t ")
            if val_lower in PLACEHOLDERS or val_lower.startswith("example"):
                return val
            if len(val) > 4:
                return val[:4] + "****"
            return "****"

        # Well-known API token patterns
        snippet = re.sub(
            r"""\b(?:(?:AKIA|ASIA)[0-9A-Z]{16}|gh[pousr]_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82}|sk_(?:live|test)_[0-9a-zA-Z]{16,}|sk-[a-zA-Z0-9_-]{16,}|xox[baprs]-[0-9a-zA-Z]{10,48}|AIza[0-9A-Za-z-_]{35}|eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})\b""",
            repl,
            snippet
        )
        # Assignment patterns: password/secret/token/apiKey = "..."
        snippet = re.sub(
            r"""((?:password|passwd|pwd|secret|token|apiKey|api_key|auth_key)["']?\s*[:=]\s*["'])([^"'\s]{6,})(["'])""",
            lambda m: m.group(1) + (m.group(2)[:4] + "****" if m.group(2).lower() not in PLACEHOLDERS and not m.group(2).lower().startswith("example") else m.group(2)) + m.group(3),
            snippet,
            flags=re.I
        )
    return snippet

def is_placeholder_secret(match, rule):
    if rule["id"] == "GEN-SEC-HARDCODED-PASSWORD":
        groups = match.groups()
        if groups:
            val = groups[0].lower().strip("\"'\t ")
            if (val in PLACEHOLDERS
                or val.startswith("example")
                or val.endswith("example")
                or val.startswith("your-")
                or val.startswith("my-")
                or set(val) == {"x"}
                or set(val) == {"0"}):
                return True
        return False
    if rule["category"] == "Secrets":
        val = match.group(0).lower().strip("\"'\t ")
        if val in PLACEHOLDERS or val.endswith("example") or "00000000" in val or "xxxxxxxx" in val:
            return True
    return False

def is_empty_catch(lines, i):
    line = lines[i]
    m = re.search(r"""\bcatch\s*(?:\([^)]*\))?\s*\{""", line)
    if not m:
        return False
    after_brace = line[m.end():].strip()
    after_clean = re.sub(r"""/\*.*?\*/""", "", after_brace).strip()
    if after_clean == "}" or re.match(r"""^(?://.*|\s*)*\}$""", after_clean):
        return True
    if after_clean and not (after_clean.startswith("//") or after_clean.startswith("/*")):
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

        def record_hit(rule, raw_text):
            clean = redact_secrets(" ".join(raw_text.strip().split())[:160], rule)
            hits.append({
                "rule_id": rule["id"],
                "category": rule["category"],
                "severity": rule["severity_hint"],
                "location": f"{rel_path}:{line_no}",
                "line_number": line_no,
                "file": rel_path,
                "line_snippet": clean,
                "explanation": rule["explanation"]
            })

        for line_no, line in enumerate(lines, start=1):
            if len(line) > 1000:
                continue
            for rule in applicable_rules:
                if rule["id"] == "JS-BUG-EMPTY-CATCH":
                    if is_empty_catch(lines, line_no - 1):
                        record_hit(rule, line)
                    continue

                if rule["id"] == "JS-REACT-STALE-CLOSURE":
                    if re.search(r"""\buseEffect\s*\(""", line):
                        has_empty_deps = any(
                            re.search(r"""\}\s*,\s*\[\s*\]\s*\)""", lines[j]) or re.search(r"""useEffect\s*\(.*?,\s*\[\s*\]\s*\)""", lines[j])
                            for j in range(line_no - 1, min(len(lines), line_no + 35))
                        )
                        if has_empty_deps:
                            record_hit(rule, line)
                    continue

                m = rule["regex"].search(line)
                if not m and "multiline_trigger" in rule and "multiline_regex" in rule:
                    if rule["multiline_trigger"].search(line):
                        window = "".join(lines[line_no - 1 : min(len(lines), line_no + 12)])
                        m = rule["multiline_regex"].search(window)

                if m and not is_placeholder_secret(m, rule):
                    record_hit(rule, line)
    except Exception:
        pass
    return hits

def generate_sarif(scan_res):
    sarif_rules = {}
    sarif_results = []

    for h in scan_res["hits"]:
        r_id = h["rule_id"]
        if r_id not in sarif_rules:
            sarif_rules[r_id] = {
                "id": r_id,
                "shortDescription": {"text": h["explanation"]},
                "properties": {
                    "category": h["category"],
                    "severity": h["severity"]
                }
            }

        level = "error" if h["severity"] in ("Critical", "High") else ("warning" if h["severity"] == "Medium" else "note")
        sarif_results.append({
            "ruleId": r_id,
            "level": level,
            "message": {"text": f"{h['explanation']} at {h['location']}"},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": h["file"]},
                    "region": {"startLine": h["line_number"]}
                }
            }]
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "ClauGravity",
                    "version": "1.1.0",
                    "rules": list(sarif_rules.values())
                }
            },
            "results": sarif_results
        }]
    }

def generate_markdown(scan_res):
    lines = [
        "# ClauGravity Risk Pattern Scan Results",
        f"**Target:** `{scan_res['target']}` | **Total Leads:** {scan_res['total_hits']} (showing top {scan_res['displayed_hits']})\n",
        "| Severity | Rule ID | Location | Summary / Hint |",
        "| :--- | :--- | :--- | :--- |"
    ]
    for h in scan_res["hits"]:
        loc_md = f"`{h['location']}`"
        lines.append(f"| **{h['severity']}** | `{h['rule_id']}` | {loc_md} | {h['explanation']} |")
    return "\n".join(lines) + "\n"

def run_scan(target_path, rules, category=None, min_severity=None, max_hits=100, max_file_bytes=2*1024*1024, include_rules=None, exclude_rules=None):
    root = Path(target_path).resolve()
    if not root.exists():
        sys.exit(f"Error: Path {root} does not exist.")

    active_rules = rules
    if include_rules:
        inc_set = set(r.strip() for r in include_rules)
        active_rules = [r for r in active_rules if r["id"] in inc_set]
    if exclude_rules:
        exc_set = set(r.strip() for r in exclude_rules)
        active_rules = [r for r in active_rules if r["id"] not in exc_set]

    patterns = load_ignore_patterns(root if root.is_dir() else root.parent)
    min_sev_score = SEVERITY_ORDER.get(min_severity, 0) if min_severity else 0

    all_hits = []

    if root.is_file():
        base_dir = Path.cwd().resolve()
        try:
            root.relative_to(base_dir)
        except ValueError:
            base_dir = root.parent
        all_hits.extend(scan_file(root, base_dir, active_rules, category, min_sev_score))
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

                hits = scan_file(fpath, root, active_rules, category, min_sev_score)
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
    parser.add_argument("--format", choices=["text", "json", "markdown", "sarif"], default="text", help="Output format (default: text)")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (Security, Concurrency, Secrets, etc.)")
    parser.add_argument("--min-severity", type=str, default=None, choices=["Critical", "High", "Medium", "Low", "Info"], help="Minimum severity")
    parser.add_argument("--max-hits", type=int, default=100, help="Maximum number of hits to display (default: 100)")
    parser.add_argument("--include-rule", type=str, default=None, help="Comma-separated rule IDs to include exclusively")
    parser.add_argument("--exclude-rule", type=str, default=None, help="Comma-separated rule IDs to exclude")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output destination file path")
    args = parser.parse_args()

    fmt = "json" if args.json else args.format
    inc_rules = [r.strip() for r in args.include_rule.split(",")] if args.include_rule else None
    exc_rules = [r.strip() for r in args.exclude_rule.split(",")] if args.exclude_rule else None

    results = run_scan(
        args.path,
        RULES,
        category=args.category,
        min_severity=args.min_severity,
        max_hits=args.max_hits,
        include_rules=inc_rules,
        exclude_rules=exc_rules
    )

    if fmt == "json":
        output_str = json.dumps(results, indent=2)
    elif fmt == "sarif":
        output_str = json.dumps(generate_sarif(results), indent=2)
    elif fmt == "markdown":
        output_str = generate_markdown(results)
    else:
        output_str = None

    if args.output:
        out_p = Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        if output_str is not None:
            out_p.write_text(output_str, encoding="utf-8")
        else:
            # Capture print_text_report
            import io
            buf = io.StringIO()
            old_stdout = sys.stdout
            try:
                sys.stdout = buf
                print_text_report(results)
            finally:
                sys.stdout = old_stdout
            out_p.write_text(buf.getvalue(), encoding="utf-8")
        if fmt not in ("json", "sarif"):
            print(f"Scan report written to {args.output}")
    else:
        if output_str is not None:
            print(output_str)
        else:
            print_text_report(results)

if __name__ == "__main__":
    main()
