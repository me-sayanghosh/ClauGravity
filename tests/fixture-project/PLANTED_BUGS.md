# Fixture Project Answer Key: Planted Defects & Decoys

This document serves as the ground-truth specification for self-testing ClauGravity. It is excluded from analysis via `.claugravityignore`.

---

## The 12 Intentionally Planted Bugs

1. **Permissive Credentialed CORS**
   - **File:** `src/server.js:15-18`
   - **Explanation:** `cors({ origin: "*", credentials: true })` misconfigures cross-origin access control, allowing untrusted origins to access credentialed endpoints.

2. **Hardcoded Fallback JWT Secret**
   - **File:** `src/server.js:23-27`
   - **Explanation:** `jwt.sign()` falls back to `"insecure-secret-key"` when `JWT_SECRET` environment variable is not defined.

3. **NoSQL Operator Injection in Login**
   - **File:** `src/routes/auth.js:10`
   - **Explanation:** `User.findOne(req.body)` allows attackers to pass MongoDB query selector objects (`{"$ne": null}`) to authenticate without a valid password.

4. **Stock Read-Modify-Save Race Condition**
   - **File:** `src/routes/orders.js:13-20`
   - **Explanation:** In `/checkout`, stock is checked and decremented in application memory before saving, allowing concurrent requests to oversell inventory.

5. **Missing await on Database Write Before Response**
   - **File:** `src/routes/orders.js:42`
   - **Explanation:** In `/orders/:id/process`, `order.save()` is executed without `await`, resulting in an unhandled floating promise and potential race condition.

6. **Order Retrieval IDOR Without Ownership Check**
   - **File:** `src/routes/orders.js:50-58`
   - **Explanation:** In `GET /orders/:id`, the route retrieves orders by primary key without checking if `order.userId` matches the authenticated `req.user.id`.

7. **Unbounded User-Facing Query**
   - **File:** `src/routes/products.js:10`
   - **Explanation:** In `GET /products`, `Product.find({})` is called without `.limit()` or pagination cursors, risking memory exhaustion.

8. **Admin Purge Route Missing Authentication & Role Middleware**
   - **File:** `src/routes/admin.js:8-16`
   - **Explanation:** `DELETE /api/admin/users/:id/purge` completely lacks `requireAuth` and `requireAdmin` middleware, allowing anonymous users to purge accounts.

9. **Swallowed Payment Failure in Empty Catch Block**
   - **File:** `src/routes/payments.js:20-22`
   - **Explanation:** In `/charge`, errors thrown by the payment provider are swallowed in an empty `catch (err) {}`, returning HTTP 200 success without a successful charge.

10. **Array.prototype.forEach with Asynchronous Callback**
    - **File:** `src/utils/notify.js:9-12`
    - **Explanation:** `users.forEach(async (user) => { ... })` does not await asynchronous operations, causing notification promises to float unmanaged.

11. **Floating-Point Arithmetic in Financial Operations**
    - **File:** `src/utils/pricing.js:4-10` and `src/utils/pricing.js:15`
    - **Explanation:** Precision issues in floating-point operations lead to rounding discrepancies and broken strict equality checks (`(balance - chargeAmount) === 0.0`).

12. **Stale React Closure and Missing useEffect Dependencies**
    - **File:** `client/OrderList.jsx:8-18`
    - **Explanation:** `useEffect` sets an interval that references `refreshCount` and `filterStatus` with an empty dependency array `[]`, causing stale closure reads.

---

## The 3 Decoys (Safe Patterns That Look Suspicious)

1. **Decoy 1: Parameterized Safe Username Check**
   - **File:** `src/routes/auth.js:28-36`
   - **Why It Is Safe:** While dynamic object construction is used, `req.query.username` is coerced via `String().trim()` and rejected if empty, preventing NoSQL operator injection.

2. **Decoy 2: Route Protected by Router-Level Middleware**
   - **File:** `src/routes/products.js:18-29`
   - **Why It Is Safe:** `router.post("/manage/featured")` appears to lack inline middleware, but is preceded by `router.use("/manage", requireAuth)`, ensuring full authentication enforcement.

3. **Decoy 3: Math.random Used Strictly for UI Display Shuffling**
   - **File:** `client/OrderList.jsx:21`
   - **Why It Is Safe:** `Math.random()` is used strictly to randomize the visual order of order cards on the client interface, carrying no cryptographic or security impact.
