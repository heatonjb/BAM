"""Pytest bridge for the script-style ``check()`` harnesses.

The ``tests_*.py`` files are written as runnable scripts: they execute at import
time and record every assertion as a ``(label, ok, detail)`` tuple in a
module-level ``RECORDS`` list. This hook turns each recorded assertion into its
own pytest test, so a single broken behaviour fails *by name* instead of
collapsing the whole file into one opaque red result.

Standalone execution is preserved — ``python tests_montecarlo.py`` still prints
its human-readable report and exits non-zero on failure.
"""

from __future__ import annotations

import pytest


def pytest_generate_tests(metafunc):
    if "case" not in metafunc.fixturenames:
        return

    module = getattr(metafunc, "module", None)
    if module is None:
        return

    # Modules whose checks live inside a main() rather than at import time
    # expose ``_HARNESS_MAIN``; run it exactly once to populate RECORDS.
    if not getattr(module, "_HARNESS_READY", False):
        runner = getattr(module, "_HARNESS_MAIN", None)
        if runner is not None:
            runner()
        module._HARNESS_READY = True

    records = list(getattr(module, "RECORDS", []))

    cases = [pytest.param(r, id=f"{i:02d} {r[0]}") for i, r in enumerate(records)]
    if not cases:
        # A harness that records nothing usually means it blew up before the
        # first check. Surface that as a failing test rather than a silent skip.
        cases = [pytest.param(None, id="no-checks-recorded")]

    metafunc.parametrize("case", cases)
