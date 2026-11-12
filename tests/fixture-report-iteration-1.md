# ClauGravity Audit Report

**Target Project:** Ecommerce Fixture Backend & Client  
**Repository Branch / Commit:** `main`  
**Audit Date:** 12 November 2026  
**Auditor Engine:** ClauGravity v1.0.0  

---

## 1. Executive Summary
A comprehensive security, reliability, and correctness audit was conducted across the `tests/fixture-project/` codebase. The application implements an Express, Mongoose, and React e-commerce stack with critical vulnerabilities in access control, authentication, database querying, and concurrent state management. High-severity defects include unauthenticated administrative deletion routes, NoSQL operator injection in authentication, and inventory overselling race conditions under load. Immediate remediation is required before production deployment.

**Overall Risk Posture:** Critical  
**Finding Breakdown:** 4 Critical, 5 High, 3 Medium, 0 Low, 0 Info (Total: 12 Confirmed Findings).

---

## 2. Scope and Coverage
- **Audited Scope:** `src/server.js`, `src/routes/`, `src/models/`, `src/middleware/`, `src/utils/`, `client/`
- **Excluded Directories:** `node_modules/`, `dist/`, `.claugravity/`
- **Total Files Inspected:** 10 source files (408 lines of code)
- **Git Context:** Working tree clean; branch `main`

---

## 3. Methodology
This audit was conducted strictly adhering to the **ClauGravity Two-Pass Auditing Framework**:
1. **Repository Mapping**: Executed `map_repo.py` to map entry points, trust boundaries, and models.
2. **Automated Signal Extraction**: Executed `find_risk_patterns.py` and `run_checks.py`.
3. **Targeted Deep Review**: Followed risk order (Auth > Payments > Persistence > Handlers > Concurrency) with manual data flow tracing.
4. **Falsification & Disproof Pass**: Applied eight-point disproof filter (`false-positive-filters.md`), discarding 3 false alarms.
5. **Mechanical Verification**: All findings validated with `verify_citations.py` against source code.

---

## 4. Findings Summary Table

| ID | Severity | Confidence | Category | Location | Title |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CG-001** | Critical | High | Access Control | `src/routes/admin.js:8-14` | Admin User Purge Route Completely Unauthenticated |
| **CG-002** | Critical | High | Injection | `src/routes/auth.js:9-13` | NoSQL Operator Injection in User Login Handler |
| **CG-003** | High | High | Access Control | `src/routes/orders.js:51-57` | Order Retrieval IDOR Lacks Tenant Ownership Verification |
| **CG-004** | High | High | Concurrency | `src/routes/orders.js:15-19` | Non-Atomic Stock Decrement Allows Inventory Oversell |
| **CG-005** | High | High | Concurrency | `src/routes/orders.js:40-44` | Missing await on Asynchronous Database Save Before Response |
| **CG-006** | Critical | High | Security | `src/server.js:23-27` | Hardcoded Fallback JWT Secret in Token Generation |
| **CG-007** | High | High | Security | `src/server.js:15-18` | Permissive Credentialed Cross-Origin Resource Sharing (CORS) |
| **CG-008** | Medium | High | Data/API | `src/routes/products.js:9-12` | Unbounded User-Facing Product Query Lacks Pagination |
| **CG-009** | High | High | Correctness | `src/routes/payments.js:18-24` | Swallowed Payment Provider Failure in Empty Catch Block |
| **CG-010** | Medium | High | Concurrency | `src/utils/notify.js:9-13` | Unmanaged Asynchronous Iteration via forEach(async) |
| **CG-011** | Medium | High | Correctness | `src/utils/pricing.js:4-10` | Floating-Point Arithmetic Imprecision in Price Calculations |
| **CG-012** | Medium | High | Correctness | `client/OrderList.jsx:8-17` | Stale React Closure and Missing Dependencies in Periodic Refresh Hook |

---

## 5. Detailed Findings

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
The administrative deletion route is mounted without `requireAuth` or `requireAdmin` middleware guards.

#### Concrete Trigger Scenario
1. An anonymous, unauthenticated user sends `DELETE /api/admin/users/TARGET_USER_ID/purge`.
2. The endpoint executes `User.findByIdAndDelete` and deletes all corresponding orders without credential verification.
3. The server responds with HTTP 200 OK and confirms permanent account deletion.

#### Impact
Catastrophic unauthorized data destruction; any remote actor can delete arbitrary accounts and order history.

#### Recommended Fix
```diff
- router.delete("/users/:id/purge", async (req, res) => {
+ router.delete("/users/:id/purge", requireAuth, requireAdmin, async (req, res) => {
```

#### Verification of Fix
Send an unauthenticated `DELETE` request to `/api/admin/users/123/purge`; verify server returns HTTP 401.

---

### CG-002: NoSQL Operator Injection in User Login Handler

**Status:** Confirmed  
**Severity:** Critical  
**Confidence:** High  
**Category:** Injection  
**Location:** `src/routes/auth.js:9-13`  
**CWE/OWASP:** CWE-943 / OWASP A03:2021-Injection  

**Evidence:**
```javascript
router.post("/login", async (req, res) => {
  try {
    const user = await User.findOne(req.body);
    if (!user) {
      return res.status(401).json({ error: "Invalid credentials" });
```

#### Root Cause
`req.body` is passed directly to `User.findOne()` without sanitizing keys or enforcing string types.

#### Concrete Trigger Scenario
1. Attacker submits HTTP POST to `/api/auth/login` with JSON payload `{"username": "admin", "passwordHash": {"$ne": null}}`.
2. Mongoose interprets `$ne` as a MongoDB query operator matching any non-null password hash.
3. The server signs and returns a valid administrative JWT without password verification.

#### Impact
Complete authentication bypass and administrative account takeover.

#### Recommended Fix
```diff
- const user = await User.findOne(req.body);
+ const username = String(req.body.username || "").trim();
+ const password = String(req.body.password || "");
+ const user = await User.findOne({ username });
+ if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
```

#### Verification of Fix
Submit `{"username": "admin", "password": {"$ne": null}}`; verify response returns HTTP 401 Unauthorized.

---

### CG-003: Order Retrieval IDOR Lacks Tenant Ownership Verification

**Status:** Confirmed  
**Severity:** High  
**Confidence:** High  
**Category:** Broken Access Control  
**Location:** `src/routes/orders.js:51-57`  
**CWE/OWASP:** CWE-639 / OWASP A01:2021-Broken Access Control  

**Evidence:**
```javascript
router.get("/:id", requireAuth, async (req, res) => {
  try {
    const order = await Order.findById(req.params.id);
    if (!order) {
      return res.status(404).json({ error: "Order not found" });
    }
    // Defect: Missing check `order.userId.toString() === req.user.id`
    res.json(order);
```

#### Root Cause
Endpoint retrieves order documents solely by route ID parameter without verifying that `order.userId` matches `req.user.id`.

#### Concrete Trigger Scenario
1. Customer A with JWT `user_a` calls `GET /api/orders/ORDER_B_ID`.
2. Server loads the order owned by Customer B.
3. Server returns full private order records and shipping addresses to Customer A.

#### Impact
Horizontal privilege escalation exposing private customer transactions and personal data.

#### Recommended Fix
```diff
- const order = await Order.findById(req.params.id);
+ const order = await Order.findOne({ _id: req.params.id, userId: req.user.id });
```

#### Verification of Fix
Call `GET /api/orders/:id` using a token belonging to a different user; verify HTTP 404 or 403 is returned.

---

### CG-004: Non-Atomic Stock Decrement Allows Inventory Oversell

**Status:** Confirmed  
**Severity:** High  
**Confidence:** High  
**Category:** Concurrency  
**Location:** `src/routes/orders.js:15-19`  
**CWE/OWASP:** CWE-362 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
    if (!product || product.stock < quantity) {
      return res.status(400).json({ error: "Insufficient inventory" });
    }

    product.stock -= quantity;
    await product.save();
```

#### Root Cause
Inventory check and decrement are performed as a read-modify-save sequence without atomic database operations or transaction locks.

#### Concrete Trigger Scenario
1. Product inventory is 1 unit.
2. Two concurrent checkouts for quantity 1 arrive simultaneously.
3. Both read `product.stock` as 1 and pass validation.
4. Both decrement stock to 0 and save, selling 2 items when only 1 is available.

#### Impact
Inventory overselling, physical fulfillment failure, and customer financial disputes.

#### Recommended Fix
```diff
- product.stock -= quantity;
- await product.save();
+ const updated = await Product.findOneAndUpdate(
+   { _id: productId, stock: { $gte: quantity } },
+   { $inc: { stock: -quantity } },
+   { new: true }
+ );
+ if (!updated) return res.status(400).json({ error: "Insufficient inventory" });
```

#### Verification of Fix
Issue two concurrent checkout requests against a product with stock 1; confirm exactly one succeeds and one receives HTTP 400.

---

### CG-005: Missing await on Asynchronous Database Save Before Response

**Status:** Confirmed  
**Severity:** High  
**Confidence:** High  
**Category:** Concurrency  
**Location:** `src/routes/orders.js:40-44`  
**CWE/OWASP:** CWE-703 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
    order.status = "SHIPPED";
    order.save(); // Defect: missing await on DB write before response

    res.json({ message: "Order processed successfully", orderId: order._id });
```

#### Root Cause
`order.save()` returns a promise that is not awaited before the HTTP response is sent, leaving errors unhandled and state uncommitted.

#### Concrete Trigger Scenario
1. Client calls `PATCH /api/orders/:id/process`.
2. The server responds 200 OK immediately.
3. If the database connection drops or validation fails during `order.save()`, the write fails silently while the client assumes success.

#### Impact
False confirmation of order status updates and silent data loss.

#### Recommended Fix
```diff
- order.save();
+ await order.save();
```

#### Verification of Fix
Inject a simulated database latency or error; confirm the client receives proper error response if the write fails.

---

### CG-006: Hardcoded Fallback JWT Secret in Token Generation

**Status:** Confirmed  
**Severity:** Critical  
**Confidence:** High  
**Category:** Security  
**Location:** `src/server.js:23-27`  
**CWE/OWASP:** CWE-798 / OWASP A02:2021-Cryptographic Failures  

**Evidence:**
```javascript
const internalToken = jwt.sign(
  { role: "system" },
  process.env.JWT_SECRET || "insecure-secret-key",
  { algorithm: "HS256" }
);
```

#### Root Cause
Application signs internal tokens using a publicly known static fallback secret string when `JWT_SECRET` is unset.

#### Concrete Trigger Scenario
1. Attacker observes default development secret in source code.
2. Attacker crafts a custom JWT with `{ "role": "admin" }` signed using `"insecure-secret-key"`.
3. Attacker accesses protected APIs using the forged token.

#### Impact
Arbitrary token forgery and system privilege escalation.

#### Recommended Fix
```diff
+ if (!process.env.JWT_SECRET) throw new Error("JWT_SECRET must be set");
  const internalToken = jwt.sign(
    { role: "system" },
-   process.env.JWT_SECRET || "insecure-secret-key",
+   process.env.JWT_SECRET,
    { algorithm: "HS256" }
  );
```

#### Verification of Fix
Ensure application refuses to boot if `JWT_SECRET` environment variable is not defined.

---

### CG-007: Permissive Credentialed Cross-Origin Resource Sharing (CORS)

**Status:** Confirmed  
**Severity:** High  
**Confidence:** High  
**Category:** Security  
**Location:** `src/server.js:15-18`  
**CWE/OWASP:** CWE-942 / OWASP A01:2021-Broken Access Control  

**Evidence:**
```javascript
app.use(cors({
  origin: "*",
  credentials: true
}));
```

#### Root Cause
CORS middleware configures wildcard origin `*` alongside `credentials: true`.

#### Concrete Trigger Scenario
1. Victim user visits a malicious website while logged into the store.
2. The malicious site issues cross-origin fetch requests with credentials to `/api/orders`.
3. Browsers allow or reflect the origin, exposing authenticated customer responses to the third-party script.

#### Impact
Cross-origin data theft of sensitive customer records and active session data.

#### Recommended Fix
```diff
- origin: "*",
+ origin: process.env.ALLOWED_ORIGINS ? process.env.ALLOWED_ORIGINS.split(",") : "https://store.example.com",
  credentials: true
```

#### Verification of Fix
Send request with `Origin: https://evil.com`; confirm `Access-Control-Allow-Origin` is omitted.

---

### CG-008: Unbounded User-Facing Product Query Lacks Pagination

**Status:** Confirmed  
**Severity:** Medium  
**Confidence:** High  
**Category:** Data/API  
**Location:** `src/routes/products.js:9-12`  
**CWE/OWASP:** CWE-770 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
router.get("/", async (req, res) => {
  try {
    const products = await Product.find({});
    res.json(products);
```

#### Root Cause
Query fetches all records from the `Product` collection without limit or cursor constraints.

#### Concrete Trigger Scenario
1. Product catalog grows to 50,000 items.
2. Concurrent users request `GET /api/products`.
3. The Node process exhausts available memory heap serializing the massive array, crashing worker instances.

#### Impact
Denial of service and worker process crashes due to memory exhaustion.

#### Recommended Fix
```diff
- const products = await Product.find({});
+ const limit = Math.min(parseInt(req.query.limit, 10) || 50, 100);
+ const page = parseInt(req.query.page, 10) || 1;
+ const products = await Product.find({}).limit(limit).skip((page - 1) * limit);
```

#### Verification of Fix
Request `GET /api/products`; verify response is capped at 50 records.

---

### CG-009: Swallowed Payment Provider Failure in Empty Catch Block

**Status:** Confirmed  
**Severity:** High  
**Confidence:** High  
**Category:** Correctness  
**Location:** `src/routes/payments.js:18-24`  
**CWE/OWASP:** CWE-390 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
  try {
    chargeResult = await fakeStripeCharge(cardToken, amount);
  } catch (err) {
    // Defect: empty catch silently swallows payment failure!
  }

  res.json({
```

#### Root Cause
Payment provider errors are discarded inside an empty `catch` block with no logging, status check, or error propagation.

#### Concrete Trigger Scenario
1. Customer initiates charge with an expired or declined credit card.
2. `fakeStripeCharge` throws an exception.
3. Catch block swallows error; endpoint returns `{ status: "success", charge: null }`.
4. Downstream fulfillment dispatches goods without valid payment collected.

#### Impact
Direct financial loss through uncollected payments for fulfilled orders.

#### Recommended Fix
```diff
  try {
    chargeResult = await fakeStripeCharge(cardToken, amount);
  } catch (err) {
-   // Defect: empty catch silently swallows payment failure!
+   return res.status(402).json({ error: "Payment failed", details: err.message });
  }
```

#### Verification of Fix
Submit payment with invalid card token; confirm server responds with HTTP 402 and error details.

---

### CG-010: Unmanaged Asynchronous Iteration via forEach(async)

**Status:** Confirmed  
**Severity:** Medium  
**Confidence:** High  
**Category:** Concurrency  
**Location:** `src/utils/notify.js:9-13`  
**CWE/OWASP:** CWE-703 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
  users.forEach(async (user) => {
    // Unawaited promise in forEach callback; does not wait for notifications to send
    await sendEmailNotification(user.email, announcement);
  });
  return { dispatched: true };
```

#### Root Cause
`Array.prototype.forEach` does not await promises returned by its callback, returning immediately while dispatches float unhandled.

#### Concrete Trigger Scenario
1. Notification service invokes `notifyCustomers()`.
2. Function returns `{ dispatched: true }` immediately before any email network calls complete.
3. If errors occur or server process shuts down, pending emails are silently lost.

#### Impact
Unreliable customer notifications and unhandled background promise rejections.

#### Recommended Fix
```diff
- users.forEach(async (user) => {
-   await sendEmailNotification(user.email, announcement);
- });
+ await Promise.all(users.map(user => sendEmailNotification(user.email, announcement)));
```

#### Verification of Fix
Monitor execution timing; verify `notifyCustomers()` resolves only after all notification promises settle.

---

### CG-011: Floating-Point Arithmetic Imprecision in Price Calculations

**Status:** Confirmed  
**Severity:** Medium  
**Confidence:** High  
**Category:** Correctness  
**Location:** `src/utils/pricing.js:4-10`  
**CWE/OWASP:** CWE-682 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
  let subtotal = 0.0;
  for (const item of items) {
    subtotal += item.price * item.quantity;
  }
  const tax = subtotal * taxRate;
  const grandTotal = subtotal + tax; // Precision loss on float money addition
  return grandTotal;
```

#### Root Cause
Using binary floating-point arithmetic for monetary calculations causes fractional cent precision errors and broken equality assertions.

#### Concrete Trigger Scenario
1. Customer purchases items where tax calculation produces `19.990000000000002`.
2. Balance check `verifyExactBalance` tests `(balance - chargeAmount) === 0.0`.
3. Due to IEEE 754 precision, comparison fails, incorrectly rejecting valid payments.

#### Impact
Erroneous checkout rejections and accounting discrepancies.

#### Recommended Fix
```diff
- let subtotal = 0.0;
- const grandTotal = subtotal + tax;
+ // Store currency in integer cents:
+ const subtotalCents = items.reduce((acc, i) => acc + Math.round(i.price * 100) * i.quantity, 0);
+ const taxCents = Math.round(subtotalCents * taxRate);
+ return (subtotalCents + taxCents) / 100;
```

#### Verification of Fix
Run test with items summing to $0.10 + $0.20; verify total equals exactly $0.30 without decimal drift.

---

### CG-012: Stale React Closure and Missing Dependencies in Periodic Refresh Hook

**Status:** Confirmed  
**Severity:** Medium  
**Confidence:** High  
**Category:** Correctness  
**Location:** `client/OrderList.jsx:8-17`  
**CWE/OWASP:** CWE-664 / OWASP A04:2021-Insecure Design  

**Evidence:**
```javascript
  useEffect(() => {
    const timer = setInterval(() => {
      // Reads stale refreshCount and filterStatus due to empty dependency array
      setRefreshCount(refreshCount + 1);
      fetch(`/api/orders?status=${filterStatus}&user=${userId}`)
        .then((res) => res.json())
        .then((data) => setOrders(data));
    }, 5000);

    return () => clearInterval(timer);
  }, []);
```

#### Root Cause
`useEffect` captures initial render closure values of `refreshCount`, `filterStatus`, and `userId` because dependencies are omitted from `[]`.

#### Concrete Trigger Scenario
1. User changes order filter dropdown from `PENDING` to `PAID`.
2. The interval continues polling using the stale initial `filterStatus` (`PENDING`).
3. `refreshCount` remains stuck at 1 because setter reads initial closed-over state `0 + 1`.

#### Impact
Client UI fails to reflect updated filter parameters and displays stale data.

#### Recommended Fix
```diff
  useEffect(() => {
    const timer = setInterval(() => {
-     setRefreshCount(refreshCount + 1);
+     setRefreshCount(prev => prev + 1);
      fetch(`/api/orders?status=${filterStatus}&user=${userId}`)
        .then((res) => res.json())
        .then((data) => setOrders(data));
    }, 5000);

    return () => clearInterval(timer);
- }, []);
+ }, [filterStatus, userId]);
```

#### Verification of Fix
Switch filter dropdown in UI; confirm immediate refetch with updated query parameter.

---

## 6. Candidates Discarded

During the Phase 4 Disprove Pass, 3 candidate leads were systematically evaluated and discarded:

1. **`src/routes/auth.js:28-36` (Candidate: Dynamic Query Injection)**:
   - *Suspicion*: Scanner flagged query object lookup in `/user-check`.
   - *Disproof*: Inspected code revealed `String(req.query.username || "").trim()`. All input is coerced to primitive string, strictly neutralizing MongoDB operator objects.
   - *Verdict*: **Discarded (Decoy 1: Parameterized Safe Lookup)**.

2. **`src/routes/products.js:20` (Candidate: Unprotected POST Route)**:
   - *Suspicion*: Scanner flagged `POST /manage/featured` lacking inline authentication middleware.
   - *Disproof*: Traced router declarations upstream; line 18 enforces `router.use("/manage", requireAuth)`. All sub-routes under `/manage` are strictly guarded.
   - *Verdict*: **Discarded (Decoy 2: Route Protected by Router-Level Middleware)**.

3. **`client/OrderList.jsx:21` (Candidate: Insecure Random Number Generator)**:
   - *Suspicion*: Scanner detected `Math.random()` usage.
   - *Disproof*: Verified context; value is utilized exclusively for client-side sorting of UI cards (`sort(() => Math.random() - 0.5)`). No token or cryptographic material is derived.
   - *Verdict*: **Discarded (Decoy 3: UI Display Shuffling)**.

---

## 7. Positive Observations
- Explicit JWT expiration configured across standard login pathways.
- Strict password hashing schema and role enumeration enforced in `User` Mongoose model.
- Clean separation between HTTP routing controllers, data schemas, and utilities.

---

## 8. Tooling Results
- `map_repo.py`: 10 source files, 21 detected routes.
- `find_risk_patterns.py`: 7 automated lead alerts.
- `run_checks.py`: Syntax verified with `node --check` on all JavaScript files.
- `verify_citations.py`: 12 of 12 citations passed mechanical verification.

---

## 9. Prioritized Fix Plan

### Quick Wins (Immediate 1-day remediation)
1. Add `requireAuth` and `requireAdmin` to `DELETE /api/admin/users/:id/purge` (CG-001).
2. Add missing `await` to `order.save()` in `PATCH /api/orders/:id/process` (CG-005).
3. Throw runtime startup error if `JWT_SECRET` is undefined (CG-006).

### High Impact (1-week sprint)
1. Sanitize login inputs with schema validation and type coercion (CG-002).
2. Add ownership check `userId: req.user.id` to order details lookup (CG-003).
3. Convert inventory checkout to atomic conditional `$inc` update (CG-004).
4. Restrict CORS origins to trusted production domains (CG-007).
5. Propagate payment gateway errors instead of empty catch (CG-009).

### Structural Improvements (Architecture roadmap)
1. Implement cursor-based pagination across all user-facing catalog queries (CG-008).
2. Migrate financial calculations to integer cents or Decimal representations (CG-011).
3. Replace async loops with `Promise.all` or dedicated message queues (CG-010).

---

## 10. Assumptions and Limitations
- Audit was conducted on static source code without an active MongoDB database instance.
- Assumed reverse proxy terminates TLS in production deployments.

---

## 11. Suggested Follow-ups
- Implement pre-commit hooks running `verify_citations.py`.
- Add integration tests specifically asserting concurrent checkout behavior.
