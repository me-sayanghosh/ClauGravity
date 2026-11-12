# General Bug Patterns Reference

This reference catalogs recurring software defects, logic pitfalls, and correctness errors across modern programming languages. Each entry provides an actionable detection signal, a concrete anti-pattern (bad), and the correct implementation (good).

---

## 1. Off-by-One and Boundary Errors
- **Signal**: Loops using `<= array.length`, slice boundaries omitting the terminal element, or pagination off-by-one calculations.
- **Bad**:
  ```js
  for (let i = 0; i <= items.length; i++) {
    process(items[i]); // Throws on items[items.length] (undefined)
  }
  ```
- **Good**:
  ```js
  for (let i = 0; i < items.length; i++) {
    process(items[i]);
  }
  ```

---

## 2. Null or Undefined Dereference
- **Signal**: Direct property access on objects returned from search, database lookups, or optional parameters without null checks or optional chaining.
- **Bad**:
  ```ts
  const user = await findUser(id);
  return user.profile.email; // Crashes if user or profile is null
  ```
- **Good**:
  ```ts
  const user = await findUser(id);
  return user?.profile?.email ?? "no-email@example.com";
  ```

---

## 3. Dangerous Type Coercion and Equality Operators
- **Signal**: Use of loose equality `==` or `!=` in JavaScript/PHP, or assignment `=` inside conditional predicates.
- **Bad**:
  ```js
  if (userRole == false) { /* falsy coercion matches 0, "", [] */ }
  if (status = "active") { /* accidental assignment always truthy */ }
  ```
- **Good**:
  ```js
  if (userRole === false) { /* strict comparison */ }
  if (status === "active") { /* strict comparison */ }
  ```

---

## 4. Integer Overflow and Range Truncation
- **Signal**: Bitwise operations or integer accumulation in languages with bounded integer types without overflow checks.
- **Bad**:
  ```go
  var total int32 = 2000000000
  total += 1000000000 // Silently wraps to negative value
  ```
- **Good**:
  ```go
  var total int64 = 2000000000
  total += 1000000000
  ```

---

## 5. Floating-Point Arithmetic in Financial Operations
- **Signal**: Using IEEE 754 floating-point numbers (`float`, `double`, JS `Number`) for currency, pricing, and balances.
- **Bad**:
  ```js
  const total = 0.1 + 0.2; // 0.30000000000000004
  if (total === 0.3) { chargeCustomer(total); }
  ```
- **Good**:
  ```js
  // Store amounts in integer cents or use Decimal library
  const totalCents = 10 + 20; // 30 cents ($0.30)
  ```

---

## 6. Timezone, DST, and Naive Date Parsing
- **Signal**: Constructing timestamps using localized string parsing or naive datetimes across international boundaries.
- **Bad**:
  ```python
  from datetime import datetime
  created_at = datetime.now() # Naive local datetime missing timezone
  ```
- **Good**:
  ```python
  from datetime import datetime, timezone
  created_at = datetime.now(timezone.utc) # Explicit UTC timestamp
  ```

---

## 7. Unicode and String Encoding Issues
- **Signal**: Character-based indexing or length checks assuming single-byte characters for multi-byte UTF-8 or surrogate pairs.
- **Bad**:
  ```js
  const str = "🚀";
  const len = str.length; // 2 (counts UTF-16 code units, not graphemes)
  ```
- **Good**:
  ```js
  const str = "🚀";
  const len = Array.from(str).length; // 1 grapheme
  ```

---

## 8. Locale-Sensitive Operations
- **Signal**: Uppercase or lowercase conversions without specifying invariant or root locale.
- **Bad**:
  ```java
  // In Turkish locale, "i".toUpperCase() becomes "İ" (dotted capital I)
  if (input.toUpperCase().equals("USER")) { grantAccess(); }
  ```
- **Good**:
  ```java
  if (input.toUpperCase(Locale.ROOT).equals("USER")) { grantAccess(); }
  ```

---

## 9. Sort Stability and Comparator Errors
- **Signal**: Sorting comparators that return boolean instead of negative/zero/positive, or inconsistent ordering logic violating strict weak ordering.
- **Bad**:
  ```js
  // Incorrect comparator returning boolean
  items.sort((a, b) => a.id > b.id);
  ```
- **Good**:
  ```js
  items.sort((a, b) => a.id - b.id);
  ```

---

## 10. Shared-Object Mutation and Parameter Tampering
- **Signal**: Modifying parameter objects or module-level singletons in-place during request handling.
- **Bad**:
  ```js
  function formatOptions(options) {
    options.processed = true; // Mutates caller object
    return options;
  }
  ```
- **Good**:
  ```js
  function formatOptions(options) {
    return { ...options, processed: true }; // Immutably copies
  }
  ```

---

## 11. Shallow vs. Deep Copy Confusion
- **Signal**: Using spread operators or `Object.assign` to clone nested structures, followed by inner property mutations.
- **Bad**:
  ```js
  const clone = { ...original };
  clone.nested.setting = false; // Mutates original.nested as well!
  ```
- **Good**:
  ```js
  const clone = structuredClone(original);
  clone.nested.setting = false;
  ```

---

## 12. Resource Leaks (Files, Sockets, Connections, Timers)
- **Signal**: Opening handles without try-finally blocks, defer statements, or context managers; uncleaned `setInterval`.
- **Bad**:
  ```python
  f = open("data.csv")
  data = f.read() # If exception occurs, descriptor leaks
  ```
- **Good**:
  ```python
  with open("data.csv") as f:
    data = f.read()
  ```

---

## 13. Swallowed Errors and Empty Catches
- **Signal**: `catch (e) {}` with no logging, re-throw, or degradation strategy.
- **Bad**:
  ```js
  try {
    await processPayment(order);
  } catch (err) {
    // Silently fails; order treated as successful
  }
  ```
- **Good**:
  ```js
  try {
    await processPayment(order);
  } catch (err) {
    logger.error("Payment failed", { orderId: order.id, error: err });
    throw new PaymentProcessingError(err);
  }
  ```

---

## 14. Incorrect HTTP and Process Error Status Codes
- **Signal**: Returning HTTP 200 OK with an embedded `{ error: "unauthorized" }`, or exiting with status code 0 on failure.
- **Bad**:
  ```js
  if (!isAuthenticated) {
    return res.status(200).json({ error: "Unauthorized access" });
  }
  ```
- **Good**:
  ```js
  if (!isAuthenticated) {
    return res.status(401).json({ error: "Authentication required" });
  }
  ```

---

## 15. Unbounded Loops, Recursion, and Memory Growth
- **Signal**: While loops lacking progress statements, recursion without depth bounds, or accumulating arrays in global scope.
- **Bad**:
  ```js
  while (cursor.hasNext()) {
    cache.push(cursor.next()); // Unbounded memory exhaustion
  }
  ```
- **Good**:
  ```js
  const MAX_BATCH = 1000;
  let count = 0;
  while (cursor.hasNext() && count++ < MAX_BATCH) {
    await processBatchItem(cursor.next());
  }
  ```

---

## 16. Missing Timeouts on External Network and IPC Calls
- **Signal**: HTTP client requests or socket connections created without an explicit timeout configuration.
- **Bad**:
  ```js
  const res = await fetch("https://api.partner.com/webhook"); // Can hang indefinitely
  ```
- **Good**:
  ```js
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch("https://api.partner.com/webhook", { signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
  ```

---

## 17. Inconsistent State After Partial Failure
- **Signal**: Multi-step state modifications without transactional guarantees or rollback hooks.
- **Bad**:
  ```js
  await deductUserCredits(userId, 50);
  await generateAiArtifact(); // If this throws, credits remain deducted without artifact
  ```
- **Good**:
  ```js
  await db.transaction(async (trx) => {
    await deductUserCredits(userId, 50, { trx });
    await recordPendingGeneration(userId, { trx });
  });
  ```

---

## 18. Copy-Paste Errors
- **Signal**: Duplicate blocks of logic where variable names, field keys, or conditions were not adapted for the new branch.
- **Bad**:
  ```js
  const width = parseDimension(req.body.width);
  const height = parseDimension(req.body.width); // Copy-paste bug: read width instead of height
  ```
- **Good**:
  ```js
  const width = parseDimension(req.body.width);
  const height = parseDimension(req.body.height);
  ```

---

## 19. Enum and Branch Non-Exhaustiveness
- **Signal**: Switch statements or if-else ladders lacking a default case or compile-time exhaustiveness check.
- **Bad**:
  ```ts
  type State = "PENDING" | "APPROVED" | "REJECTED";
  function getAction(s: State) {
    if (s === "PENDING") return "wait";
    if (s === "APPROVED") return "ship";
    // REJECTED falls through to undefined
  }
  ```
- **Good**:
  ```ts
  function getAction(s: State): string {
    switch (s) {
      case "PENDING": return "wait";
      case "APPROVED": return "ship";
      case "REJECTED": return "cancel";
      default: {
        const _exhaustive: never = s;
        throw new Error(`Unhandled state: ${_exhaustive}`);
      }
    }
  }
  ```

---

## 20. Dead Code Masking Logic Errors
- **Signal**: Unreachable statements following an early return or unconditional throw, obscuring missing logic.
- **Bad**:
  ```js
  function validate(user) {
    return true; // Accidental early debug return
    if (!user.isActive) throw new Error("Inactive user");
  }
  ```
- **Good**:
  ```js
  function validate(user) {
    if (!user.isActive) throw new Error("Inactive user");
    return true;
  }
  ```

---

## 21. Variable Shadowing
- **Signal**: Declaring an inner scope variable with the same identifier as an outer or module-level variable.
- **Bad**:
  ```js
  let user = getSessionUser();
  function process(id) {
    let user = findAccount(id); // Shadows outer user
    notify(user);
  }
  ```
- **Good**:
  ```js
  const sessionUser = getSessionUser();
  function process(id) {
    const targetAccount = findAccount(id);
    notify(targetAccount);
  }
  ```

---

## 22. Operator Precedence Mistakes
- **Signal**: Mixing bitwise operators, ternary conditions, nullish coalescing, or boolean logic without explicit grouping parentheses.
- **Bad**:
  ```js
  const val = a || b ?? c; // Syntax error in modern JS, or unexpected precedence
  const mask = flag & 1 === 1; // Evaluates (1 === 1) first due to precedence!
  ```
- **Good**:
  ```js
  const val = (a || b) ?? c;
  const mask = (flag & 1) === 1; // Explicit parentheses
  ```
