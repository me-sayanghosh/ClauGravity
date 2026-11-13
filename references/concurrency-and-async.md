# Concurrency and Asynchronous Programming Reference

This guide covers common pitfalls, race conditions, and asynchronous bugs in multi-threaded and event-driven runtime environments (Node.js, Go, Python asyncio, Java).

---

## 1. Read-Modify-Write and Check-Then-Act Races
- **Signal**: Application loads state into memory, performs validation logic, and writes back the modified object without locking or atomic database primitives.
- **Bad**:
  ```js
  const account = await Account.findById(id);
  if (account.balance >= amount) {
    account.balance -= amount;
    await account.save(); // Race: concurrent requests both pass the check
  }
  ```
- **Good**:
  ```js
  const result = await Account.updateOne(
    { _id: id, balance: { $gte: amount } },
    { $inc: { balance: -amount } }
  );
  if (result.matchedCount === 0) throw new Error("Insufficient funds");
  ```
- **Fix Hint**: Use atomic conditional updates (`$inc`, `UPDATE ... WHERE ...`) or database-level transactions with row locking.

---

## 2. Lost Updates
- **Signal**: Concurrent clients overwrite each other records without checking version stamps or optimistic locks.
- **Bad**:
  ```js
  const doc = await Article.findById(id);
  doc.title = req.body.title;
  await doc.save(); // Last write wins, silently obliterating intermediate edits
  ```
- **Good**:
  ```js
  const doc = await Article.findOneAndUpdate(
    { _id: id, version: req.body.expectedVersion },
    { $set: { title: req.body.title }, $inc: { version: 1 } },
    { new: true }
  );
  if (!doc) throw new Error("Conflict: Record modified by another user");
  ```
- **Fix Hint**: Enforce optimistic locking with explicit record version counters.

---

## 3. Double Submit and Missing Idempotency
- **Signal**: Payment or resource creation endpoints lacking idempotency keys, allowing duplicate requests on network retries.
- **Bad**:
  ```js
  app.post("/api/charges", async (req, res) => {
    const charge = await stripe.charges.create({ amount: req.body.amount, currency: "usd" });
    res.json(charge); // Network retry creates a second distinct charge
  });
  ```
- **Good**:
  ```js
  app.post("/api/charges", async (req, res) => {
    const idempotencyKey = req.headers["idempotency-key"];
    if (!idempotencyKey) return res.status(400).json({ error: "Idempotency-Key required" });
    const charge = await stripe.charges.create(
      { amount: req.body.amount, currency: "usd" },
      { idempotencyKey }
    );
    res.json(charge);
  });
  ```
- **Fix Hint**: Require unique client idempotency keys stored in Redis or database for state-altering transactions.

---

## 4. Missing Database Transactions
- **Signal**: Modifying multiple distinct tables or collections sequentially without a wrapping transaction.
- **Bad**:
  ```js
  await Order.create({ id, items });
  // If server crashes here, inventory was never decremented
  await Inventory.decrement({ items });
  ```
- **Good**:
  ```js
  const session = await mongoose.startSession();
  session.startTransaction();
  try {
    await Order.create([{ id, items }], { session });
    await Inventory.decrement({ items }, { session });
    await session.commitTransaction();
  } catch (err) {
    await session.abortTransaction();
    throw err;
  } finally {
    session.endSession();
  }
  ```
- **Fix Hint**: Wrap multi-collection mutations in ACID transactions or two-phase commits.

---

## 5. Cache Stampede and Stale Cache
- **Signal**: Multiple parallel workers experience cache misses simultaneously and all execute expensive database queries concurrently.
- **Bad**:
  ```js
  let data = await redis.get("catalog");
  if (!data) {
    data = await db.fetchExpensiveCatalog(); // 1,000 requests trigger 1,000 DB queries
    await redis.set("catalog", data, "EX", 300);
  }
  ```
- **Good**:
  ```js
  let data = await redis.get("catalog");
  if (!data) {
    // Single-flight or distributed lock
    data = await singleflight.do("catalog", () => db.fetchExpensiveCatalog());
    await redis.set("catalog", data, "EX", 300);
  }
  ```
- **Fix Hint**: Employ distributed mutexes, single-flight coalescing, or background cache warmers with probabilistic early expiration.

---

## 6. Unawaited Promises and Floating Promises
- **Signal**: Calling asynchronous functions returning promises without `await`, `.then()`, or `void` discarding.
- **Bad**:
  ```js
  app.post("/api/audit", (req, res) => {
    writeAuditLog(req.body); // Floating promise: errors unhandled, process crash on Node 16+
    res.status(202).send("Accepted");
  });
  ```
- **Good**:
  ```js
  app.post("/api/audit", async (req, res) => {
    await writeAuditLog(req.body).catch(err => logger.error("Audit write failed", err));
    res.status(202).send("Accepted");
  });
  ```
- **Fix Hint**: Enable TypeScript lint rule `@typescript-eslint/no-floating-promises` and explicitly handle rejections.

---

## 7. The forEach(async) Anti-Pattern
- **Signal**: Passing an async callback to `Array.prototype.forEach`. `forEach` does not await promises, executing all iterations concurrently and returning immediately.
- **Bad**:
  ```js
  items.forEach(async (item) => {
    await processOrder(item); // Not awaited; function finishes before items process
  });
  res.send("Done"); // Sends response while processing is still active!
  ```
- **Good**:
  ```js
  for (const item of items) {
    await processOrder(item); // Sequential execution properly awaited
  }
  // OR concurrent with Promise.all:
  await Promise.all(items.map(item => processOrder(item)));
  res.send("Done");
  ```
- **Fix Hint**: Replace `forEach(async ...)` with `for...of` for sequential operations or `Promise.all(items.map(...))` for concurrent execution.

---

## 8. Promise.all Partial Failure
- **Signal**: `Promise.all` rejects immediately on the first encountered failure, abandoning downstream monitoring while pending promises continue executing unmanaged.
- **Bad**:
  ```js
  const results = await Promise.all([taskA(), taskB(), taskC()]);
  ```
- **Good**:
  ```js
  const results = await Promise.allSettled([taskA(), taskB(), taskC()]);
  const failures = results.filter(r => r.status === "rejected");
  if (failures.length > 0) {
    handlePartialFailures(failures);
  }
  ```
- **Fix Hint**: Use `Promise.allSettled` when tasks are independent and partial recovery is desirable.

---

## 9. Unhandled Promise Rejections
- **Signal**: Promise rejections occurring outside of active try/catch blocks without a terminal `.catch()` listener.
- **Bad**:
  ```js
  new Promise((resolve, reject) => {
    throw new Error("Unhandled failure");
  });
  ```
- **Good**:
  ```js
  new Promise((resolve, reject) => {
    throw new Error("Handled failure");
  }).catch(err => logger.error("Caught rejection", err));
  ```
- **Fix Hint**: Register global `unhandledRejection` telemetry and wrap asynchronous handlers in framework error boundaries.

---

## 10. Event-Loop Blocking (CPU-Bound Operations)
- **Signal**: Running synchronous cryptographic hashing, large JSON parsing, or heavy regex evaluation directly on the main event loop.
- **Bad**:
  ```js
  app.post("/hash", (req, res) => {
    const hash = crypto.pbkdf2Sync(req.body.pwd, salt, 100000, 64, "sha512"); // Blocks all HTTP traffic
    res.send(hash);
  });
  ```
- **Good**:
  ```js
  app.post("/hash", (req, res) => {
    crypto.pbkdf2(req.body.pwd, salt, 100000, 64, "sha512", (err, hash) => {
      if (err) return res.status(500).send("Error");
      res.send(hash);
    });
  });
  ```
- **Fix Hint**: Offload CPU-heavy computation to Worker Threads, child processes, or asynchronous non-blocking APIs.

---

## 11. Deadlocks and Lock Acquisition Ordering
- **Signal**: Acquiring multiple locks or database rows in inconsistent orders across different code paths.
- **Bad**:
  ```js
  // Transaction 1 locks A then B; Transaction 2 locks B then A
  // Both wait indefinitely on each other
  ```
- **Good**:
  ```js
  // Enforce global deterministic locking order (e.g., sort IDs alphabetically)
  const [firstId, secondId] = [idA, idB].sort();
  await lock(firstId);
  await lock(secondId);
  ```
- **Fix Hint**: Establish and enforce a strict, deterministic acquisition order for all multiple-lock acquisitions.

---

## 12. Retries Without Exponential Backoff and Jitter
- **Signal**: Retrying failed HTTP calls in tight immediate loops, amplifying outages during downstream service degradation.
- **Bad**:
  ```js
  while (retries < 5) {
    try { return await fetchApi(); }
    catch (e) { retries++; } // Immediate retry hammers degraded dependency
  }
  ```
- **Good**:
  ```js
  while (retries < 5) {
    try { return await fetchApi(); }
    catch (e) {
      retries++;
      const delay = Math.pow(2, retries) * 100 + Math.random() * 50;
      await new Promise(r => setTimeout(r, delay));
    }
  }
  ```
- **Fix Hint**: Implement truncated exponential backoff with full jitter on all external call retries.

---

## 13. Queue Poison Messages and Infinite Redelivery
- **Signal**: Message consumer throws an unhandled error, rejecting message back to queue without dead-letter routing.
- **Bad**:
  ```js
  channel.consume("tasks", async (msg) => {
    await processTask(JSON.parse(msg.content)); // Throws on bad JSON; RabbitMQ requeues infinitely
    channel.ack(msg);
  });
  ```
- **Good**:
  ```js
  channel.consume("tasks", async (msg) => {
    try {
      await processTask(JSON.parse(msg.content));
      channel.ack(msg);
    } catch (err) {
      logger.error("Poison message routed to dead-letter", err);
      channel.nack(msg, false, false); // Do not requeue; forward to DLQ
    }
  });
  ```
- **Fix Hint**: Configure Dead Letter Exchanges (DLX) and limit maximum delivery attempts before discarding or archiving.

---

## 14. Missing Graceful Shutdown Handlers
- **Signal**: Application process exits immediately on `SIGTERM` / `SIGINT`, abruptly cutting off in-flight HTTP requests and database transactions.
- **Bad**:
  ```js
  process.on("SIGTERM", () => process.exit(0)); // Abrupt termination drops active transactions
  ```
- **Good**:
  ```js
  process.on("SIGTERM", async () => {
    server.close(async () => {
      await db.disconnect();
      process.exit(0);
    });
  });
  ```
- **Fix Hint**: Intercept termination signals, stop accepting new connections, wait for in-flight tasks to drain, and cleanly release connection pools.

---

## 15. Goroutine, Thread, and Background Task Leaks
- **Signal**: Spawning goroutines or worker threads listening on channels or sockets without cancellation contexts or exit triggers.
- **Bad**:
  ```go
  func monitor() {
    ch := make(chan int)
    go func() {
      val := <-ch // Hangs forever if nothing writes to ch
      process(val)
    }()
  }
  ```
- **Good**:
  ```go
  func monitor(ctx context.Context) {
    ch := make(chan int)
    go func() {
      select {
      case val := <-ch:
        process(val)
      case <-ctx.Done():
        return // Clean exit on context termination
      }
    }()
  }
  ```
- **Fix Hint**: Pass explicit `context.Context` to all asynchronous routines and handle cancellation channels.

---

## 16. Shared Mutable Module Singletons
- **Signal**: Storing request-scoped state (user session, tenant ID) inside module-level variables or static class properties.
- **Bad**:
  ```js
  let currentUser = null; // Shared across concurrent HTTP requests in same Node process
  app.use((req, res, next) => {
    currentUser = req.user;
    next();
  });
  ```
- **Good**:
  ```js
  // Attach request state strictly to req or AsyncLocalStorage
  import { AsyncLocalStorage } from "async_hooks";
  const userStorage = new AsyncLocalStorage();
  app.use((req, res, next) => {
    userStorage.run(req.user, () => next());
  });
  ```
- **Fix Hint**: Use scoped request context objects or `AsyncLocalStorage` to isolate concurrent request state.

---

## 17. Relational Database Row-Level Locking (`SELECT FOR UPDATE`)
- **Signal**: Checking row values (account balance, available seat count) in a transaction and updating later without acquiring a row-level write lock.
- **Bad**:
  ```sql
  -- Transaction 1 and Transaction 2 both read balance = 100 concurrently
  SELECT balance FROM accounts WHERE id = 42;
  -- Both proceed to debit 60, resulting in negative balance (-20)
  UPDATE accounts SET balance = balance - 60 WHERE id = 42;
  ```
- **Good**:
  ```sql
  -- Explicitly lock row until transaction commits
  SELECT balance FROM accounts WHERE id = 42 FOR UPDATE;
  UPDATE accounts SET balance = balance - 60 WHERE id = 42;
  ```
- **Fix Hint**: Enforce `SELECT ... FOR UPDATE` or optimistic locking versions (`WHERE version = :expected`) on financial balance mutations.

---

## 18. Goroutine Variable Closure Capture
- **Signal**: In Go (prior to Go 1.22), launching a goroutine inside a loop that references the loop variable directly by pointer/closure.
- **Bad**:
  ```go
  for _, item := range items {
    go func() {
      process(item) // Data race: all goroutines reference the same memory address of item
    }()
  }
  ```
- **Good**:
  ```go
  for _, item := range items {
    go func(val Item) {
      process(val) // Passed explicitly by value
    }(item)
  }
  ```
- **Fix Hint**: Pass loop variables explicitly as arguments to goroutine function closures.
