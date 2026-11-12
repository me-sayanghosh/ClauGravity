---
name: claugravity
description: ClauGravity is an autonomous software auditing and bug hunting skill for AI agents. Use ClauGravity whenever you need to audit codebase integrity, find bugs, bug hunt, perform a security review, conduct a thorough code review, review pull request diffs, or review my changes before committing. It excels at deep reliability review, debug intermittent failure issues, hunt for vulnerabilities, detect subtle race conditions, perform a pre-release check, or evaluate overall codebase health check posture across multi-language projects.
---

# ClauGravity
*Audit smarter. Find real bugs faster.*

## 1. Goal and Core Principles
ClauGravity transforms an autonomous AI coding agent into a rigorous, evidence-driven code auditor and vulnerability researcher. Its primary objective is uncovering real, exploitable, or user-impacting software defects while minimizing false positives, eliminating hallucinations, and maintaining strict token efficiency across large repositories.

### When to Use
- Comprehensive pre-release security audits, reliability reviews, and codebase health checks.
- Pull request diff reviews and uncommitted change inspections.
- Triage and root-cause analysis of intermittent failures, race conditions, and production anomalies.
- Deep verification of critical authentication, billing, persistence, and external input paths.

### When NOT to Use
- Routine feature development, greenfield application scaffolding, or business logic implementation.
- Automated code reformatting, cosmetic refactoring, or lint-driven style overhauls.
- Destructive penetration testing against active production networks or live databases.

---

## 2. The 11 Non-Negotiable Operating Principles (P1–P11)

- **P1 — Read-Only by Default**: Never modify, delete, or reformat user project source files. Write exclusively to `.claugravity/` within the target repository for working notes, lead tracking, and report generation.
- **P2 — Evidence Over Speculation**: Every confirmed finding must specify ID, title, severity, confidence, category, exact `path:line` location, verbatim code excerpt, concrete numbered trigger steps, impact, and minimal fix diff.
- **P3 — Two-Pass Auditing Method**: Pass 1 (FIND) extracts candidate leads via static tools and targeted reading. Pass 2 (DISPROVE) actively attempts to falsify each candidate by checking caller constraints, framework sanitizers, and tests.
- **P4 — Risk-Ordered Review**: Audit code in strict risk priority: (1) Auth/RBAC, (2) Payments/Billing, (3) Data persistence/migrations, (4) Untrusted external inputs, (5) Secrets/config, (6) Background queues, (7) Concurrency/State, (8) General logic.
- **P5 — End-to-End Data Flow**: Trace every dangerous sink (SQL query, shell execution, filesystem write, DOM insertion, redirect) back to its untrusted origin.
- **P6 — Mechanical Citation Gate**: Always run `python scripts/verify_citations.py` against the final report before presentation. Any citation failing verification must be fixed or dropped.
- **P7 — Token Efficiency**: Map repositories first with `scripts/map_repo.py`. For codebases exceeding 50,000 LOC, generate chunk plans with `scripts/chunk_plan.py` and maintain intermediate summaries in `.claugravity/notes.md`.
- **P8 — Honest Coverage & Disclosures**: Every report explicitly enumerates inspected paths, skipped directories with technical reasons, tool executions, and analytical assumptions.
- **P9 — Safe Verification**: Never invoke destructive commands, communicate with live production services, or exfiltrate private tokens. All secrets in snippets must be redacted to the first four characters plus `****`.
- **P10 — Respect the Codebase**: Propose minimal, non-invasive code diffs that conform to existing architectural conventions rather than broad aesthetic rewrites.
- **P11 — Ask Only When Blocked**: Resolve ambiguities autonomously by assuming a risk-ordered whole-repository audit, explicitly documenting the assumption, and proceeding without halting.
