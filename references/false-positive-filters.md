# False-Positive Filters and Candidate Disproof Checklist

ClauGravity operates on a strict **Two-Pass Audit Model**. Phase 2 generates candidate leads via heuristic pattern matching. Phase 4 systematically applies this disproof filter to eliminate false alarms and downgrade speculative findings.

---

## The Eight-Point Disproof Checklist

Before any candidate pattern match is confirmed as a real finding, the auditor must evaluate eight falsification questions:

1. **Attacker-Controlled Input**: Does data flowing into the dangerous sink genuinely originate from an untrusted caller (HTTP query, request body, headers, webhook), or is it statically hard-coded, computed internally, or loaded from trusted administrative configuration?
2. **Upstream Validation & Sanitization**: Has the input already passed through schema validation (Zod, Joi, Pydantic), type coercion, allowlist filtering, or regex sanitization prior to reaching the sink?
3. **Framework and ORM Built-in Protection**: Does the underlying framework or library automatically neutralize the vulnerability (e.g., ORM parameter binding, React JSX auto-escaping, template engine HTML encoding)?
4. **Production Reachability**: Can the code path be triggered in production runtime execution, or is it isolated behind inactive feature flags or disabled endpoints?
5. **Dead or Test-Only Code**: Does the code reside in test suites (`tests/`, `__tests__/`, `mock/`), benchmarking scripts, migration fixtures, or unreferenced deprecated helper files?
6. **Asserting Unit / Integration Tests**: Does an existing test suite actively assert that this specific edge case or security requirement is satisfied and verified?
7. **Documented Intended Behavior**: Is the observed behavior explicitly documented as the intended business contract (e.g., public anonymous ping endpoint)?
8. **Router or Application-Level Middleware**: Is the endpoint protected higher up in the router hierarchy (e.g., `router.use(requireAuth)`) even if individual route handlers lack inline middleware?

---

## Confidence Downgrade Rules

If a candidate cannot be fully disproved but exhibits mitigating factors, apply the following downgrade rules:

- **Downgrade to Medium Confidence**: When source-to-sink data flow is verified, but runtime execution depends on an environment setting or reverse proxy header (e.g., `X-Forwarded-For`) that cannot be confirmed from source alone.
- **Downgrade to Low Confidence (Suspicion)**: When code matches a dangerous pattern, but complete reachability cannot be traced due to dynamic dispatch or external plugin architecture.
- **Immediate Discard**: If any of checks 1, 2, 3, 5, or 8 conclusively demonstrate that no exploit path exists.

---

## 15 Common False-Positive Examples

### 1. Parameterized Queries Flagged as Injection
- **Pattern Match**: `find_risk_patterns.py` flags SQL query construction.
- **Disproof**: The query utilizes parameterized placeholders (`$1`, `?`) and binds parameters separately. No dynamic string concatenation exists.
- **Verdict**: **Discard**.

### 2. Router-Level Auth Middleware Protecting Subsequent Routes
- **Pattern Match**: An Express route `router.get("/profile", handler)` appears unauthenticated.
- **Disproof**: A preceding statement `router.use(requireAuth)` guards all routes registered below it on that router instance.
- **Verdict**: **Discard**.

### 3. Math.random Used Strictly for UI Jitter or Shuffling
- **Pattern Match**: Heuristic detects `Math.random()`.
- **Disproof**: The value is used solely to randomize the delay of an animated CSS spinner or shuffle product showcase order on the homepage.
- **Verdict**: **Discard**.

### 4. Placeholder Secrets in Example Configurations
- **Pattern Match**: Secret scanner detects `API_KEY="your-api-key-here"` or `JWT_SECRET="changeme"`.
- **Disproof**: The values reside in `.env.example` or dummy documentation files designed as setup templates.
- **Verdict**: **Discard**.

### 5. Informational TODO and FIXME Comments
- **Pattern Match**: Grep detects `// TODO: add caching later`.
- **Disproof**: The TODO represents a future optimization, not a functional bug, security vulnerability, or broken logic.
- **Verdict**: **Discard**.

### 6. Internal Admin Endpoints Missing Public Rate Limits
- **Pattern Match**: Endpoint lacks `express-rate-limit` middleware.
- **Disproof**: Route is bound strictly to private localhost / cluster-internal IP range and requires mutual TLS or VPC peering.
- **Verdict**: **Downgrade to Info** or **Discard**.

### 7. Test Fixtures Containing Mock Passwords
- **Pattern Match**: Scanner flags `password = "SecretPassword123!"`.
- **Disproof**: File is `tests/fixtures/users.json` used exclusively by local test suites.
- **Verdict**: **Discard**.

### 8. React dangerouslySetInnerHTML Sanitized with DOMPurify
- **Pattern Match**: Scanner flags `dangerouslySetInnerHTML`.
- **Disproof**: Input is passed through `DOMPurify.sanitize(input)` immediately prior to assignment.
- **Verdict**: **Discard**.

### 9. Safe Regular Expressions Flagged as ReDoS
- **Pattern Match**: Heuristic flags complex regex with quantifiers.
- **Disproof**: Regex contains no overlapping or nested unbounded repetition; string length is hard-capped to 50 characters upstream.
- **Verdict**: **Discard**.

### 10. Non-Cryptographic Hashes Used for Caching or Sharding
- **Pattern Match**: Scanner flags `murmurhash` or `crc32`.
- **Disproof**: Hash function is used to calculate in-memory cache partition keys, not security nonces or digital signatures.
- **Verdict**: **Discard**.

### 11. CORS with Specific Whitelisted Origins Flagged as Permissive
- **Pattern Match**: CORS middleware configuration detected.
- **Disproof**: Origin resolver explicitly validates incoming `Origin` against a strict trusted domain list and denies unmatched requests.
- **Verdict**: **Discard**.

### 12. CLI Maintenance Scripts Executing Shell Commands Intentionally
- **Pattern Match**: Scanner flags `child_process.exec()` or `subprocess.run()`.
- **Disproof**: The script is a developer build utility or deployment hook that intentionally invokes build tools with static arguments.
- **Verdict**: **Discard**.

### 13. Naturally Idempotent Operations Flagged for Missing Locks
- **Pattern Match**: Heuristic flags database update lacking a mutex lock.
- **Disproof**: The operation is a pure idempotent assignment (`SET status = "COMPLETED"`) where concurrent executions produce the identical valid state.
- **Verdict**: **Discard**.

### 14. Synchronous File Reads During Application Boot
- **Pattern Match**: Scanner flags `fs.readFileSync()` on the main event loop.
- **Disproof**: Invocation occurs in top-level initialization code before HTTP server calls `.listen()`.
- **Verdict**: **Discard**.

### 15. Intentional Bare Exception in Daemon Shutdown Loop
- **Pattern Match**: Scanner flags `except Exception:` in cleanup loop.
- **Disproof**: The daemon is shutting down and intentionally ignores teardown exceptions for already-closed sockets.
- **Verdict**: **Discard**.
