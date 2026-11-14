---
description: Run ClauGravity autonomous software auditing, vulnerability hunting, and PR review
---

You are invoking ClauGravity, the evidence-driven software auditor and bug hunter.

Follow the ClauGravity methodology:
1. **Map Topology**: Run `python3 scripts/map_repo.py .` to inspect entry points, frameworks, and routes.
2. **Scan Signals**: Run `python3 scripts/find_risk_patterns.py .` and `python3 scripts/run_checks.py .`.
3. **Disprove Pass**: Actively attempt to falsify each candidate lead against router guards, sanitizers, and callers.
4. **Verify Citations**: Run `python3 scripts/verify_citations.py` to guarantee zero hallucinated code lines.
5. **Report**: Deliver an evidence-backed report with root cause, trigger steps, citations, and minimal fix diffs.

Target / Instructions: $ARGUMENTS
