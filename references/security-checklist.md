# Security Audit Checklist

A structured, code-level vulnerability catalog for reviewing web applications and backend APIs.

---

## 1. Broken Access Control
- **Code Signals**: Route parameters (`:id`, `?tenantId=`) used directly in database lookups without checking session user ownership; admin endpoints lacking role enforcement middleware; UI hiding buttons without server-side validation; forced browsing of sequential record IDs.
- **Bad**:
  ```js
  // Insecure Direct Object Reference (IDOR)
  app.get("/api/orders/:id", requireAuth, async (req, res) => {
    const order = await Order.findById(req.params.id);
    res.json(order); // Missing check: does order.userId === req.user.id?
  });
  ```
- **Good**:
  ```js
  app.get("/api/orders/:id", requireAuth, async (req, res) => {
    const order = await Order.findOne({ _id: req.params.id, userId: req.user.id });
    if (!order) return res.status(404).json({ error: "Order not found" });
    res.json(order);
  });
  ```
- **Verification Question**: Can an authenticated user in Tenant A read, modify, or delete a resource owned by Tenant B by simply substituting the ID in the request path or payload?

---

## 2. Injection Flaws
- **Code Signals**: String concatenation, formatting, or template literals interpolating untrusted input into database queries (SQL, NoSQL), system shell commands (`exec`, `spawn`), template engines, LDAP filters, or HTTP response headers.
- **Bad**:
  ```js
  // NoSQL Operator Injection
  app.post("/api/login", async (req, res) => {
    // If req.body is { "username": "admin", "password": { "$ne": null } }
    const user = await User.findOne(req.body);
    if (user) issueToken(res, user);
  });
  ```
- **Good**:
  ```js
  app.post("/api/login", async (req, res) => {
    const username = String(req.body.username || "");
    const password = String(req.body.password || "");
    const user = await User.findOne({ username });
    if (!user || !(await bcrypt.compare(password, user.passwordHash))) {
      return res.status(401).json({ error: "Invalid credentials" });
    }
    issueToken(res, user);
  });
  ```
- **Verification Question**: Is user-supplied data ever evaluated as executable code, shell command tokens, raw query syntax, or template directives without parameterization or type enforcement?

---

## 3. Cross-Site Scripting (XSS)
- **Code Signals**: Rendering unsanitized input directly into DOM structures via `dangerouslySetInnerHTML`, `innerHTML`, `v-html`, unescaped template expressions (`{{{ }}}`), or reflection of URL query parameters directly into raw HTML responses without Content-Type or escaping.
- **Bad**:
  ```jsx
  // Unsafe DOM insertion
  function UserBio({ bioHtml }) {
    return <div dangerouslySetInnerHTML={{ __html: bioHtml }} />;
  }
  ```
- **Good**:
  ```jsx
  import DOMPurify from "dompurify";

  function UserBio({ bioHtml }) {
    const clean = DOMPurify.sanitize(bioHtml);
    return <div dangerouslySetInnerHTML={{ __html: clean }} />;
  }
  ```
- **Verification Question**: Can an adversary inject executable JavaScript strings that execute within the security context of another user browser session?

---

## 4. Cross-Site Request Forgery (CSRF)
- **Code Signals**: State-changing endpoints (`POST`, `PUT`, `DELETE`) relying exclusively on ambient browser credentials (cookies or basic auth) without requiring anti-CSRF tokens, Custom Request Headers (`X-Requested-With`), or `SameSite=Lax/Strict` cookie enforcement.
- **Bad**:
  ```js
  // Cookie session without CSRF token protection
  app.post("/api/account/transfer-funds", requireCookieAuth, async (req, res) => {
    await transfer(req.user.id, req.body.recipient, req.body.amount);
    res.json({ success: true });
  });
  ```
- **Good**:
  ```js
  // Enforcing double-submit cookie or synchronizer CSRF token
  app.post("/api/account/transfer-funds", requireCookieAuth, verifyCsrfToken, async (req, res) => {
    await transfer(req.user.id, req.body.recipient, req.body.amount);
    res.json({ success: true });
  });
  ```
- **Verification Question**: Can a malicious third-party website trigger state-altering transactions on behalf of an authenticated victim simply by issuing a cross-site HTTP request?

---

## 5. Server-Side Request Forgery (SSRF)
- **Code Signals**: Backend fetching URLs provided directly by users (webhooks, avatar imports, PDF generation, proxying) without IP resolution validation, DNS pinning, or blocking access to link-local/private ranges (`127.0.0.1`, `169.254.169.254`, `10.0.0.0/8`).
- **Bad**:
  ```js
  app.post("/api/webhook/test", async (req, res) => {
    // Allows attacking AWS/GCP metadata at 169.254.169.254 or internal services
    const response = await fetch(req.body.targetUrl);
    res.send(await response.text());
  });
  ```
- **Good**:
  ```js
  import { isSafePublicUrl } from "./security/network";

  app.post("/api/webhook/test", async (req, res) => {
    if (!await isSafePublicUrl(req.body.targetUrl)) {
      return res.status(400).json({ error: "Disallowed target address" });
    }
    const response = await fetch(req.body.targetUrl);
    res.send(await response.text());
  });
  ```
- **Verification Question**: Can a user specify a URL that forces the backend server to communicate with internal cloud metadata services, loopback interfaces, or isolated internal microservices?

---

## 6. Path Traversal
- **Code Signals**: Constructing filesystem paths using unvalidated user input (`req.params.file`, `req.query.path`) in `fs.readFile`, `res.sendFile`, or `open()`.
- **Bad**:
  ```js
  app.get("/download", (req, res) => {
    // Allows reading ../../../etc/passwd
    const filePath = path.join(__dirname, "uploads", req.query.filename);
    res.sendFile(filePath);
  });
  ```
- **Good**:
  ```js
  app.get("/download", (req, res) => {
    const safeName = path.basename(req.query.filename);
    const targetPath = path.resolve(__dirname, "uploads", safeName);
    if (!targetPath.startsWith(path.resolve(__dirname, "uploads"))) {
      return res.status(403).send("Forbidden");
    }
    res.sendFile(targetPath);
  });
  ```
- **Verification Question**: Can path sequence tokens (`..`, `%2e%2e`) escape the designated sandbox directory and read arbitrary server files?

---

## 7. Unsafe Deserialization and XXE
- **Code Signals**: Calling `pickle.loads`, `yaml.load` (without SafeLoader), `unserialize`, `JSON.parse` with revivers executing code, or XML parsers with external entity resolution enabled.
- **Bad**:
  ```python
  import pickle
  def load_session(raw_data):
      return pickle.loads(raw_data) # Arbitrary code execution via payload
  ```
- **Good**:
  ```python
  import json
  def load_session(raw_data):
      return json.loads(raw_data.decode("utf-8")) # Safe data-only serialization
  ```
- **Verification Question**: Does deserializing untrusted binary or text blobs instantiate arbitrary classes or execute constructors?

---

## 8. Authentication and Session Flaws
- **Code Signals**: JWTs with `alg: "none"`, missing expiration checks (`expiresIn`), static fallback secrets (`process.env.JWT_SECRET || "default_secret"`), weak password hashing (MD5, plain SHA), or absence of brute-force rate limits on login/reset endpoints.
- **Bad**:
  ```js
  const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET || "supersecret123");
  // Missing expiration and fallback secret committed in source!
  ```
- **Good**:
  ```js
  if (!process.env.JWT_SECRET || process.env.JWT_SECRET.length < 32) {
    throw new Error("Fatal: JWT_SECRET environment variable is missing or insecure");
  }
  const token = jwt.sign({ userId: user._id }, process.env.JWT_SECRET, {
    algorithm: "HS256",
    expiresIn: "1h"
  });
  ```
- **Verification Question**: Can an attacker forge valid tokens, brute-force credentials without rate limits, or leverage default secrets?

---

## 9. Hardcoded Secrets in Code, Logs, and Client Bundles
- **Code Signals**: AWS credentials, private keys, API tokens, database connection strings with passwords hard-coded in source or exposed via frontend environment prefixes (`NEXT_PUBLIC_`, `VITE_`).
- **Bad**:
  ```js
  const STRIPE_KEY = "sk_live_51ABC1234567890abcdef";
  const client = new Stripe(STRIPE_KEY);
  ```
- **Good**:
  ```js
  const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;
  if (!STRIPE_KEY) throw new Error("STRIPE_SECRET_KEY is required");
  const client = new Stripe(STRIPE_KEY);
  ```
- **Verification Question**: Are API keys, production certificates, or cryptographic secrets committed to repository source control or leaked into frontend builds?

---

## 10. Insecure Cryptography
- **Code Signals**: Using `Math.random()` to generate cryptographic nonces, password reset tokens, or session IDs; utilizing deprecated algorithms (MD5, SHA1, DES) or AES in ECB mode without authenticated encryption (GCM).
- **Bad**:
  ```js
  const resetToken = Math.random().toString(36).substring(2); // Predictable pseudo-random
  ```
- **Good**:
  ```js
  import crypto from "crypto";
  const resetToken = crypto.randomBytes(32).toString("hex"); // Cryptographically secure
  ```
- **Verification Question**: Are security-critical random tokens or encryption schemes reliant on predictable seeds or obsolete ciphers?

---

## 11. Unrestricted File Uploads
- **Code Signals**: Accepting uploaded files without validating extensions against strict allowlists, validating MIME types strictly from client headers, or writing uploads directly into publicly executable directories.
- **Bad**:
  ```js
  app.post("/upload", upload.single("avatar"), (req, res) => {
    fs.renameSync(req.file.path, `./public/avatars/${req.file.originalname}`);
  });
  ```
- **Good**:
  ```js
  const ALLOWED_EXT = new Set([".png", ".jpg", ".jpeg"]);
  app.post("/upload", upload.single("avatar"), (req, res) => {
    const ext = path.extname(req.file.originalname).toLowerCase();
    if (!ALLOWED_EXT.has(ext)) return res.status(400).send("Invalid file type");
    const safeName = `${crypto.randomUUID()}${ext}`;
    fs.copyFileSync(req.file.path, path.join("/secure/storage", safeName));
    res.json({ id: safeName });
  });
  ```
- **Verification Question**: Can a user upload an executable `.php`, `.jsp`, or `.html` file that is directly served by the webserver?

---

## 12. Permissive CORS, Cookie Flags, and Security Headers
- **Code Signals**: `Access-Control-Allow-Origin: *` paired with `Access-Control-Allow-Credentials: true`; cookies missing `HttpOnly`, `Secure`, or `SameSite`; missing security headers (HSTS, CSP, X-Frame-Options).
- **Bad**:
  ```js
  app.use(cors({ origin: "*", credentials: true })); // Invalid spec or exploitable reflection
  res.cookie("auth_token", token); // Missing HttpOnly and Secure flags
  ```
- **Good**:
  ```js
  app.use(cors({ origin: "https://app.example.com", credentials: true }));
  res.cookie("auth_token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax"
  });
  ```
- **Verification Question**: Can third-party origins read authenticated API responses or steal session cookies via client-side scripts?

---

## 13. Vulnerable Dependencies and Supply Chain
- **Code Signals**: Unpinned wildcards (`"*"`, `"latest"`) in package manifests; packages known to have critical unpatched CVEs; post-install scripts pulling untrusted binaries.
- **Bad**:
  ```json
  "dependencies": {
    "express": "*",
    "lodash": "4.17.4"
  }
  ```
- **Good**:
  ```json
  "dependencies": {
    "express": "^4.21.1",
    "lodash": "^4.17.21"
  }
  ```
- **Verification Question**: Are vulnerable third-party components introduced without version locking or integrity checksums?

---

## 14. Sensitive Logging and Information Disclosure
- **Code Signals**: Passing full request bodies containing passwords, credit card numbers, or auth tokens directly to logger calls; returning full stack traces to clients in production errors.
- **Bad**:
  ```js
  app.post("/login", (req, res) => {
    logger.info("Login attempt payload", req.body); // Leaks plaintext password to log files
  });
  ```
- **Good**:
  ```js
  app.post("/login", (req, res) => {
    logger.info("Login attempt for user", { username: req.body.username });
  });
  ```
- **Verification Question**: Do application logs, APM traces, or error responses store unredacted secrets or credentials?

---

## 15. Mass Assignment
- **Code Signals**: Directly passing `req.body` into database create, update, or find methods without an explicit field allowlist.
- **Bad**:
  ```js
  app.put("/api/users/profile", requireAuth, async (req, res) => {
    // Attacker sends { role: "admin", isVerified: true }
    await User.findByIdAndUpdate(req.user.id, req.body);
    res.json({ success: true });
  });
  ```
- **Good**:
  ```js
  app.put("/api/users/profile", requireAuth, async (req, res) => {
    const { displayName, avatarUrl } = req.body;
    await User.findByIdAndUpdate(req.user.id, { displayName, avatarUrl }, { runValidators: true });
    res.json({ success: true });
  });
  ```
- **Verification Question**: Can an attacker overwrite sensitive metadata fields (roles, account balance, tenant ID) via extraneous JSON properties?

---

## 16. Open Redirects
- **Code Signals**: Redirecting users to a URL provided directly in request query parameters without validating against an allowed domain list.
- **Bad**:
  ```js
  app.get("/logout", (req, res) => {
    res.redirect(req.query.returnUrl); // Attacker redirects to malicious phishing site
  });
  ```
- **Good**:
  ```js
  app.get("/logout", (req, res) => {
    const target = req.query.returnUrl || "/";
    if (target.startsWith("/") && !target.startsWith("//")) {
      return res.redirect(target);
    }
    res.redirect("/");
  });
  ```
- **Verification Question**: Can the endpoint be manipulated into serving as an open redirector for phishing campaigns?

---

## 17. Business Logic Race Conditions
- **Code Signals**: Check-then-act sequences where balance checks or coupon eligibility checks occur before non-atomic updates.
- **Bad**:
  ```js
  // Concurrent requests can redeem coupon multiple times
  const coupon = await Coupon.findById(couponId);
  if (coupon.usesLeft > 0) {
    await applyDiscount(order);
    coupon.usesLeft -= 1;
    await coupon.save();
  }
  ```
- **Good**:
  ```js
  // Atomic conditional update
  const updated = await Coupon.findOneAndUpdate(
    { _id: couponId, usesLeft: { $gt: 0 } },
    { $inc: { usesLeft: -1 } },
    { new: true }
  );
  if (!updated) throw new Error("Coupon exhausted");
  await applyDiscount(order);
  ```
- **Verification Question**: Can parallel requests duplicate financial credit, reuse single-use promo codes, or bypass rate limits?
