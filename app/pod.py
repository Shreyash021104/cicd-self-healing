"""A "pod" is one running instance of the sample service. The controller talks to
pods through a small interface so its rollout/rollback logic can be tested with
fast, deterministic FakePods and run for real with RealPods (subprocesses).

  ready() — readiness probe (GET /health 200): may the pod take traffic?
  alive() — liveness probe: is it still up?
  smoke() — critical-path check (GET /work 200): does the business path work?
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Protocol


class Pod(Protocol):
    version: str

    def ready(self) -> bool: ...
    def alive(self) -> bool: ...
    def smoke(self) -> bool: ...
    def stop(self) -> None: ...


class RealPod:
    def __init__(self, version: str, port: int, broken_health: bool = False,
                 broken_work: bool = False):
        self.version = version
        self.port = port
        env = {**os.environ, "VERSION": version,
               "BROKEN_HEALTH": "1" if broken_health else "",
               "BROKEN_WORK": "1" if broken_work else ""}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.service:app",
             "--host", "127.0.0.1", "--port", str(port), "--log-level", "error"],
            env=env,
        )

    def _status(self, path: str) -> int:
        import httpx
        try:
            return httpx.get(f"http://127.0.0.1:{self.port}{path}", timeout=1).status_code
        except Exception:  # noqa: BLE001
            return 0

    def ready(self) -> bool:
        return self._status("/health") == 200

    def alive(self) -> bool:
        return self.proc.poll() is None and self.ready()

    def smoke(self) -> bool:
        return self._status("/work") == 200

    def stop(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def crash(self) -> None:
        """Hard-kill the process to simulate a runtime crash (for self-healing)."""
        self.proc.kill()


class FakePod:
    """In-process pod for tests — its probes are just booleans you control."""

    def __init__(self, version: str, ready: bool = True, work: bool = True):
        self.version = version
        self._ready = ready
        self._work = work
        self._alive = True

    def ready(self) -> bool:
        return self._alive and self._ready

    def alive(self) -> bool:
        return self._alive and self._ready

    def smoke(self) -> bool:
        return self._alive and self._work

    def stop(self) -> None:
        self._alive = False

    def crash(self) -> None:
        """Simulate a pod dying at runtime (for the self-healing test)."""
        self._alive = False


# A factory maps (version, port, broken_health, broken_work) -> Pod.
def real_pod_factory(version, port, broken_health=False, broken_work=False) -> Pod:
    return RealPod(version, port, broken_health, broken_work)


def fake_pod_factory(version, port, broken_health=False, broken_work=False) -> Pod:
    return FakePod(version, ready=not broken_health, work=not broken_work)
