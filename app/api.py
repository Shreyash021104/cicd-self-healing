"""Control-plane API + dashboard for the deployment controller. Deploy healthy or
broken builds and watch rolling updates, smoke tests, automatic rollback, and
self-healing in real time."""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import cfg
from .controller import Controller
from .db import Store
from .pod import real_pod_factory

PAGE = (Path(__file__).parent / "page.html").read_text()

_store: Store | None = None
_ctl: Controller | None = None
_version_counter = {"n": 0}
_monitor_stop = threading.Event()


def _monitor_loop():
    while not _monitor_stop.is_set():
        try:
            if _ctl:
                _ctl.monitor_once()
        except Exception:  # noqa: BLE001
            pass
        _monitor_stop.wait(cfg.liveness_interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store, _ctl
    _store = Store(cfg.database_url)
    _store.migrate()
    _ctl = Controller(real_pod_factory, _store, replicas=cfg.replicas, base_port=cfg.pod_base_port,
                      readiness_timeout=cfg.readiness_timeout, readiness_interval=cfg.readiness_interval,
                      smoke_attempts=cfg.smoke_attempts)
    t = threading.Thread(target=_monitor_loop, daemon=True)
    t.start()
    yield
    _monitor_stop.set()
    _ctl.stop_all()
    _store.close()


app = FastAPI(title="cicd-self-healing", lifespan=lifespan)


class DeployBody(BaseModel):
    broken: bool = False   # a build that passes CI but breaks the critical path at runtime


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


@app.post("/api/deploy")
def deploy(body: DeployBody):
    _version_counter["n"] += 1
    version = f"v{_version_counter['n']}"
    # A "broken" build is READY (health ok) but its critical path 500s — exactly the
    # case that passes CI and readiness yet must be caught post-deploy and rolled back.
    result = _ctl.deploy(version, broken_work=body.broken)
    return jsonable_encoder(result)


@app.post("/api/crash")
def crash():
    # Kill one replica to demonstrate the liveness monitor healing it.
    with _ctl.lock:
        for p in _ctl.pods:
            if p.alive():
                p.crash()
                return {"crashed": p.version}
    return {"crashed": None}


@app.get("/api/status")
def status():
    return {"status": _ctl.status(),
            "history": jsonable_encoder(_store.history(12)),
            "events": jsonable_encoder(_store.recent_events(30))}
