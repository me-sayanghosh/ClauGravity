### [FINDING_ID]: [Concise Title Describing the Specific Flaw]

**Status:** Confirmed | Suspicion  
**Severity:** Critical | High | Medium | Low | Info  
**Confidence:** High | Medium | Low  
**Category:** Broken Access Control | Injection | Race Condition | Concurrency | Correctness | Security | Data/API  
**Location:** `path/to/file.ext:start_line-end_line`  
**CWE/OWASP:** CWE-XXX / OWASP AXX:2021  

**Evidence:**
```language
// Verbatim code excerpt directly matching lines from the target repository
const example = vulnerableCall(untrustedInput);
```

#### Root Cause
A concise explanation of the technical mechanism responsible for the defect (e.g., missing input validation, un-awaited asynchronous promise, missing transactional lock).

#### Concrete Trigger Scenario
A numbered, step-by-step walk-through demonstrating how the vulnerability or bug is exercised in practice:
1. The client issues an unauthenticated HTTP POST request to `/api/vulnerable-endpoint` with payload `{"param": {"$ne": null}}`.
2. The route handler passes the payload directly to the database query without sanitizing operator keys.
3. The query executes unconditionally, returning the first administrative record and issuing a valid session token.

#### Impact
The real-world business and system consequence of exploitation or triggering (e.g., full authentication bypass, data loss, process crash, financial over-allocation).

#### Recommended Fix
A minimal, surgical code modification that eliminates the flaw while conforming to surrounding codebase conventions:

```diff
- const example = vulnerableCall(untrustedInput);
+ const sanitized = sanitize(untrustedInput);
+ const example = vulnerableCall(sanitized);
```

#### Verification of Fix
Instructions on how to test and verify that the fix resolves the problem without introducing regressions:
- Run targeted automated check: `npm test tests/auth.test.js`.
- Execute reproduction script to confirm that the trigger payload now receives HTTP 400 Bad Request.
