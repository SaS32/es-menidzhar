# Test setup. Run:  python -m pytest
#
# The data directory is redirected to a temp folder BEFORE anything from the
# program is imported — core/paths.py reads ES_DATA_DIR at import time. The
# real etazna.db is never touched.
import os
import sys
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="es_tests_")
os.environ["ES_DATA_DIR"] = _TMP
os.environ["ES_NO_BROWSER"] = "1"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest          # noqa: E402
import core            # noqa: E402
import core.database   # noqa: E402


def _wipe():
    for name in os.listdir(_TMP):
        path = os.path.join(_TMP, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)


@pytest.fixture
def db():
    """A brand-new empty database for every test."""
    _wipe()
    core.init_db()
    yield core
    _wipe()


@pytest.fixture
def building(db):
    """Two apartments with residents and a tariff of 10 + 5/resident + 3/dog.

    Apartment "1": 2 residents, 1 dog → 23.00
    Apartment "2": 1 resident         → 15.00
    """
    a1 = core.create_apartment("1", 1, 80, 5.0, 1, "")
    a2 = core.create_apartment("2", 1, 60, 4.0, 0, "")
    core.add_resident(a1, "Иван Иванов", "", "", "", "resident")
    core.add_resident(a1, "Мария Иванова", "", "", "", "resident")
    core.add_resident(a2, "Петър Петров", "", "", "", "resident")
    core.save_fee_settings("2025-01", 10.0, 5.0, 3.0)
    return a1, a2


@pytest.fixture
def client(db):
    import app as app_module
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def fee_of(apt_id, period):
    return next(dict(f) for f in core.get_monthly_fees(period) if f["apt_id"] == apt_id)


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)
