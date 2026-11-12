# ClauGravity
*Audit smarter. Find real bugs faster.*

ClauGravity is a production-grade Agent Skill for Google Antigravity that transforms AI coding agents into rigorous software auditors, security analysts, and bug hunters. Designed for professional engineering workflows, ClauGravity audits codebases and pull requests to discover exploitable vulnerabilities, concurrency race conditions, data persistence defects, and subtle logic errors while aggressively eliminating false alarms.

Rather than inundating developers with speculative or superficial lint warnings, ClauGravity enforces empirical evidence requirements: every confirmed finding is accompanied by a concrete trigger scenario, root-cause explanation, verified source citations, and minimal remediation diffs. By coupling static pattern screening with a rigorous second-pass falsification process, ClauGravity ensures high-signal audit reports that engineering teams can immediately trust and act upon.

---

## Why ClauGravity Works

### 1. Two-Pass Auditing & Falsification Gate
Traditional AI code reviews suffer from confirmation bias and hallucinated defects. ClauGravity uses a mandatory two-pass protocol:
- **Pass 1 (FIND)**: Fast topological mapping and pattern screening gather candidate leads.
- **Pass 2 (DISPROVE)**: The auditor actively attempts to prove each candidate is *not* a bug by validating caller constraints, framework sanitizers, ORM bindings, router-level guards, and unit test suites. Only survivors are promoted to findings.

### 2. Mechanical Citation Verification Gate
Every reported finding must cite exact file lines and verbatim code excerpts. Before any report is delivered, the mechanical citation verifier (`scripts/verify_citations.py`) validates that all cited excerpts exist line-by-line in the target repository. If a citation fails verification, the finding is automatically blocked from the report.

### 3. Risk-Ordered Review Hierarchy
Auditors prioritize review depth according to empirical failure impact:
1. Authentication, Authorization & Session Management
2. Payments, Billing & Financial Invariants
3. Data Persistence, State Mutations & Schema Migrations
4. Untrusted Ingress & External Input Handlers
5. Cryptography, Secrets & Environment Configurations
6. Background Workers, Schedulers & Queues
7. Concurrency, Shared State & Mutexes
8. Auxiliary Logic & Formatting

### 4. Read-Only Safety Posture
ClauGravity operates under a strict read-only mandate. It never modifies, deletes, or reformats user project source code. All working notes, intermediate candidate logs, and reports are written exclusively to `.claugravity/` inside the target workspace.

### 5. Token Efficiency & Scalable Chunking
For codebases exceeding 50,000 LOC, ClauGravity utilizes `scripts/chunk_plan.py` to partition repositories into bounded, risk-ranked modules, maintaining rolling summaries in `.claugravity/notes.md` to conserve context windows.

---

## Operational Modes

| Mode | Purpose | Primary Triggers & Prompts | Output Format |
| :--- | :--- | :--- | :--- |
| **FULL** | Comprehensive whole-repo audit | *"Use ClauGravity to audit this repo"*, *"Pre-release codebase health check"* | `templates/audit-report.md` |
| **MODULE** | Targeted directory or feature review | *"ClauGravity audit src/routes/orders.js"*, *"Review the auth service"* | `templates/audit-report.md` |
| **DIFF** | Pull request and uncommitted changes | *"Use ClauGravity to review my uncommitted changes"*, *"Review PR #42"* | `templates/pr-review.md` |
| **HUNT** | Symptom-specific bug & crash diagnosis | *"Why does /checkout intermittently return 500?"*, *"Debug stock overselling"* | Ranked Hypotheses & Diff |
| **SECURITY** | Dedicated OWASP vulnerability review | *"ClauGravity security review of the auth module"*, *"Hunt for vulnerabilities"* | CWE/OWASP Cited Report |
| **QUICK** | Rapid 10-minute risk triage | *"ClauGravity quick triage"*, *"Fast risk assessment"* | Executive Briefing |

---

## Repository Layout

```
ClauGravity/
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
│   └── large-repo-strategy.md        # Chunking & token efficiency guidelines
├── scripts/                          # Portable Python 3.8+ standard library utilities
│   ├── map_repo.py                   # Repository topology & entry point mapper
│   ├── find_risk_patterns.py         # Multi-language heuristic lead scanner
│   ├── run_checks.py                 # Safe native linter & typecheck runner
│   ├── chunk_plan.py                 # Risk-weighted review module planner
│   └── verify_citations.py           # Mechanical citation verification gate
├── templates/                        # Standardized report & review structures
│   ├── finding.md                    # Structured defect template
│   ├── audit-report.md               # Full audit report template
│   └── pr-review.md                  # Pull request review template
├── examples/                         # Verified completed outputs
│   ├── sample-report.md              # Complete sample audit report (6 findings)
│   └── sample-pr-review.md           # Complete sample pull request review
└── tests/                            # Validation suite & fixture project
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
