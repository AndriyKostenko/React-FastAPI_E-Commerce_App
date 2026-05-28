import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PoolSettings:
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool

    def as_dict(self, echo: bool = False) -> dict:
        return {
            "echo": echo,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
        }

    def describe(self) -> str:
        workers = (2 * (os.cpu_count() or 1)) + 1
        total = (self.pool_size + self.max_overflow) * workers
        return (
            f"PoolSettings | workers={workers} "
            f"pool_size={self.pool_size} max_overflow={self.max_overflow} "
            f"→ max_connections_used≈{total}"
        )


class PoolSettingsCalculator:
    """
    Calculates safe SQLAlchemy connection-pool settings based on:

        workers            = (2 × cpu_count) + 1          (Gunicorn formula)
        per_service_budget = (pg_max_connections - reserved) ÷ num_db_services
        pool_size          = max(1, floor(per_service_budget ÷ workers ÷ 2))
        max_overflow       = pool_size                     (equal burst headroom)

    The ÷2 ensures (pool_size + max_overflow) × workers never exceeds the
    per-service connection budget.

    Parameters
    ----------
    pg_max_connections : int
        PostgreSQL max_connections setting (default: 100).
    reserved_connections : int
        Connections reserved for superuser/admin/monitoring (default: 5).
    num_db_services : int
        Number of microservices sharing the same Postgres instance (default: 5).
    pool_timeout : int
        Seconds to wait for a connection from the pool before raising (default: 5).
    pool_recycle : int
        Seconds before recycling a connection to prevent staleness (default: 1800).
    """

    def __init__(
        self,
        pg_max_connections: int = 100,
        reserved_connections: int = 5,
        num_db_services: int = 5,
        pool_timeout: int = 5,
        pool_recycle: int = 1800,
    ) -> None:
        self.pg_max_connections = pg_max_connections
        self.reserved_connections = reserved_connections
        self.num_db_services = num_db_services
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle

    @property
    def _cpu_count(self) -> int:
        return os.cpu_count() or 1

    @property
    def workers(self) -> int:
        return (2 * self._cpu_count) + 1

    def calculate(self) -> PoolSettings:
        available = self.pg_max_connections - self.reserved_connections
        per_service = available / max(self.num_db_services, 1)
        # ÷2 because max_overflow == pool_size, so total slots per worker = 2×pool_size
        pool_size = max(1, math.floor(per_service / self.workers / 2))
        return PoolSettings(
            pool_size=pool_size,
            max_overflow=pool_size,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,
        )
