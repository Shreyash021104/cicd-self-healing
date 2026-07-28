# Contributing

Thanks for your interest in improving Helm!

## Getting set up

1. Install Python 3.11+ and PostgreSQL.
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements.txt pytest`
4. `python scripts/migrate.py`
5. `python scripts/devrun.py` and open http://localhost:8097

## Before opening a pull request

Run the full test suite — this is what CI runs (it needs Postgres for the audit trail):

```bash
python -m pytest -q
```

The rollout / rollback / self-healing state machine is the point of this project, so keep it
covered. The tests use **fake pods** (`app/pod.py`) so they're deterministic — new behavior should
be testable the same way, without spinning up real subprocesses.

## Guidelines

- The controller talks to replicas only through the `Pod` interface (`ready`/`alive`/`smoke`/
  `stop`). Keep it that way so the logic stays testable with fakes and runnable with real pods.
- Preserve the safety invariant: **never retire old replicas until the new set has passed both
  readiness and the smoke test.** That's what makes rollback zero-downtime.

By contributing, you agree that your contributions will be licensed under the MIT License.
