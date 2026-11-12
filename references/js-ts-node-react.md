# JavaScript, TypeScript, Node.js, and React Reference

A comprehensive guide to idiomatic patterns, vulnerability detection, and performance pitfalls across the JavaScript and TypeScript ecosystem.

---

## 1. Missing await and Floating Promises
- **Signal**: Calling asynchronous functions returning promises without `await`, leading to unhandled errors or out-of-order execution.
- **Bad**:
  ```js
  app.post("/log", (req, res) => {
    saveAuditLog(req.body); // Floating promise
    res.sendStatus(200);
  });
  ```
- **Good**:
  ```js
  app.post("/log", async (req, res, next) => {
    try {
      await saveAuditLog(req.body);
      res.sendStatus(200);
    } catch (err) {
      next(err);
    }
  });
  ```

---

## 2. Array.prototype.forEach with Async Callbacks
- **Signal**: Passing an async function to `forEach`. The loop finishes synchronously without waiting for iterations.
- **Bad**:
  ```js
  ids.forEach(async (id) => {
    await deleteRecord(id);
  });
  res.send("Deleted"); // Responds before deletions complete
  ```
- **Good**:
  ```js
  for (const id of ids) {
    await deleteRecord(id);
  }
  res.send("Deleted");
  ```

---

## 3. Express Asynchronous Error Handling
- **Signal**: Asynchronous route handlers in Express 4 without `try/catch` or an async wrapper, causing unhandled promise rejections that crash the Node process.
- **Bad**:
  ```js
  app.get("/users", async (req, res) => {
    const data = await fetchUsers(); // If throws, bypasses Express error middleware
    res.json(data);
  });
  ```
- **Good**:
  ```js
  const asyncHandler = fn => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
  app.get("/users", asyncHandler(async (req, res) => {
    const data = await fetchUsers();
    res.json(data);
  }));
  ```

---

## 4. Request Validation (Zod, Joi, Yup)
- **Signal**: Relying on ad-hoc conditional checks or unvalidated `req.body` and `req.query` properties.
- **Bad**:
  ```js
  app.post("/pay", (req, res) => {
    if (!req.body.amount) return res.status(400).send("Amount missing");
    charge(req.body.amount); // If amount is a negative number or object, passes
  });
  ```
- **Good**:
  ```js
  import { z } from "zod";
  const PaySchema = z.object({ amount: z.number().positive() });
  app.post("/pay", (req, res) => {
    const { amount } = PaySchema.parse(req.body);
    charge(amount);
  });
  ```

---

## 5. NoSQL Operator Injection
- **Signal**: Passing unparsed `req.body` or `req.query` objects directly into MongoDB query methods.
- **Bad**:
  ```js
  // If req.body is { username: "admin", password: { $ne: "" } }
  const user = await User.findOne(req.body);
  ```
- **Good**:
  ```js
  const user = await User.findOne({
    username: String(req.body.username || ""),
    passwordHash: String(req.body.password || "")
  });
  ```

---

## 6. Mongoose Indexes and Missing Keys
- **Signal**: Schemas lacking explicit indexes on foreign keys, tenant IDs, or frequently queried fields.
- **Bad**:
  ```js
  const OrderSchema = new mongoose.Schema({ userId: String, status: String });
  ```
- **Good**:
  ```js
  const OrderSchema = new mongoose.Schema({ userId: { type: String, index: true }, status: String });
  OrderSchema.index({ userId: 1, status: 1 });
  ```

---

## 7. Unbounded Database Queries
- **Signal**: Invoking `find({})` without specifying `.limit()` or pagination cursors.
- **Bad**:
  ```js
  const records = await Transaction.find({}); // Out of memory on large collection
  ```
- **Good**:
  ```js
  const records = await Transaction.find({}).limit(50);
  ```

---

## 8. Read-Modify-Save Race Conditions vs. Atomic Updates
- **Signal**: Loading a document, modifying a field in JavaScript, and calling `.save()` without transactions or atomic operators.
- **Bad**:
  ```js
  const item = await Item.findById(id);
  item.stock -= 1;
  await item.save(); // Race condition: concurrent checkouts overwrite stock
  ```
- **Good**:
  ```js
  const updated = await Item.findOneAndUpdate(
    { _id: id, stock: { $gte: 1 } },
    { $inc: { stock: -1 } },
    { new: true }
  );
  if (!updated) throw new Error("Out of stock");
  ```

---

## 9. Mongoose Replica-Set Transaction Requirements
- **Signal**: Using `.startSession()` and `.startTransaction()` on standalone MongoDB instances, causing runtime failure.
- **Bad**:
  ```js
  // Fails on standalone Mongo dev instances without replica set
  const session = await mongoose.startSession();
  session.startTransaction();
  ```
- **Good**:
  ```js
  // Verify deployment topology or handle replica-set requirements
  const session = await mongoose.startSession();
  if (mongoose.connection.client.topology.description.type.includes("ReplicaSet")) {
    session.startTransaction();
  }
  ```

---

## 10. Mongoose lean() Surprises
- **Signal**: Using `.lean()` and attempting to access virtual getters, document helper methods, or timestamp hooks.
- **Bad**:
  ```js
  const user = await User.findById(id).lean();
  console.log(user.fullName); // undefined: virtual getters not attached to plain objects
  ```
- **Good**:
  ```js
  // Either use full document or explicitly compute virtuals
  const user = await User.findById(id);
  console.log(user.fullName);
  ```

---

## 11. Populate N+1 Query Traps
- **Signal**: Iterating over documents and calling `.populate()` or manual find queries in a loop.
- **Bad**:
  ```js
  const orders = await Order.find({});
  for (const o of orders) {
    await o.populate("items"); // N individual round-trips
  }
  ```
- **Good**:
  ```js
  const orders = await Order.find({}).populate("items"); // Single batch query
  ```

---

## 12. Mongoose Update Validators
- **Signal**: Calling `findOneAndUpdate` or `updateOne` without passing `{ runValidators: true }`, bypassing schema validation.
- **Bad**:
  ```js
  // Bypasses schema min: 0 validator on balance
  await Account.updateOne({ _id: id }, { balance: -100 });
  ```
- **Good**:
  ```js
  await Account.updateOne({ _id: id }, { balance: -100 }, { runValidators: true });
  ```

---

## 13. JWT Expiry, "none" Algorithm, and Secret Storage
- **Signal**: Accepting JWTs without verifying the signature algorithm, omitting `expiresIn`, or using fallback secrets.
- **Bad**:
  ```js
  const token = jwt.sign(payload, process.env.SECRET || "secret"); // Static weak secret
  ```
- **Good**:
  ```js
  if (!process.env.JWT_SECRET) throw new Error("JWT_SECRET missing");
  const token = jwt.sign(payload, process.env.JWT_SECRET, { algorithm: "HS256", expiresIn: "15m" });
  ```

---

## 14. Bcrypt Work Factor and Timing Attacks
- **Signal**: Using bcrypt rounds lower than 10, or comparing password strings directly with `===`.
- **Bad**:
  ```js
  const hash = await bcrypt.hash(password, 4); // Inadequate work factor
  if (user.passwordHash === hash) grant(); // Vulnerable to timing attack
  ```
- **Good**:
  ```js
  const hash = await bcrypt.hash(password, 12);
  const match = await bcrypt.compare(password, user.passwordHash);
  ```

---

## 15. Permissive Credentialed CORS
- **Signal**: Setting `Access-Control-Allow-Origin: *` while enabling `Access-Control-Allow-Credentials: true`.
- **Bad**:
  ```js
  app.use(cors({ origin: "*", credentials: true })); // Insecure reflection or browser block
  ```
- **Good**:
  ```js
  const allowed = ["https://app.example.com"];
  app.use(cors({
    origin: (origin, cb) => cb(null, allowed.includes(origin) ? origin : false),
    credentials: true
  }));
  ```

---

## 16. Insecure Cookie Flags
- **Signal**: Setting authentication cookies without `httpOnly: true`, `secure: true`, or strict `sameSite`.
- **Bad**:
  ```js
  res.cookie("session", id); // Accessible to JavaScript via document.cookie
  ```
- **Good**:
  ```js
  res.cookie("session", id, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax"
  });
  ```

---

## 17. Missing Helmet Security Headers and Rate Limits
- **Signal**: Exposing Express API servers without `helmet()` and rate-limiting middleware.
- **Bad**:
  ```js
  const app = express(); // Missing security headers; X-Powered-By exposed
  ```
- **Good**:
  ```js
  import helmet from "helmet";
  import rateLimit from "express-rate-limit";
  const app = express();
  app.use(helmet());
  app.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100 }));
  ```

---

## 18. Prototype Pollution
- **Signal**: Merging untrusted JSON objects recursively into target objects without filtering `__proto__`, `constructor`, or `prototype`.
- **Bad**:
  ```js
  function merge(target, src) {
    for (let key in src) target[key] = src[key]; // Pollutes Object.prototype
  }
  ```
- **Good**:
  ```js
  function mergeSafe(target, src) {
    for (let key of Object.keys(src)) {
      if (key === "__proto__" || key === "constructor" || key === "prototype") continue;
      target[key] = src[key];
    }
  }
  ```

---

## 19. Regular Expression Denial of Service (ReDoS)
- **Signal**: Evaluating regular expressions with nested quantifiers (e.g., `(a+)+$`) on untrusted strings.
- **Bad**:
  ```js
  const emailRegex = /^([a-zA-Z0-9_.-]+)+@([a-zA-Z0-9_.-]+)+$/;
  emailRegex.test(userInput); // Exponential backtracking hangs event loop
  ```
- **Good**:
  ```js
  import validator from "validator";
  validator.isEmail(userInput); // Safe linear parsing
  ```

---

## 20. Path Traversal in sendFile and Filesystem Operations
- **Signal**: Using unsanitized parameters in `res.sendFile` or `fs.createReadStream`.
- **Bad**:
  ```js
  app.get("/files", (req, res) => {
    res.sendFile(path.join(__dirname, "public", req.query.file)); // Allows ../ escaping
  });
  ```
- **Good**:
  ```js
  app.get("/files", (req, res) => {
    const safePath = path.resolve(__dirname, "public", path.basename(req.query.file));
    res.sendFile(safePath);
  });
  ```

---

## 21. Child Process Execution with User Input
- **Signal**: Passing user-supplied strings directly to `child_process.exec` or shell options.
- **Bad**:
  ```js
  exec(`git checkout ${req.query.branch}`); // Command injection via ; or &&
  ```
- **Good**:
  ```js
  execFile("git", ["checkout", req.query.branch]); // Argument vector execution
  ```
