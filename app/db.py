"""Postgres store for deployment history and rollout events — the audit trail the
dashboard reads and that proves what happened (deployed vs rolled back, and why)."""
from __future__ import annotations

from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  version    text NOT NULL,
  strategy   text NOT NULL DEFAULT 'rolling',
  status     text NOT NULL DEFAULT 'deploying',  -- deploying | deployed | rolled_back
  note       text,
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS events (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  deploy_id  bigint REFERENCES deployments(id) ON DELETE CASCADE,
  kind       text NOT NULL DEFAULT 'rollout',    -- rollout | heal
  message    text NOT NULL,
  ts         timestamptz NOT NULL DEFAULT now()
);
"""


class Store:
    def __init__(self, database_url: str):
        conninfo = database_url.replace("postgres://", "postgresql://", 1)
        self.pool = ConnectionPool(conninfo, min_size=1, max_size=6, open=True,
                                   kwargs={"row_factory": dict_row})

    def close(self):
        self.pool.close()

    def migrate(self):
        with self.pool.connection() as conn:
            conn.execute(SCHEMA)

    def start_deploy(self, version: str, strategy: str) -> int:
        with self.pool.connection() as conn:
            return conn.execute(
                "INSERT INTO deployments (version, strategy) VALUES (%s,%s) RETURNING id",
                (version, strategy)).fetchone()["id"]

    def event(self, deploy_id: Optional[int], message: str, kind: str = "rollout"):
        with self.pool.connection() as conn:
            conn.execute("INSERT INTO events (deploy_id, kind, message) VALUES (%s,%s,%s)",
                         (deploy_id, kind, message))

    def finish_deploy(self, deploy_id: int, status: str, note: str) -> dict:
        with self.pool.connection() as conn:
            return conn.execute(
                """UPDATE deployments SET status=%s, note=%s, finished_at=now()
                   WHERE id=%s RETURNING *""", (status, note, deploy_id)).fetchone()

    def history(self, limit: int = 20) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                "SELECT * FROM deployments ORDER BY id DESC LIMIT %s", (limit,)).fetchall()

    def recent_events(self, limit: int = 40) -> list[dict]:
        with self.pool.connection() as conn:
            return conn.execute(
                """SELECT e.*, d.version FROM events e
                   LEFT JOIN deployments d ON d.id = e.deploy_id
                   ORDER BY e.id DESC LIMIT %s""", (limit,)).fetchall()
