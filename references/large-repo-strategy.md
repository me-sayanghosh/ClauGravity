# Large-Repository Audit Strategy

Auditing large codebases (>50,000 lines of code or >100 source files) presents severe context window and token budget constraints. This guide outlines the chunking architecture, sampling methodology, and context conservation strategies employed by ClauGravity.

---

## 1. Activation Thresholds

Chunking mode is automatically triggered when:
- Total source code exceeds **50,000 Lines of Code (LOC)**, or
- Total audit scope contains more than **100 source files**, or
- A specific module or sub-service audit is requested within an enterprise monorepo.

---

## 2. Chunking Architecture and Risk Ranking

Do not attempt to read an entire large codebase in a single pass. Instead, divide the codebase into bounded modules using `scripts/chunk_plan.py` and review them in strict risk-weighted priority order:

1. **Authentication, Session, and RBAC Services**: Identity providers, token issuance, middleware guards.
2. **Billing, Payment, and Financial Transactions**: Ledger management, Stripe/payment integrations, quota enforcement.
3. **Primary Data Models & Mutation Handlers**: Core state managers, schema definitions, write pipelines.
4. **External-Facing Ingress and Webhooks**: Public APIs, partner webhook listeners, file ingestion endpoints.
5. **Background Workers, Queues, and Schedulers**: Asynchronous job processors, BullMQ/Celery consumers.
6. **Auxiliary and Presentation Layers**: Reporting, UI views, telemetry wrappers, and internal tooling.

---

## 3. Persistent Scratchpad: .claugravity/notes.md

To maintain context across chunk reviews without bloating token usage, record progress inside `.claugravity/notes.md`:

```markdown
# ClauGravity Audit Notes

## Architecture Overview
- Tech Stack: Node.js, Express, MongoDB (Mongoose), React.
- Ingress: /api/v1 routes guarded by JWT middleware; public webhooks at /webhooks/stripe.

## Chunk Progress
- [x] Chunk 1 (Auth & Users): Verified. IDOR finding noted in user profile.
- [x] Chunk 2 (Orders & Payments): Non-atomic inventory decrement identified.
- [ ] Chunk 3 (Admin & Reports): In progress.

## Discarded Candidates
- Route /public/ping flagged for missing auth: Discarded (intentional health check).
- Math.random in Banner.jsx: Discarded (UI display shuffling).
```

---

## 4. Skip Lists (Ignoring Low-Value Artifacts)

Auditors must never burn tokens reading:
- **Generated Code**: Protocol buffer stubs (`*.pb.go`), GraphQL generated types, Prisma generated clients.
- **Vendored Dependencies**: `node_modules/`, `vendor/`, `third_party/`, `.venv/`.
- **Build Output**: `dist/`, `build/`, `.next/`, `out/`, `bundle.js`, `*.min.js`, `*.map`.
- **Lockfiles**: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.lock`, `poetry.lock`.
- **Static Assets & Media**: Images, fonts, SVGs, audio, compiled binaries.
- **Historic Migrations**: Sequential migrations older than 6 months unless actively investigating schema drift.

---

## 5. Time-Boxed Sampling and Inter-Chunk Summarization

1. **Time-Box per Chunk**: Allocate a maximum budget of reads per chunk (e.g., 5 to 15 targeted file snippets).
2. **Summarize Before Advancing**: Before moving to the next chunk, distill confirmed findings and discarded candidates into `.claugravity/notes.md`.
3. **Clear Intermediate Context**: Do not retain raw file contents in conversation memory; rely on notes and citations.

---

## 6. Honest Partial-Coverage Reporting

When token limits or project scale prevent 100% source inspection, the audit report must explicitly disclose:
- Exact list of reviewed modules and file subsets.
- Explicit list of skipped subdirectories and the technical rationale (e.g., third-party SDKs, client static assets).
- Explicit declaration of assumptions regarding uninspected layers.
