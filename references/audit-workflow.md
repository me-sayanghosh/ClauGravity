# ClauGravity Audit Workflow Reference

This guide details the complete 7-phase audit methodology implemented by ClauGravity. Adherence to this structured workflow ensures deep technical rigor, eliminates hallucinated defects, and maximizes auditing efficiency.

---

## The Seven Audit Phases

```
Phase 0: Scope & Setup ──> Phase 1: Map ──> Phase 2: Automated Signals
                                                      │
Phase 5: Reproduce <── Phase 4: Disprove <── Phase 3: Targeted Deep Review
         │
         v
Phase 6: Report
```

---

### Phase 0: Scope and Setup
- **Entry Criteria**: Audit request received with target repository and specified objective.
- **Actions**:
  1. Detect audit mode (FULL, MODULE, DIFF, HUNT, SECURITY, QUICK).
  2. Inspect Git working tree state (`git status`, `git branch`, recent commits).
  3. Detect tech stack and languages via project manifests (`package.json`, `pyproject.toml`, `go.mod`, etc.).
  4. Initialize `.claugravity/` directory inside target workspace for local scratchpad and notes (`notes.md`).
- **Exit Criteria**: Mode confirmed, environment characterized, `.claugravity/notes.md` initialized.
- **Common Mistakes**: Proceeding without confirming project boundaries or altering source code during setup.

---

### Phase 1: Repository Mapping
- **Entry Criteria**: Setup complete; `.claugravity/` ready.
- **Actions**:
  1. Execute `python scripts/map_repo.py <target_path>`.
  2. Identify primary entry points (HTTP routers, CLI commands, background consumers, WebSockets).
  3. Identify trust boundaries: public endpoints vs. internal/admin routes.
  4. Identify datastores, caching layers, and external third-party API integrations.
  5. Draft a concise 10-line architectural sketch into `.claugravity/notes.md`.
- **Exit Criteria**: Clear map of attack surfaces, entry points, and storage architecture documented.
- **Common Mistakes**: Reading full file bodies during mapping instead of scanning module structures and manifests.

---

### Phase 2: Automated Signals
- **Entry Criteria**: High-level repository architecture mapped.
- **Actions**:
  1. Run `python scripts/run_checks.py <target_path>` to capture native linters, type checks, and security advisories.
  2. Run `python scripts/find_risk_patterns.py <target_path> --format markdown --output .claugravity/leads.md` to identify regex-based pattern matches across the codebase. Optional SARIF export: `python scripts/find_risk_patterns.py <target_path> --format sarif -o .claugravity/scan.sarif`.
  3. Record raw lead counts into `.claugravity/notes.md`.
  4. Classify leads by priority category: Auth/Payment > Data Persistence > Input Handling > Async/Concurrency > Others.
- **Exit Criteria**: Automated signal leads compiled into candidate pool.
- **Common Mistakes**: Treating raw pattern matches as confirmed vulnerabilities without verification.

---

### Phase 3: Targeted Deep Review
- **Entry Criteria**: Prioritized candidate list and risk map established.
- **Actions**:
  1. Review candidates in strict risk order:
     1. Authentication and authorization logic
     2. Payments, financial balances, and quota tracking
     3. Data persistence, deletions, and schema migrations
     4. Untrusted external input handlers
     5. Secret handling and environment configurations
     6. Background queues and worker state
     7. Concurrency, mutexes, and shared memory
  2. Load relevant reference guides from `references/` based on technology stack.
  3. Read targeted line ranges (20–60 lines around suspect blocks).
  4. Perform end-to-end data flow tracing from untrusted source to dangerous sink.
- **Exit Criteria**: Each candidate annotated with traced source-to-sink data path or dropped.
- **Common Mistakes**: Reading large files top-to-bottom or reviewing low-risk utility code before securing core business handlers.

---

### Phase 4: Disprove Pass (The Falsification Gate)
- **Entry Criteria**: Candidate defect identified with apparent source-to-sink path.
- **Actions**:
  1. Actively attempt to falsify the bug hypothesis.
  2. Inspect calling sites: Is input guaranteed to be sanitized upstream?
  3. Inspect framework defaults: Does ORM or router automatically sanitize or escape?
  4. Check test coverage: Does an existing unit or integration test assert this behavior?
  5. Check reachability: Is the code dead, deprecated, or executed only during test runs?
  6. If disproved, move to discarded candidate log with clear justification.
- **Exit Criteria**: Only survivable defects with demonstrable failure mechanisms proceed.
- **Common Mistakes**: Confirmation bias; ignoring defensive checks in parent routers or middleware.

---

### Phase 5: Safe Reproduction (Optional & Isolated)
- **Entry Criteria**: High-confidence defect requiring empirical verification.
- **Actions**:
  1. Construct a minimal reproduction script or failing test case.
  2. **Strict Isolation**: Execute reproductions ONLY within an isolated temporary directory (e.g. `/tmp/cg-repro-XXXX/`).
  3. NEVER modify production databases, live external APIs, or working repository trees.
  4. If reproduction is purely analytical, document exact step-by-step trigger preconditions.
- **Exit Criteria**: Bug trigger verified empirically or analytically documented.
- **Common Mistakes**: Modifying user repository files to reproduce bugs or running destructive SQL queries.

---

### Phase 6: Report Generation & Verification
- **Entry Criteria**: Survived findings verified, categorized, and scored.
- **Actions**:
  1. Scaffold or format report: Run `python scripts/generate_report.py <target_path> --output .claugravity/report.md` or format findings using `templates/finding.md` within `templates/audit-report.md`.
  2. Run citation verification gate: `python scripts/verify_citations.py .claugravity/report.md --root <target_path>`.
  3. Ensure 100% of code excerpts match exact file lines.
  4. Generate prioritized fix plan structured into:
     - **Quick Wins**: Immediate, low-risk patches (typos, validation guards).
     - **High Impact**: Core vulnerability and logic bug remediation.
     - **Structural Improvements**: Architectural shifts (transactions, rate limiting, ORM migration).
  5. Include honest coverage statement, skipped directories, and assumptions.
- **Exit Criteria**: Mechanically verified, non-empty, actionable audit report generated at `.claugravity/report.md`.
- **Common Mistakes**: Skipping the citation verification gate or providing generic remediation advice.

---

## Specialized Modes

### HUNT Mode (Bug Hunting & Triage)
When auditing for a specific symptom, error stack trace, or intermittent failure:
1. **Gather Symptom**: Extract error message, stack trace, frequency, and deployment context.
2. **Formulate Hypotheses**: Generate 3 to 5 distinct, ranked hypotheses explaining the failure:
   - *Hypothesis 1*: Concurrency race condition (e.g., non-atomic DB update).
   - *Hypothesis 2*: Unhandled promise rejection / uncaught exception in asynchronous handler.
   - *Hypothesis 3*: Resource exhaustion (connection pool exhaustion, file descriptor leak).
3. **Targeted Evidence Gathering**:
   - Inspect specific call stacks and error origins.
   - Gather evidence *for* and *against* each hypothesis.
4. **Conclusion**: Rank final hypotheses, eliminate disproved causes, and deliver exact fix diff.

### DIFF Mode (Pull Request & Change Review)
When reviewing uncommitted changes or a specific branch/pull request:
1. **Run Automated Diff Audit**:
   Execute `python scripts/diff_audit.py [git-ref] --output .claugravity/diff-review.md`.
   For uncommitted working tree changes: `python scripts/diff_audit.py`.
   For PR branches: `python scripts/diff_audit.py origin/main...HEAD`.
2. **Caller and Callee Impact**:
   - Inspect all callers of modified functions.
   - Trace updated return types and error-handling requirements across caller chains.
3. **Contract Drift**: Verify that changes preserve existing API schemas and database contracts.
4. **Test Gap Analysis**: Check whether new edge cases or error branches have corresponding unit tests.
5. **Output**: Use `templates/pr-review.md` or `diff_audit.py` output to issue a clear verdict: BLOCK, FIX BEFORE MERGE, OK WITH NITS, or APPROVE.
