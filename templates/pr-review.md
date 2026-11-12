# Pull Request Code Review

**Pull Request:** #[PR_NUMBER]: [PR Title]  
**Author:** @[Author]  
**Target Branch:** `main` <- `feature-branch`  
**Reviewer:** ClauGravity v1.0.0  

---

## 1. Review Verdict

**Verdict:** **Block** | **Fix before merge** | **OK with nits**

[Provide a 2–3 sentence executive summary explaining the rationale for the verdict.]

---

## 2. Summary of Changes
- Core functionality introduced or refactored in this PR.
- Key modules affected and API surface impacts.
- Migration or configuration requirements.

---

## 3. Must-Fix Findings (Blockers)

### CG-PR-01: [Title of Critical/High Blocker Finding]

**Severity:** High  
**Category:** Concurrency | Security | Correctness  
**Location:** `src/controllers/orderController.js:12-18`  

**Evidence:**
```javascript
const order = await Order.findById(req.params.id);
order.status = req.body.status;
await order.save();
```

#### Problem & Impact
Explanation of why this change introduces a regression, vulnerability, or failure in production.

#### Concrete Fix
```diff
- order.status = req.body.status;
- await order.save();
+ await Order.findOneAndUpdate(
+   { _id: req.params.id, status: "PENDING" },
+   { $set: { status: req.body.status } }
+ );
```

---

## 4. Should-Fix Items (Non-Blocking Quality Improvements)

### 1. [Title of Non-Blocking Improvement]
- **Location:** `src/utils/formatters.js:45-50`
- **Issue:** Redundant string conversion or missing nullish coalescing.
- **Suggestion:** Refactor to use optional chaining.

---

## 5. Author Questions & Architectural Inquiries
1. What is the expected behavior when a customer cancels an order that has already transitioned to `SHIPPED`?
2. Are database migrations for the new `metadata` column intended to run prior to service deployment?

---

## 6. Test Gaps & Missing Test Scenarios
- [ ] Missing unit test for non-existent record ID on `GET /api/orders/:id`.
- [ ] No concurrency test verifying parallel status updates do not overwrite newer states.
- [ ] Missing error boundary test when downstream payment gateway times out.

---

## 7. Reviewed Scope
- **Files Modified in PR:**
  - `src/controllers/orderController.js` (Lines 1–120)
  - `src/models/Order.js` (Lines 15–30)
- **Upstream Callers Checked:**
  - `src/server.js` (Route mounting and middleware chain)
  - `src/jobs/nightlyReconciliation.js` (Caller of order status updates)
