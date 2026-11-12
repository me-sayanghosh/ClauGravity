# ClauGravity Fixture Audit Self-Test Results

This document records the empirical results, detection metrics, and improvement iterations of ClauGravity evaluated against `tests/fixture-project/`.

---

## Iteration 1: script signals

### Raw Lead Metrics
- **Total Automated Leads Identified:** 7
- **Categories Detected:** Security (4), Concurrency (1), Data/API (1), Correctness (1)
- **Decoys Flagged as Leads:** 1 (Decoy 2 flagged by `JS-SEC-UNGUARDED-ROUTE` at `src/routes/products.js:20`)

### Planted Bugs Detection via Automated Scanner (Leads)

| Bug ID | Planted Defect Description | Target File & Line | Automated Lead Flagged? | Scanner Rule ID |
| :--- | :--- | :--- | :--- | :--- |
| **B1** | Permissive Credentialed CORS | `src/server.js:15-18` | Missed by scanner | — |
| **B2** | Hardcoded Fallback JWT Secret | `src/server.js:23-27` | Missed by scanner | — |
| **B3** | NoSQL Operator Injection | `src/routes/auth.js:10` | **Yes (Lead)** | `JS-SEC-NOSQL` |
| **B4** | Stock Read-Modify-Save Race | `src/routes/orders.js:13-20` | Missed by scanner | — |
| **B5** | Missing await on DB Write | `src/routes/orders.js:42` | Missed by scanner | — |
| **B6** | Order Retrieval IDOR | `src/routes/orders.js:50-58` | Missed by scanner | — |
| **B7** | Unbounded Query in Products | `src/routes/products.js:10` | **Yes (Lead)** | `JS-DATA-UNBOUNDED-FIND` |
| **B8** | Missing Auth on Admin Route | `src/routes/admin.js:8-16` | **Yes (Lead)** | `JS-SEC-UNGUARDED-ROUTE` |
| **B9** | Swallowed Payment Error | `src/routes/payments.js:20-22` | Missed by scanner | — |
| **B10** | forEach(async) in Notifications | `src/utils/notify.js:9-12` | **Yes (Lead)** | `JS-CONC-FOREACH-ASYNC` |
| **B11** | Floating-Point Financial Math | `src/utils/pricing.js:4-15` | Missed by scanner | — |
| **B12** | Stale React Closure in Hook | `client/OrderList.jsx:8-18` | Missed by scanner | — |

*Notes on Script Signals:*
Automated scanning identified 4 of the 12 defects directly as leads. The remaining 8 defects require semantic data-flow tracing and targeted deep review (Phases 3 & 4) as prescribed by the ClauGravity two-pass audit workflow.
