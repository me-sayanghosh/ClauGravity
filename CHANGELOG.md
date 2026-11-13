# Changelog

All notable changes to ClauGravity will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-13

### Added
- **Automated Pull Request & Diff Reviewer (`scripts/diff_audit.py`)**: Hunk-aware diff analysis filtering risk findings strictly to touched lines with automated PR verdict scoring (`BLOCK`, `FIX BEFORE MERGE`, `OK WITH NITS`, `APPROVE`).
- **Audit Report Scaffolder & Assembler (`scripts/generate_report.py`)**: Automatic generation of compliant `.claugravity/report.md` reports with auto-populated topology, linter checks, and structured finding sections.
- **SARIF v2.1.0 & Markdown Export**: Added `--format` (`sarif`, `markdown`, `json`, `text`) and `--output` options across all analysis scripts for seamless CI/CD and GitHub Security integration.
- **Multiline Sliding Window Scanning**: Extended `find_risk_patterns.py` to detect multiline SQL template string injections, multiline command execution, and multiline CORS flaws.
- **New Web & Cloud Security Rules**: Added detection for SSRF, open redirect, prototype pollution, XXE (XML External Entity), Google Cloud API keys, OpenAI/Anthropic API keys, database connection URIs, Slack webhooks, and hardcoded JWT literals.
- **New Concurrency & Reliability Rules**: Added detection for Go loop closure capture, non-atomic read-modify-write race conditions, unbounded in-memory caches, listener leaks, and regular expression ReDoS vulnerabilities.
- **Language-Specific Audit Rules**: Added Python `tarfile.extractall` traversal (CVE-2007-4559), `tempfile.mktemp`, `os.system` formatting; Rust `.unwrap()` / `unsafe`; C# SQL formatting and insecure deserialization.
- **Monorepo Partitioning**: `scripts/chunk_plan.py` now partitions monorepos across `packages/*`, `apps/*`, `services/*`, and `modules/*`.
- **Package Manager Auto-Detection**: `scripts/run_checks.py` automatically detects and uses `bun`, `pnpm`, `yarn`, or `npm`.
- **Python Test Fallback**: Added standard library `python -m unittest` fallback in `scripts/run_checks.py` when `pytest` is not installed.
- **Citation Offset Diagnostics**: `scripts/verify_citations.py` provides exact candidate line guidance when citation line numbers have shifted.

### Fixed
- **Secret Redaction Bug**: Fixed pattern matching bug in `find_risk_patterns.py` where rules with `SECRET` in their ID were skipped from redaction.
- **Ignore Pattern Trailing Slashes**: Normalized `.claugravityignore` directory patterns ending in trailing slashes (`dist/`, `build/`) across all scripts.
- **Binary & Media Asset Filtering**: Expanded binary extension and lockfile skip lists to prevent scanning models, parquet files, audio/video, and source maps (`.map`).
- **Route & Framework Detection**: Expanded route mapping for Rust (Axum, Actix), Go 1.22+ stdlib, ASP.NET Core, PHP Laravel, and Rails; fixed manifest framework parsing order.

### Changed
- Expanded automated test suite from 43 to 64 tests covering CLI execution, multiline scans, monorepos, and all new security rules.

## [1.0.0] - 2026-11-12

### Added
- Initial release of ClauGravity v1.0.0.
- Autonomous codebase auditing and risk pattern detection engine (`scripts/find_risk_patterns.py`).
- Multi-language security and concurrency review references across JS/TS, Python, Go, Java, C#, PHP, Ruby, and Rust.
- Safe local check runner (`scripts/run_checks.py`) and chunk planner (`scripts/chunk_plan.py`) for scalable code analysis.
- Mechanical citation verification gate (`scripts/verify_citations.py`) ensuring zero hallucinated line citations.
- Six operational modes: FULL, MODULE, DIFF, HUNT, SECURITY, and QUICK.
- Bundled test fixture project with 12 planted defects and 3 deceptive decoys.
- Verified sample audit reports and pull request reviews in `examples/`.
