# Contributing to ClauGravity

Thank you for contributing to ClauGravity. We appreciate your efforts to improve codebase audits and bug hunting capabilities.

## Architecture and Guidelines

1. **Standard Library Only**: All Python scripts in `scripts/` must rely strictly on the Python 3.8+ standard library. External third-party packages are not permitted.
2. **Cross-Platform Compatibility**: Use `pathlib.Path` for all filesystem operations to ensure consistent behavior across Windows, macOS, and Linux.
3. **No Project Mutation**: ClauGravity operates in a strictly read-only mode relative to audited targets. Only `.claugravity/` within the target project may be used for working notes.

## Adding a Risk Pattern to find_risk_patterns.py

When adding a new risk pattern to `scripts/find_risk_patterns.py`:
- Add a rule dictionary containing:
  - `id`: Unique identifier (e.g., `SEC-JS-015`, `CONC-PY-005`).
  - `category`: Relevant category (`Security`, `Concurrency`, `Data/API`, `Correctness`, `Secrets`).
  - `regex`: Compiled regex or pattern string targeting the risky code pattern.
  - `languages`: List of supported file extensions (e.g., `[".js", ".ts", ".jsx", ".tsx"]`).
  - `severity_hint`: One of `Critical`, `High`, `Medium`, `Low`, or `Info`.
  - `explanation`: Clear description of why the pattern represents a potential bug or vulnerability.
- **Mandatory Fixture Test**: Every new pattern must have an accompanying test case in `tests/fixture-project/` demonstrating both detection on true positives and non-detection on safe code.

## Adding or Updating Language References

Language guidelines in `references/` provide focused, actionable signals for code auditors:
- Include a concise signal for recognizing the vulnerability or flaw.
- Provide concrete bad and good code examples.
- Include a verification checklist item or test hint.
- Keep references focused and code-centric, targeting under 400 lines per topic.

## Running the Test Suite & Fixture Self-Tests

Before opening a pull request, run the automated test suite and fixture verification:
```bash
# 1. Run all 64 automated unit & subprocess tests
python3 -m unittest tests/test_scripts.py

# 2. Verify citations against the fixture reports
python3 scripts/verify_citations.py tests/fixture-report-iteration-1.md --root tests/fixture-project
python3 scripts/verify_citations.py tests/fixture-report-iteration-2.md --root tests/fixture-project
```

## Pull Request Process

1. Create a feature branch from `main`.
2. Ensure all scripts pass syntax and standard-library compatibility checks.
3. Validate that citations verify cleanly with `scripts/verify_citations.py`.
4. Submit a pull request with a descriptive summary of changes and test evidence.
