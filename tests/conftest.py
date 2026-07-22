"""Shared pytest fixtures. Generates synthetic files once per session so tests
run anywhere without depending on external sample data."""
import sys
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# src layout: prefer the installed (editable) package, fall back to src/ for
# running tests without an install.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from transcripe.core import selftest  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", default=False,
                     help="Include slow tests (transcription pipeline, model downloads)")


def pytest_configure(config):
    # Exposed to test modules that build parametrized cases at collection time.
    if config.getoption("--slow"):
        os.environ["TRANSCRIPE_TEST_SLOW"] = "1"


@pytest.fixture(scope="session")
def fixtures():
    d = Path(tempfile.mkdtemp(prefix="transcripe_tests_"))
    fx = selftest.generate_fixtures(d)
    yield fx
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def nullconsole():
    return selftest.NULL
