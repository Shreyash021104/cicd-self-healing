"""Environment-driven configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url: str = os.getenv("DATABASE_URL", "postgres://localhost:5432/deploydb")
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8097"))

    replicas: int = int(os.getenv("REPLICAS", "3"))
    pod_base_port: int = int(os.getenv("POD_BASE_PORT", "9200"))

    # Rolling update tuning
    readiness_timeout: float = float(os.getenv("READINESS_TIMEOUT", "8"))
    readiness_interval: float = float(os.getenv("READINESS_INTERVAL", "0.3"))
    smoke_attempts: int = int(os.getenv("SMOKE_ATTEMPTS", "3"))

    # Liveness monitor
    liveness_interval: float = float(os.getenv("LIVENESS_INTERVAL", "2"))


cfg = Config()
