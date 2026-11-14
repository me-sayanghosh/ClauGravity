# Pull Request Code Review

**Pull Request:** #84: Add Order Cancellation Endpoint  
**Author:** @developer-alex  
**Target Branch:** `main` <- `feature/cancel-order`  
**Reviewer Engine:** ClauGravity v1.1.1  

---

## 1. Review Verdict

**Verdict:** **Block**

This PR introduces an unauthenticated horizontal access flaw (IDOR) and an invalid state transition in order management. Authenticated customers can cancel orders belonging to other accounts, and orders that have already reached `SHIPPED` status can be retroactively cancelled without inventory restoration or payment refund checks. These issues must be addressed before this change can be merged.

---

## 2. Synthetic Unified Diff
```diff
diff --git a/src/routes/orders.js b/src/routes/orders.js
--- a/src/routes/orders.js
+++ b/src/routes/orders.js
@@ -60,4 +60,14 @@ router.get("/:id", requireAuth, async (req, res) => {
   }
 });
 
+router.post("/:id/cancel", requireAuth, async (req, res) => {
+  try {
+    const order = await Order.findById(req.params.id);
+    if (!order) return res.status(404).json({ error: "Order not found" });
+    order.status = "CANCELLED";
+    await order.save();
+    res.json({ success: true, order });
+  } catch (err) {
+    res.status(500).json({ error: "Cancellation failed" });
+  }
+});
+
 module.exports = router;
```

---

## 3. Must-Fix Findings (Blockers)

### CG-PR-01: Insecure Direct Object Reference (IDOR) in Order Cancellation

**Severity:** High  
**Category:** Broken Access Control  
**Location:** `src/routes/orders.js:51-57`  

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

#### Problem & Impact
The new `POST /:id/cancel` handler mimics the existing query pattern in `src/routes/orders.js:51-57` by querying `Order.findById(req.params.id)` without checking tenant ownership. Any authenticated user can cancel arbitrary orders belonging to other customers by providing their order ID.

#### Concrete Fix
```diff
- const order = await Order.findById(req.params.id);
+ const order = await Order.findOne({ _id: req.params.id, userId: req.user.id });
  if (!order) return res.status(404).json({ error: "Order not found" });
```

---

### CG-PR-02: Missing State Machine Transition Validation (Cancelling Shipped Orders)

**Severity:** High  
**Category:** Correctness  
**Location:** `src/routes/orders.js:40-44`  

**Evidence:**
```javascript
    order.status = "SHIPPED";
    order.save(); // Defect: missing await on DB write before response

    res.json({ message: "Order processed successfully", orderId: order._id });
```

#### Problem & Impact
The handler unconditionally mutates `order.status = "CANCELLED"` regardless of current order lifecycle state. If an order has already transitioned to `SHIPPED` via `PATCH /:id/process` (defined at `src/routes/orders.js:40`), it can still be cancelled without coordinating with warehouse logistics or triggering payment reversals.

#### Concrete Fix
```diff
+ if (order.status !== "PENDING" && order.status !== "PAID") {
+   return res.status(400).json({ error: `Cannot cancel order in ${order.status} state` });
+ }
  order.status = "CANCELLED";
```

---

## 4. Should-Fix Items (Quality Improvements)

### 1. Missing Inventory Reversal Hook
- **Location:** `src/routes/orders.js`
- **Issue:** When an order is cancelled, deducted inventory stock is not restored to the `Product` collection.
- **Suggestion:** Add an atomic increment: `await Product.findByIdAndUpdate(item.productId, { $inc: { stock: item.quantity } });`

---

## 5. Author Questions & Clarifications Needed
1. Is refund processing through Stripe intended to trigger automatically on cancellation, or will refunds be handled out-of-band by customer support?
2. Should email notifications be dispatched to the customer when cancellation is confirmed?

---

## 6. Test Gaps & Missing Test Scenarios
- [ ] No test asserting that user A cannot cancel an order owned by user B (IDOR prevention).
- [ ] No test asserting that attempting to cancel a `SHIPPED` order receives HTTP 400 Bad Request.
- [ ] No concurrency test verifying parallel checkout and cancellation requests.

---

## 7. Reviewed Scope
- **Files Modified in PR:** `src/routes/orders.js` (Lines 60–75)
- **Callers and Models Checked:**
  - `src/models/Order.js` (Verified enum allows `"CANCELLED"`)
  - `src/server.js` (Verified route mounting under `/api/orders`)
