# Severity and Confidence Rubric

This document defines how ClauGravity scores, validates, and prioritizes audit findings. It ensures that findings reflect genuine technical risk rather than theoretical conjecture.

## 1. Severity Levels

| Severity | Definition | Impact Scope | Examples |
| :--- | :--- | :--- | :--- |
| **Critical** | Unauthenticated remote execution, direct financial loss, total data destruction, or authentication bypass. | System-wide compromise, unconstrained exploitation. | RCE via deserialization, unauthenticated admin bypass, SQL injection dumping user tables, race condition allowing wallet balance duplication. |
| **High** | Likely user-facing outage, severe data corruption, unauthorized horizontal/vertical access with preconditions. | Serious business disruption or significant data leak. | IDOR allowing access to other users private records, unhandled exception crashing primary API worker, SSRF accessing internal cloud metadata. |
| **Medium** | Edge-case correctness defect, unexpected state transition under concurrency, or moderate operational risk. | Localized data inconsistency or degraded service quality. | Unbounded query risking memory exhaustion under traffic surge, missing database index on frequently searched foreign key, missing CSRF token on state-changing non-financial action. |
| **Low** | Minor defect, theoretical risk with extensive mitigations, or defensive hygiene failure. | Negligible impact under normal operations. | Information disclosure via stack traces in debug responses, permissive CORS on read-only public endpoint, non-cryptographic random number generator used for non-security sorting. |
| **Info** | Architecture observation, dead code, or documentation gap without direct defect impact. | Informational only. | Deprecated library call with supported replacement available, missing type annotations on internal helper function. |

## 2. Confidence Levels

| Confidence | Verification Standard | Criteria |
| :--- | :--- | :--- |
| **High** | End-to-end verified | Source-to-sink path traced completely, preconditions validated, reachability confirmed, framework default defenses ruled out, and concrete trigger reproducible. |
| **Medium** | Plausible with minor assumption | Clear path from entry to sink, but one runtime precondition (e.g., specific environment variable or reverse proxy header) cannot be statically proven from source code. |
| **Low** | Pattern suspicion | Code snippet matches a risky idiom, but data flow is incomplete, downstream guards may neutralize the impact, or trigger conditions are speculative. |

## 3. Severity Adjustment Factors

A raw vulnerability type does not dictate final severity in isolation. Auditors must evaluate four contextual axes:

1. **Reachability**: Is the vulnerable code on an active public route, behind authentication, or isolated to internal CLI utilities?
2. **Authentication Preconditions**: Unauthenticated exploits score higher than those requiring authenticated regular user privileges, which in turn score higher than those requiring superadmin credentials.
3. **Exploitability**: Does triggering the issue require specific timing windows, uncommon configurations, or user interaction?
4. **Blast Radius**: Does failure compromise the entire database and infrastructure, or does it merely affect the requesting tenant?

## 4. Six Worked Examples

### Example 1: Public IDOR vs. Internal Admin IDOR
- **Case A (Public Endpoint)**: `GET /api/users/:id/billing` lacks an ownership check; any authenticated user can view invoice PDFs of any other tenant.
  - *Severity*: **High** (Direct data leak of sensitive customer billing data).
  - *Confidence*: **High** (Verified that `req.user.id !== req.params.id` is never checked).
- **Case B (Internal Admin Endpoint)**: `GET /api/admin/tenants/:id/billing` lacks an explicit tenant-scoped check, but route is guarded by `requireSuperAdmin` middleware.
  - *Severity*: **Low** (Admin already possesses broad cross-tenant management privileges; lacks privilege escalation beyond admin role).
  - *Confidence*: **High** (Verified admin middleware guards the route).

### Example 2: SQL Injection in Search vs. Internal Report Generation
- **Case A (Public Search)**: `GET /search?q=` concatenates input into an unsanitized SQL string.
  - *Severity*: **Critical** (Unauthenticated full database exfiltration).
  - *Confidence*: **High** (Direct string concatenation into DB query driver).
- **Case B (Batch Analytics CLI)**: An internal script run manually by developers uses string interpolation for table partition names from CLI flags.
  - *Severity*: **Medium** (Requires local execution access; operator already has database access).
  - *Confidence*: **High** (Observable CLI argument interpolation).

### Example 3: Unhandled Rejection in Route vs. Background Task
- **Case A (Express Route)**: An async route performs `JSON.parse(req.body.data)` inside an unhandled promise chain on Node < 16 without error middleware, causing worker process crash.
  - *Severity*: **High** (Denial of service against API workers via crafted payload).
  - *Confidence*: **High** (Missing try/catch or async wrapper around parsing).
- **Case B (Scheduled Cleanup Job)**: A nightly telemetry purge job throws on missing log files, terminating the batch run without affecting production traffic.
  - *Severity*: **Low** (Isolated task failure; resumes next cycle without user impact).
  - *Confidence*: **High** (Cron task log analysis).

### Example 4: Unbounded Query
- **Scenario**: `GET /api/products` queries `Product.find({})` with no `limit` or cursor pagination.
- **Severity**: **Medium** (As product catalog scales beyond 10,000 items, responses cause memory bloat and API latency spikes).
- **Confidence*: **High** (Explicit query inspected in route handler without pagination parameters).

### Example 5: Non-Atomic Stock Decrement (Race Condition)
- **Scenario**: An inventory service reads stock `item = await Item.findById(id)`, checks `if (item.quantity >= count)`, then executes `item.quantity -= count; await item.save()`.
- **Severity*: **High** (Concurrent checkouts oversell physical inventory, causing financial disputes).
- **Confidence*: **High** (Read-modify-write pattern verified without database transactions or atomic `$inc`).

### Example 6: Weak Random Generator for Nonces vs. UI Shuffling
- **Case A (Password Reset Token)**: `Math.random().toString(36)` used to issue password reset tokens.
  - *Severity*: **Critical** (Predictable PRNG allows account takeover).
  - *Confidence*: **High** (Direct token generation observed).
- **Case B (UI Banner Sorting)**: `Math.random()` used to randomize the order of promotional images displayed on the homepage.
  - *Severity*: **Info** / *Discarded* (No security implication; non-cryptographic random is standard for UI presentation).
  - *Confidence*: **High** (Context confirmed purely visual).

## 5. Suspicions and Dropping Candidates

### When to Mark as "Suspicion"
Mark a candidate as **Suspicion** (with **Low** confidence) only when:
1. The code construct looks dangerous (e.g., dynamic property access), but static analysis cannot determine if input originates from an untrusted caller.
2. An upstream middleware might sanitize or validate the payload, but the middleware implementation resides in an external binary or uninspected dependency.
3. Every suspicion must clearly state the exact missing link required to prove or disprove it.

### When to Drop an Item
An auditor must immediately discard a candidate when:
1. **Upstream Defenses**: Parameterized queries, schema validation (Zod, Joi), or strict type guards render the vulnerability unreachable.
2. **Framework Protection**: Framework built-ins (e.g., React JSX auto-escaping, ORM query builders) naturally neutralize the danger.
3. **Dead or Test Code**: The flagged code resides in test suites, mock files, or obsolete unreferenced modules.
4. **Documented Intentional Semantics**: The observed behavior is an explicit, documented requirement (e.g., admin CLI tool intentionally running arbitrary shell scripts).
