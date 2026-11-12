# Data and API Reliability Reference

This guide catalogs design patterns, database pitfalls, and API integration flaws that undermine system stability, data integrity, and cross-service reliability.

---

## 1. Transaction Boundaries
- **Signal**: Performing multiple interrelated write operations across distinct tables or documents without an enveloping ACID transaction.
- **Bad**:
  ```sql
  INSERT INTO orders (id, user_id, amount) VALUES (1, 10, 100);
  -- If power or connection drops here, wallet deduction never happens
  UPDATE wallets SET balance = balance - 100 WHERE user_id = 10;
  ```
- **Good**:
  ```sql
  BEGIN TRANSACTION;
  INSERT INTO orders (id, user_id, amount) VALUES (1, 10, 100);
  UPDATE wallets SET balance = balance - 100 WHERE user_id = 10;
  COMMIT;
  ```

---

## 2. N+1 Query Anti-Pattern
- **Signal**: Executing a query inside a loop for each item returned by an initial query rather than using batch joins or eager loading.
- **Bad**:
  ```js
  const users = await User.find({ role: "developer" });
  for (const u of users) {
    u.posts = await Post.find({ authorId: u.id }); // N queries executed in sequence
  }
  ```
- **Good**:
  ```js
  const users = await User.find({ role: "developer" }).lean();
  const userIds = users.map(u => u._id);
  const posts = await Post.find({ authorId: { $in: userIds } }).lean();
  // Map posts in-memory
  ```

---

## 3. Missing Indexes on High-Cardinality and Filter Fields
- **Signal**: Querying tables with `WHERE user_id = ?` or `WHERE status = ? AND created_at > ?` where no index covers the filter columns.
- **Bad**:
  ```sql
  -- Full table scan across millions of audit rows
  SELECT * FROM audit_logs WHERE tenant_id = "t_123" ORDER BY created_at DESC LIMIT 50;
  ```
- **Good**:
  ```sql
  -- Create composite index
  CREATE INDEX idx_audit_logs_tenant_created ON audit_logs (tenant_id, created_at DESC);
  ```

---

## 4. Unbounded Queries and Missing Limits
- **Signal**: Calling `SELECT * FROM table` or `Model.find({})` without specifying an explicit limit or pagination bounds.
- **Bad**:
  ```js
  app.get("/api/products", async (req, res) => {
    const products = await Product.find({}); // Returns all 500,000 products, causing OOM
    res.json(products);
  });
  ```
- **Good**:
  ```js
  app.get("/api/products", async (req, res) => {
    const limit = Math.min(parseInt(req.query.limit, 10) || 50, 100);
    const products = await Product.find({}).limit(limit);
    res.json(products);
  });
  ```

---

## 5. Pagination and Cursor Drift Bugs
- **Signal**: Using large `OFFSET` values in SQL which cause linear disk scans and duplicate or skipped items when new records are inserted during browsing.
- **Bad**:
  ```sql
  SELECT * FROM transactions ORDER BY created_at DESC LIMIT 20 OFFSET 100000;
  ```
- **Good**:
  ```sql
  -- Keyset / Cursor-based pagination
  SELECT * FROM transactions WHERE created_at < :last_seen_timestamp ORDER BY created_at DESC LIMIT 20;
  ```

---

## 6. Schema and Validation Drift
- **Signal**: Application domain models assume mandatory fields that are nullable or missing in the underlying database schema.
- **Bad**:
  ```ts
  // Code assumes email is non-nullable string
  interface Profile { email: string; }
  // DB schema allows NULL values for legacy users, resulting in TypeError at runtime
  ```
- **Good**:
  ```ts
  import { z } from "zod";
  const ProfileSchema = z.object({
    email: z.string().email().nullable().default(null)
  });
  ```

---

## 7. Risky Database Migrations
- **Signal**: Adding a non-null column without a default value, or dropping a column actively read by previous application versions during rolling zero-downtime deployments.
- **Bad**:
  ```sql
  ALTER TABLE users ADD COLUMN age INT NOT NULL; -- Locks table and fails on existing rows
  ```
- **Good**:
  ```sql
  -- Multi-phase expand/contract migration
  ALTER TABLE users ADD COLUMN age INT NULL;
  -- Backfill data, then set default and not-null in subsequent deploy
  ```

---

## 8. Soft-Delete Record Leaks
- **Signal**: Queries omitting `WHERE deleted_at IS NULL`, inadvertently exposing deactivated accounts, canceled items, or deleted records.
- **Bad**:
  ```js
  const users = await User.find({ companyId }); // Returns soft-deleted users
  ```
- **Good**:
  ```js
  const users = await User.find({ companyId, deletedAt: null });
  ```

---

## 9. Inconsistent API Response and Error Formats
- **Signal**: Some API endpoints returning `{ data: ... }` while others return raw arrays, or returning unstructured string error messages instead of standard JSON envelopes.
- **Bad**:
  ```js
  res.status(500).send("Database failure"); // Incompatible with JSON clients
  ```
- **Good**:
  ```js
  res.status(500).json({
    error: {
      code: "DATABASE_ERROR",
      message: "An internal database error occurred",
      requestId: req.id
    }
  });
  ```

---

## 10. API Contract and Backward Compatibility Breakage
- **Signal**: Removing fields, renaming JSON keys, or changing data types in responses without versioning or deprecation notices.
- **Bad**:
  ```json
  // V1 returned: { "userId": 123 }
  // V2 breaking change without versioning:
  { "id": "user_123" }
  ```
- **Good**:
  ```json
  // Maintain backward-compatible alias until V1 deprecation window closes:
  { "id": "user_123", "userId": 123 }
  ```

---

## 11. Boundary Validation Failures
- **Signal**: Trusting input shape and data types directly from request payloads without schema validation at the HTTP boundary.
- **Bad**:
  ```js
  app.post("/api/update", (req, res) => {
    applyDiscount(req.body.discount); // If discount is "NaN" or negative object, bypasses checks
  });
  ```
- **Good**:
  ```js
  import { z } from "zod";
  const DiscountSchema = z.object({
    discount: z.number().min(0).max(100)
  });
  app.post("/api/update", (req, res) => {
    const data = DiscountSchema.parse(req.body);
    applyDiscount(data.discount);
  });
  ```

---

## 12. Cross-Service Partial Failure and Sagas
- **Signal**: Calling multiple external microservices sequentially where failure in service 3 leaves services 1 and 2 in a modified, uncompensated state.
- **Bad**:
  ```js
  await paymentService.charge(card);
  await inventoryService.reserve(items);
  await notificationService.send(email); // If this throws, money is charged and items reserved with no notice
  ```
- **Good**:
  ```js
  // Saga pattern with compensating actions
  try {
    await orchestrateOrder(order);
  } catch (err) {
    await rollbackPayment(order);
    await releaseInventory(order);
    throw err;
  }
  ```

---

## 13. Timeouts, Retries, and Circuit Breakers
- **Signal**: Outbound HTTP or RPC requests lacking connection and read timeouts, or failing to break circuits during sustained downstream outages.
- **Bad**:
  ```js
  const client = new HttpClient(); // Default socket timeout is infinity
  ```
- **Good**:
  ```js
  const client = new HttpClient({
    timeoutMs: 3000,
    retryConfig: { maxRetries: 3, backoffFactor: 2 },
    circuitBreaker: { failureThreshold: 5, resetTimeoutMs: 30000 }
  });
  ```

---

## 14. UTC Storage vs. Local Display
- **Signal**: Storing timestamps in server local time or database session timezone rather than normalized UTC with ISO 8601 representation.
- **Bad**:
  ```js
  const record = { createdAt: new Date().toLocaleDateString() }; // Loses time and zone info
  ```
- **Good**:
  ```js
  const record = { createdAt: new Date().toISOString() }; // Always ISO 8601 UTC string
  ```

---

## 15. Enum and State Machine Transition Violations
- **Signal**: Directly setting status fields without validating that the state transition is valid according to business lifecycle rules.
- **Bad**:
  ```js
  // Can transition directly from CANCELLED to SHIPPED
  order.status = req.body.status;
  await order.save();
  ```
- **Good**:
  ```js
  const ALLOWED_TRANSITIONS = {
    PENDING: ["CONFIRMED", "CANCELLED"],
    CONFIRMED: ["SHIPPED", "CANCELLED"],
    SHIPPED: ["DELIVERED"],
    CANCELLED: []
  };
  if (!ALLOWED_TRANSITIONS[order.status]?.includes(req.body.status)) {
    throw new Error(`Invalid status transition from ${order.status} to ${req.body.status}`);
  }
  order.status = req.body.status;
  await order.save();
  ```
