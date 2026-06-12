"""Enable coverage measurement in CLI subprocesses during tests."""

try:
    import coverage

    coverage.process_startup()
except Exception:
    pass
