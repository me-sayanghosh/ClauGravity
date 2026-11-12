# Changelog

All notable changes to ClauGravity will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
