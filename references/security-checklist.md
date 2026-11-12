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
