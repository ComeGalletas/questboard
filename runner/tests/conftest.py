import os
import tempfile


def pytest_configure() -> None:
    # Keep tests off the real runner state (lock file, persona digests) on a dev machine.
    os.environ["QUESTBOARD_DATA_DIR"] = tempfile.mkdtemp(prefix="questboard-test-")
