"""The deployment controller — a mini-Kubernetes rollout engine.

It performs a **rolling update**: bring up new-version pods one at a time, gating
each on a **readiness probe**, while the OLD pods keep serving. Only once all new
pods are ready does it run a **post-deploy smoke test** against the critical path.
If readiness times out OR the smoke test fails, it **rolls back automatically** —
it simply discards the new pods and keeps the old ones running, so there's no
downtime and no bad version ever takes traffic. A separate **liveness monitor**
restarts any pod that dies at runtime (self-healing).

This is the orchestration logic Kubernetes gives you (rollout, readiness gating,
undo on failed health checks); here it runs over local process "pods" so it works
without a cluster. The state machine is identical.
"""
from __future__ import annotations

import threading
import time

from .db import Store
from .pod import Pod


class Controller:
    def __init__(self, factory, store: Store, replicas: int = 3, base_port: int = 9200,
                 readiness_timeout: float = 8, readiness_interval: float = 0.3,
                 smoke_attempts: int = 3):
        self.factory = factory
        self.store = store
        self.replicas = replicas
        self.readiness_timeout = readiness_timeout
        self.readiness_interval = readiness_interval
        self.smoke_attempts = smoke_attempts

        self.current_version: str | None = None
        self.current_flags: tuple[bool, bool] = (False, False)
        self.pods: list[Pod] = []
        self._port = base_port
        self.lock = threading.RLock()

    def _alloc_port(self) -> int:
        self._port += 1
        return self._port

    def _wait_ready(self, pod: Pod) -> bool:
        deadline = time.time() + self.readiness_timeout
        while time.time() < deadline:
            if pod.ready():
                return True
            time.sleep(self.readiness_interval)
        return False

    def _smoke(self, pods: list[Pod]) -> bool:
        for _ in range(self.smoke_attempts):
            if all(p.smoke() for p in pods):
                return True
            time.sleep(self.readiness_interval)
        return False

    def deploy(self, version: str, *, broken_health: bool = False, broken_work: bool = False,
               strategy: str = "rolling") -> dict:
        with self.lock:
            old_pods = self.pods
            dep_id = self.store.start_deploy(version, strategy)
            self.store.event(dep_id, f"rolling out {version} ({self.replicas} replicas)")
            new_pods: list[Pod] = []

            # 1) Roll out new pods one at a time, gated on readiness. Old pods keep
            #    serving throughout, so a failed rollout means zero downtime.
            for slot in range(self.replicas):
                pod = self.factory(version, self._alloc_port(), broken_health, broken_work)
                if not self._wait_ready(pod):
                    pod.stop()
                    for p in new_pods:
                        p.stop()
                    self.store.event(dep_id, f"readiness probe FAILED on replica {slot + 1} — rolling back")
                    return self._rolled_back(dep_id, "readiness probe failed")
                new_pods.append(pod)
                self.store.event(dep_id, f"replica {slot + 1}/{self.replicas} ready")

            # 2) Post-deploy smoke test on the critical path.
            self.store.event(dep_id, "running post-deploy smoke test (/work)")
            if not self._smoke(new_pods):
                for p in new_pods:
                    p.stop()
                self.store.event(dep_id, "smoke test FAILED — critical path broken — rolling back")
                return self._rolled_back(dep_id, "smoke test failed")

            # 3) Success: retire the old pods and switch traffic to the new set.
            for p in old_pods:
                try:
                    p.stop()
                except Exception:  # noqa: BLE001
                    pass
            self.pods = new_pods
            self.current_version = version
            self.current_flags = (broken_health, broken_work)
            self.store.event(dep_id, f"{version} healthy — deploy succeeded")
            return self.store.finish_deploy(dep_id, "deployed", "healthy")

    def _rolled_back(self, dep_id: int, reason: str) -> dict:
        # New pods already stopped; the OLD pods were never touched, so we're
        # instantly back to the previous good version. Nothing to restart.
        kept = self.current_version or "nothing (initial deploy)"
        self.store.event(dep_id, f"rolled back — still serving {kept}")
        return self.store.finish_deploy(dep_id, "rolled_back", reason)

    # ── Self-healing: replace pods that die at runtime ─────────────────────
    def monitor_once(self) -> int:
        with self.lock:
            healed = 0
            for i, pod in enumerate(self.pods):
                if not pod.alive():
                    self.store.event(None, f"replica of {pod.version} is unhealthy — restarting",
                                     kind="heal")
                    try:
                        pod.stop()
                    except Exception:  # noqa: BLE001
                        pass
                    new = self.factory(pod.version, self._alloc_port(), *self.current_flags)
                    self._wait_ready(new)
                    self.pods[i] = new
                    healed += 1
            return healed

    def status(self) -> dict:
        with self.lock:
            return {
                "version": self.current_version,
                "replicas": len(self.pods),
                "healthy": sum(1 for p in self.pods if p.alive()),
                "desired": self.replicas,
            }

    def stop_all(self):
        with self.lock:
            for p in self.pods:
                try:
                    p.stop()
                except Exception:  # noqa: BLE001
                    pass
            self.pods = []
