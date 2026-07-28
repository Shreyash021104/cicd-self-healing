"""The rollout / rollback / self-healing state machine, tested with fake pods."""


def test_successful_rollout(controller):
    r = controller.deploy("v1")
    assert r["status"] == "deployed"
    assert controller.current_version == "v1"
    assert len(controller.pods) == 3
    assert controller.status()["healthy"] == 3


def test_readiness_failure_rolls_back_keeping_previous(controller):
    controller.deploy("v1")
    v1_pods = controller.pods

    # v2 never becomes ready → readiness gate never opens → rollback.
    r = controller.deploy("v2", broken_health=True)
    assert r["status"] == "rolled_back"
    assert "readiness" in r["note"]
    # Still serving v1, and the ORIGINAL v1 pods were never touched (zero downtime).
    assert controller.current_version == "v1"
    assert controller.pods is v1_pods
    assert all(p.alive() for p in controller.pods)


def test_smoke_failure_rolls_back(controller):
    controller.deploy("v1")

    # v2 is READY (health ok) but its critical path is broken → smoke test catches it.
    r = controller.deploy("v2", broken_work=True)
    assert r["status"] == "rolled_back"
    assert "smoke" in r["note"]
    assert controller.current_version == "v1"          # rolled back
    assert all(p.smoke() for p in controller.pods)     # v1 critical path still works


def test_good_upgrade_switches_version(controller):
    controller.deploy("v1")
    old = controller.pods
    r = controller.deploy("v2")
    assert r["status"] == "deployed"
    assert controller.current_version == "v2"
    assert all(not p.alive() for p in old)             # old pods retired
    assert all(p.version == "v2" for p in controller.pods)


def test_initial_deploy_failure_leaves_nothing_running(controller):
    r = controller.deploy("v1", broken_work=True)
    assert r["status"] == "rolled_back"
    assert controller.current_version is None
    assert controller.pods == []


def test_self_healing_restarts_a_dead_pod(controller):
    controller.deploy("v1")
    # Kill one pod at runtime (simulate a crash).
    controller.pods[1].crash()
    assert controller.status()["healthy"] == 2

    healed = controller.monitor_once()
    assert healed == 1
    assert controller.status()["healthy"] == 3         # back to full health
    assert all(p.version == "v1" for p in controller.pods)


def test_history_and_events_recorded(controller, store):
    controller.deploy("v1")
    controller.deploy("v2", broken_work=True)          # rolled back
    hist = store.history()
    statuses = [h["status"] for h in hist]
    assert "deployed" in statuses and "rolled_back" in statuses
    msgs = " ".join(e["message"] for e in store.recent_events())
    assert "smoke test" in msgs.lower()
