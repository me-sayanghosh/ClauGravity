# ClauGravity
*Audit smarter. Find real bugs faster.*

[![Version](https://img.shields.io/badge/version-1.1.1-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests: 64 passed](https://img.shields.io/badge/tests-64%20passed-brightgreen.svg)](tests/test_scripts.py)
[![Verification: 100%](https://img.shields.io/badge/citations-100%25%20verified-success.svg)](tests/RESULTS.md)

**ClauGravity** is a production-grade Agent Skill for AI coding agents that transforms AI assistants into rigorous software auditors, security researchers, and bug hunters. Designed for professional engineering environments, ClauGravity audits repositories and pull requests to discover exploitable vulnerabilities, concurrency race conditions, data persistence defects, and subtle logic errors while aggressively eliminating false alarms.

Rather than inundating developers with speculative or superficial lint warnings, ClauGravity enforces empirical evidence requirements: every confirmed finding is accompanied by a concrete trigger scenario, root-cause explanation, verified source citations, and minimal remediation diffs. By coupling static pattern screening with a rigorous second-pass falsification process, ClauGravity ensures high-signal audit reports that engineering teams can immediately trust and act upon.

---

## Key Capabilities

- **Automated Pull Request & Diff Reviewing (`scripts/diff_audit.py`)**: Hunk-aware diff analysis that maps touched lines and filters findings strictly to modified code with automated PR verdict scoring (`BLOCK`, `FIX BEFORE MERGE`, `OK WITH NITS`, `APPROVE`).
- **Mechanical Citation Verification Gate (`scripts/verify_citations.py`)**: Validates that all cited file paths, line ranges, and code excerpts exist verbatim in the target repository before report delivery, preventing hallucinated bugs.
- **Automated Report Scaffolding (`scripts/generate_report.py`)**: Automatically assembles topology analysis, native check outputs, and structured findings into compliant `.claugravity/report.md` reports.
- **SARIF v2.1.0 & Markdown Export**: Native export options (`--format sarif|markdown|json|text`) across analysis tools for direct integration into GitHub Actions, GitHub Code Scanning, and CI/CD pipelines.
- **Multiline Sliding Window Scanning**: Heuristic pattern scanner (`scripts/find_risk_patterns.py`) catches multiline template string injections, multiline command executions, and multiline CORS flaws.
- **Comprehensive Multi-Language Rule Catalog**: Out-of-the-box detection for SSRF, open redirect, prototype pollution, XXE, ReDoS, Zip Slip, and cloud credentials (Google Cloud, OpenAI, Anthropic, database URIs, webhooks, JWTs) across JavaScript/TypeScript, Python, Go, Java, C#, Rust, PHP, and Ruby.
- **Safe Native Tooling Runner (`scripts/run_checks.py`)**: Auto-detects package managers (`bun`, `pnpm`, `yarn`, `npm`) and test runners (`pytest`, standard library `unittest`) to run available linters and typecheckers safely without modifying project state.
- **Monorepo & Scalable Chunk Planning (`scripts/chunk_plan.py`)**: Partitions large repositories (>50k LOC) and monorepos (`packages/*`, `apps/*`, `services/*`, `modules/*`) into risk-ranked review modules to conserve LLM context.
- **Modular & DRY Core Architecture (`scripts/common.py`)**: Fast binary line counting, consolidated ignore pattern evaluation, and zero external runtime dependencies (Python 3.8+ standard library only).

---

## Why ClauGravity Works

### 1. Two-Pass Auditing & Falsification Gate
Traditional AI code reviews suffer from confirmation bias and hallucinated defects. ClauGravity enforces a mandatory two-pass protocol:
- **Pass 1 (FIND)**: Fast topological mapping and pattern screening gather candidate leads.
- **Pass 2 (DISPROVE)**: The auditor actively attempts to prove each candidate is *not* a bug by validating caller constraints, framework sanitizers, ORM bindings, router-level guards, and unit test suites. Only survivors are promoted to confirmed findings.

### 2. Mechanical Citation Verification Gate
Every reported finding must cite exact file lines and verbatim code excerpts. Before any report is delivered, `scripts/verify_citations.py` validates that all cited excerpts exist line-by-line in the target repository. If citation drift is detected, the verifier provides exact line candidate guidance. If a citation fails verification, the finding is automatically blocked from the report.

### 3. Risk-Ordered Review Hierarchy
Auditors prioritize review depth according to empirical failure impact:
1. Authentication, Authorization & Session Management (RBAC, OAuth, JWT, session hijacking)
2. Payments, Billing & Financial Invariants (currency precision, balance updates, webhooks)
3. Data Persistence, State Mutations & Schema Migrations (data loss, race conditions)
4. Untrusted Ingress & External Input Handlers (SQL/NoSQL injection, SSRF, command injection)
5. Cryptography, Secrets & Environment Configurations (hardcoded tokens, ECB mode, weak keys)
6. Background Workers, Schedulers & Queues (idempotency, deadlocks, task duplication)
7. Concurrency, Shared State & Mutexes (goroutine leaks, atomic counters, stale closures)
8. Auxiliary Logic & Formatting

### 4. Read-Only Safety Posture
ClauGravity operates under a strict read-only mandate. It never modifies, deletes, or reformats user project source code. All working notes, intermediate candidate logs, and reports are written exclusively to `.claugravity/` inside the target workspace.

---

## Operational Modes

Select the operational mode corresponding to your objective:

| Mode | Purpose | Primary Triggers & Prompts | Output Artifact |
| :--- | :--- | :--- | :--- |
| **FULL** | Comprehensive whole-repo audit | *"Use ClauGravity to audit this repo"*, *"Pre-release codebase health check"* | `.claugravity/report.md` |
| **MODULE** | Targeted directory or feature review | *"ClauGravity audit src/routes/orders.js"*, *"Review the auth service"* | `.claugravity/module-report.md` |
| **DIFF** | Pull request and uncommitted changes | *"Use ClauGravity to review my uncommitted changes"*, *"Review PR #42"* | `.claugravity/diff-review.md` |
| **HUNT** | Symptom-specific bug & crash diagnosis | *"Why does /checkout intermittently return 500?"*, *"Debug stock overselling"* | Ranked Hypotheses & Fix Diff |
| **SECURITY** | Dedicated OWASP vulnerability review | *"ClauGravity security review of the auth module"*, *"Hunt for vulnerabilities"* | CWE/OWASP Cited Report |
| **QUICK** | Rapid 10-minute risk triage | *"ClauGravity quick triage"*, *"Fast risk assessment"* | Executive Briefing |

---

## Repository Layout

```
ClauGravity/
├── .claude-plugin/                   # Claude Code plugin & marketplace manifests
│   ├── marketplace.json              # Claude Code marketplace catalog
│   └── plugin.json                   # Claude Code plugin manifest
├── plugin.json                       # Antigravity plugin manifest
├── SKILL.md                          # Root skill definition & agent instructions
├── README.md                         # Complete project documentation & guide
├── LICENSE                           # MIT License
├── CHANGELOG.md                      # Semantic versioning changelog
├── CONTRIBUTING.md                   # Developer contribution guidelines
├── .gitignore                        # Global repository ignore rules
├── references/                       # Focused, code-level auditing guides
│   ├── audit-workflow.md             # The 7-phase audit methodology & modes
│   ├── severity-and-confidence.md    # Scoring rubric & worked examples
│   ├── general-bug-patterns.md       # 22 common language-agnostic defects
│   ├── security-checklist.md         # 17 OWASP-aligned vulnerability patterns
│   ├── concurrency-and-async.md      # 16 race condition & async hazards
│   ├── data-and-api.md               # 15 database, migration & API pitfalls
│   ├── js-ts-node-react.md           # 43 JavaScript, TypeScript & React checks
│   ├── python.md                     # 15 Python, Django & FastAPI patterns
│   ├── other-languages.md            # Top 10 pitfalls for Go, Java, C#, PHP, Ruby, Rust
│   ├── false-positive-filters.md     # 8-point disproof checklist & 15 examples
│   └── large-repo-strategy.md        # Monorepo chunking & token efficiency guidelines
├── scripts/                          # Portable Python 3.8+ standard library utilities
│   ├── common.py                     # Shared core utilities, ignore matching & line counting
│   ├── map_repo.py                   # Repository topology, modern routes & entry point mapper
│   ├── find_risk_patterns.py         # Multi-language heuristic scanner (SARIF, multiline, rules)
│   ├── run_checks.py                 # Safe native linter, package manager & typecheck runner
│   ├── chunk_plan.py                 # Risk-weighted review module planner & monorepo partitioner
│   ├── diff_audit.py                 # Automated PR and git diff reviewer with verdict scoring
│   ├── generate_report.py            # Scaffold compliant, verifiable audit reports
│   └── verify_citations.py           # Mechanical citation verification gate with diagnostics
├── templates/                        # Standardized report & review structures
│   ├── finding.md                    # Structured defect template
│   ├── audit-report.md               # Full audit report template
│   └── pr-review.md                  # Pull request review template
├── examples/                         # Verified completed outputs
│   ├── sample-report.md              # Complete sample audit report (6 findings)
│   └── sample-pr-review.md           # Complete sample pull request review
└── tests/                            # Validation suite & fixture project
    ├── test_scripts.py               # Automated unit & CLI subprocess test suite (64 tests)
    ├── RESULTS.md                    # Empirical scorecard & test history
    ├── fixture-report-iteration-1.md # Full 12-finding fixture audit report
    ├── fixture-report-iteration-2.md # Iteration 2 verified audit report
    └── fixture-project/              # Intentionally vulnerable test project
        ├── PLANTED_BUGS.md           # Answer key for 12 bugs & 3 decoys
        ├── .claugravityignore        # Ignore rules excluding answer key
        ├── package.json              # Sample dependency manifest
        ├── src/                      # Express, Mongoose & auth handlers
        └── client/                   # React frontend components
```

---

## Installation

ClauGravity can be installed across both **Claude Code** and **Google Antigravity**.

### Option 1: Claude Code (Plugin Marketplace)
You can install ClauGravity directly inside Claude Code using its native plugin marketplace commands:

```bash
# 1. Register the ClauGravity marketplace catalog
/plugin marketplace add me-sayanghosh/ClauGravity

# 2. Install the ClauGravity plugin
/plugin install claugravity@ClauGravity
```

### Option 2: Google Antigravity (Workspace / Per-Project)
Install ClauGravity inside a specific project repository. You can commit `.agents/skills/claugravity` to Git so your entire team has it automatically:

```bash
cd /path/to/your-project
mkdir -p .agents/skills
git clone https://github.com/me-sayanghosh/ClauGravity.git .agents/skills/claugravity
```
*Note:* The destination folder must be lowercase `claugravity`, matching the skill name defined in `SKILL.md`. The path `.agent/skills/claugravity` is also supported.

### Option 3: Google Antigravity (Global / All Projects)
To make ClauGravity available globally across all workspaces on your workstation:

```bash
mkdir -p ~/.gemini/config/skills
git clone https://github.com/me-sayanghosh/ClauGravity.git ~/.gemini/config/skills/claugravity
```

---

## Example Usage Prompts

Invoke ClauGravity directly within conversational agent sessions:
- **Full Audit:** *"Use ClauGravity to audit this repo."*
- **Pull Request Review:** *"Use ClauGravity to review my uncommitted changes against main."*
- **Symptom Hunting:** *"ClauGravity: why does /checkout intermittently return 500 under load?"*
- **Targeted Security Audit:** *"ClauGravity security review of the auth module."*
- **Fast Assessment:** *"ClauGravity quick triage."*

---

## CLI Script Reference

All tools in `scripts/` are standalone Python 3.8+ utilities using standard library only:

### 1. Repository Topology Mapper (`scripts/map_repo.py`)
Analyzes directory structure, entry points, frameworks, manifests, and HTTP route endpoints across 10+ frameworks without loading full file bodies into LLM context:
```bash
# Human-readable summary
python scripts/map_repo.py .

# JSON output for automated pipelines
python scripts/map_repo.py /path/to/project --json --max-depth 4
```

### 2. Risk Pattern Scanner (`scripts/find_risk_patterns.py`)
Heuristic scanner detecting security flaws, concurrency hazards, secret leaks, and logic bugs with multiline sliding window detection:
```bash
# Standard text scan
python scripts/find_risk_patterns.py .

# Export as SARIF v2.1.0 for GitHub Code Scanning
python scripts/find_risk_patterns.py . --format sarif -o .claugravity/results.sarif

# Export as Markdown table
python scripts/find_risk_patterns.py src/ --format markdown -o .claugravity/leads.md

# Filter by category, severity, or specific rule IDs
python scripts/find_risk_patterns.py . --category Security --min-severity High
python scripts/find_risk_patterns.py . --include-rules JS-SEC-SQL,PY-SEC-INJECTION
```

### 3. Pull Request & Diff Reviewer (`scripts/diff_audit.py`)
Parses git unified diffs or patch files, identifies changed lines, and runs targeted pattern audits with automated PR verdict scoring (`BLOCK`, `FIX BEFORE MERGE`, `OK WITH NITS`, `APPROVE`):
```bash
# Audit uncommitted changes vs HEAD
python scripts/diff_audit.py

# Audit staged/cached changes
python scripts/diff_audit.py --staged

# Audit branch changes against main
python scripts/diff_audit.py main...HEAD

# Audit from a patch file and export markdown review
python scripts/diff_audit.py --patch fix.patch -o .claugravity/pr-review.md
```

### 4. Safe Tooling & Check Runner (`scripts/run_checks.py`)
Safely detects and executes local linters (`eslint`, `ruff`, `flake8`, `go vet`), type-checkers (`tsc`, `mypy`, `cargo check`), dependency audits (`npm/yarn/pnpm audit`, `pip-audit`), and unit test runners:
```bash
# Run linters, typecheckers, and dependency audits
python scripts/run_checks.py .

# Allow running test suites (pytest, python unittest, go test, npm test)
python scripts/run_checks.py . --allow-tests

# Output results in JSON format or save to file
python scripts/run_checks.py . --json -o .claugravity/checks.json
```

### 5. Review Chunk Planner (`scripts/chunk_plan.py`)
Partitions large codebases (>50k LOC) and monorepos (`packages/*`, `apps/*`, `services/*`, `modules/*`) into risk-ranked review modules based on directory weight, keyword scoring, and git churn:
```bash
# Generate partitioned review plan
python scripts/chunk_plan.py . --max-chunks 8

# Export plan as markdown checklist
python scripts/chunk_plan.py . --format markdown -o .claugravity/chunk-plan.md
```

### 6. Audit Report Scaffolder (`scripts/generate_report.py`)
Scaffolds a compliant, fully-cited `.claugravity/report.md` file matching `templates/audit-report.md` by combining topology signals, check runner outputs, and candidate finding leads:
```bash
# Scaffold standard report
python scripts/generate_report.py . -o .claugravity/report.md

# Scaffold report populated with candidate leads
python scripts/generate_report.py . --title "Production Audit" --leads-json leads.json -o .claugravity/report.md
```

### 7. Mechanical Citation Verification Gate (`scripts/verify_citations.py`)
Mechanically parses all cited code locations and verbatim excerpts from an audit report and verifies line-by-line that they exist in the target repository:
```bash
# Verify report citations
python scripts/verify_citations.py .claugravity/report.md --root .

# Verify with custom tolerance window and export verification JSON
python scripts/verify_citations.py .claugravity/report.md --root . --tolerance 5 -o .claugravity/verify.json
```

---

## Sample Finding Format

Every confirmed finding adheres to the structured format defined in `templates/finding.md`:

```markdown
### CG-001: Admin User Purge Route Completely Unauthenticated

**Status:** Confirmed  
**Severity:** Critical  
**Confidence:** High  
**Category:** Broken Access Control  
**Location:** `src/routes/admin.js:8-14`  
**CWE/OWASP:** CWE-306 / OWASP A01:2021-Broken Access Control  

**Evidence:**
```javascript
router.delete("/users/:id/purge", async (req, res) => {
  try {
    await User.findByIdAndDelete(req.params.id);
    await Order.deleteMany({ userId: req.params.id });
    res.json({ success: true, message: "User account and history purged" });
  } catch (err) {
    res.status(500).json({ error: "Purge failed" });
```

#### Root Cause
The administrative deletion route is mounted directly on the router without `requireAuth` or `requireAdmin` middleware guards. Any unauthenticated caller possessing a target user ID can trigger an irrevocable purge of the user and their associated orders.

#### Concrete Trigger Scenario
1. Unauthenticated attacker sends `DELETE /users/654321/purge` to the server.
2. The route executes immediately without token verification.
3. Target user record and all associated order histories are permanently removed from the database.

#### Minimal Fix Diff
```diff
- router.delete("/users/:id/purge", async (req, res) => {
+ router.delete("/users/:id/purge", requireAuth, requireRole("admin"), async (req, res) => {
```
```

---

## Empirical Self-Test Metrics & Validation

ClauGravity's capabilities are empirically verified through automated test suites and fixture project benchmarks:

### 1. Automated Test Suite (`tests/test_scripts.py`)
A comprehensive suite of **64 automated unit and CLI subprocess tests** executed via Python's standard `unittest` framework:
```bash
python3 -m unittest tests/test_scripts.py
# Ran 64 tests in ~0.2s (100% passing)
```
Tests cover:
- Citation parser (Windows/Unix paths, line ranges, `L` prefixes, tolerances, candidate line diagnostics).
- Topology mapping (Rust Axum/Actix, Go 1.22+ stdlib, ASP.NET Core, PHP Laravel, Rails, entry points).
- Risk pattern scanning (SARIF v2.1.0 output, multiline template strings, secret redaction, rule filtering).
- Diff auditing (unified git diffs, patch files, staged diffs, PR verdicts).
- Safe check execution (package manager detection, linter dispatch, test execution gating).
- Chunk planning (monorepo package discovery, git churn scoring, markdown plan exports).
- Report generation (topology integration, check table assembly, finding block formatting).

### 2. Fixture Project Benchmark (`tests/RESULTS.md`)
ClauGravity is validated against the bundled fixture project (`tests/fixture-project/`), which contains 12 intentionally planted real-world defects and 3 deceptive decoys:

| Metric | Iteration 1 | Iteration 2 | Target Threshold | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Planted Defects Detected** | 12 of 12 (100%) | 12 of 12 (100%) | >= 10 of 12 | **PASS** |
| **Missed Planted Defects** | 0 | 0 | <= 2 misses | **PASS** |
| **Decoys Wrongly Confirmed** | 0 | 0 | 0 confirmed | **PASS** |
| **Citation Verification Failures** | 0 (100% verified) | 0 (100% verified) | 0 failures | **PASS** |
| **Iterations to Meet Pass Bar** | 1 | 2 | 1–4 iterations | **PASS** |
| **Audit Blindness Disclosure** | Disclosed (Not Blind) | Disclosed (Not Blind) | Transparent | **PASS** |

---

## Extending ClauGravity

### Adding New Risk Patterns
Add a rule dictionary to `RULES` in `scripts/find_risk_patterns.py` with `id`, `category`, `regex`, `languages`, `severity_hint`, and `explanation`. For multiline patterns, supply `multiline_trigger` and `multiline_regex`. Always maintain zero third-party dependencies (standard library only) and add test cases to `tests/test_scripts.py`.

### Custom Ignore Rules
Place a `.claugravityignore` file in your project root containing gitignore-style glob patterns to exclude non-production code, generated directories, vendor libraries, or test fixtures from scans. Both directory slashes (`dist/`) and file patterns (`*.min.js`) are supported.

---

## Known Caveats and Limitations

- **Analytical Aid, Not a Formal Proof:** ClauGravity is an automated analytical aid. It can miss novel vulnerability chains or misunderstand complex domain constraints. Always verify findings with human domain experts prior to production deployment.
- **Leads vs. Confirmed Bugs:** Pattern matches from `find_risk_patterns.py` are candidate leads; they must pass the Phase 4 Disprove Pass before promotion to confirmed findings.
- **Fixture Project Safety:** The bundled project at `tests/fixture-project/` contains intentionally vulnerable code designed for testing. It must **never** be deployed to production or public networks.

---

## License & Disclaimers

ClauGravity is released under the [MIT License](LICENSE).

**Independent Project Disclaimer:** ClauGravity is an independent open-source project and is not affiliated with, sponsored by, or endorsed by Google LLC or Anthropic PBC.
