# Workflow

- Does not rewrite or refactor code that already works; integrates new features on top of existing contracts. Confidence: 0.9
- When a required backend contract is missing, records the dependency in the report rather than inventing/implementing backend or new endpoints in a frontend task. Confidence: 0.9
- Runs the project's real quality-gate scripts (test, typecheck, lint, build, format:check, depcruise) and requires them all to pass. Confidence: 0.9
- Stops at the defined scope instead of continuing into out-of-scope features. Confidence: 0.85
- Preserves all existing i18n locales and maintains translation-key parity across them. Confidence: 0.85
- Adds tests only for the flows actually implemented and avoids chasing artificial coverage. Confidence: 0.85
- Prefers a short, structured final report covering scope, tests, quality gates, and real blockers/dependencies. Confidence: 0.8
- For the Python backend, runs pytest, ruff check, ruff format --check, mypy, alembic check, and import-linter and requires them all to pass. Confidence: 0.9
- Prefers deterministic/fake implementations over real external integrations (carrier, banking, fiscal, GIS) so results are reproducible in tests. Confidence: 0.85
- Ensures every critical business rule has a test, prioritizing business rules and critical paths over artificial coverage. Confidence: 0.85
- Prefers the smallest safe change (minimum necessary implementation), documenting limitations instead of larger refactors. Confidence: 0.85
- Works sequentially: implement → test → validate each stage before moving to the next. Confidence: 0.8
- Does not alter tests merely to make them pass; fixes the real defect and explains its impact. Confidence: 0.85
- Does not change global environment to mask failures; runs tests in an isolated environment and documents the exact command. Confidence: 0.8
