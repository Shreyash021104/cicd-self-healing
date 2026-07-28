import pytest

from app.config import cfg
from app.controller import Controller
from app.db import Store
from app.pod import fake_pod_factory


@pytest.fixture(scope="session")
def store():
    s = Store(cfg.database_url)
    s.migrate()
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _clean(store):
    with store.pool.connection() as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM deployments")
    yield


@pytest.fixture
def controller(store):
    # Fake pods + tiny timeouts so tests are fast and deterministic.
    return Controller(fake_pod_factory, store, replicas=3, base_port=9500,
                      readiness_timeout=0.4, readiness_interval=0.02, smoke_attempts=2)
