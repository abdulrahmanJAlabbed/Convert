"""Per-conversion suite.

Runs the full self-test matrix (one real conversion per capability) and turns
each result into an individual pytest case, so failures pinpoint exactly which
conversion broke. Conversions whose dependencies are missing are skipped.
"""
import os

import pytest

from core import selftest

# Run every conversion once at collection time; parametrize over the results.
_SLOW = os.environ.get("TRANSCRIPE_TEST_SLOW") == "1"
_RESULTS = selftest.run_all(include_slow=_SLOW)
_IDS = [f"{r.category}:{r.name}" for r in _RESULTS]


@pytest.mark.parametrize("result", _RESULTS, ids=_IDS)
def test_conversion(result):
    if result.status == "skip":
        pytest.skip(result.detail or "dependency unavailable")
    assert result.status == "pass", f"{result.category}/{result.name} → {result.detail}"


def test_at_least_the_core_conversions_ran():
    names = {f"{r.category}:{r.name}": r for r in _RESULTS}
    # Data conversions are pure-Python and must always be present + passing.
    for key in ("data:csv → json", "data:csv↔json round-trip", "data:xml → json"):
        assert key in names, f"missing self-test: {key}"
        assert names[key].status == "pass", names[key].detail
