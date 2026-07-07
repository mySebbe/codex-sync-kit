# Contributing

Use small pull requests and include tests for behavior changes.

Before submitting:

```powershell
python -m pytest
python -m ruff check .
python -m build --sdist --wheel
```

Do not add new sync include rules for credentials, logs, sessions, or live database files without a matching security review.
