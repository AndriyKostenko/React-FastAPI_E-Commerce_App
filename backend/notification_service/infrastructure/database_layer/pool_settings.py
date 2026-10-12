from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PoolSettings:
    """
    SQLAlchemy pool settings for one process's engine.

    ``pool_size + max_overflow`` is the most connections this process may hold.
    The numbers are set per process, not derived: an API process keeps the
    service's defaults (DB_POOL_SIZE / DB_MAX_OVERFLOW in its settings), while
    compose and dev.sh give background processes smaller ones. The sum over
    every process of every service must fit Postgres's max_connections;
    ``./local/dev.sh pool-budget`` checks docker-compose.yml against it.

    A pool cannot be sized from the CPU count: the gunicorn worker count is set
    by GUNICORN_WORKERS, not by a formula, and inside a container
    ``os.cpu_count()`` reports the host's CPUs rather than the container's limit.
    """

    pool_size: int
    max_overflow: int
    pool_timeout: int = 5
    pool_recycle: int = 1800
    pool_pre_ping: bool = True

    def __post_init__(self) -> None:
        if self.pool_size < 1:
            raise ValueError("pool_size must be at least 1")
        if self.max_overflow < 0:
            raise ValueError("max_overflow cannot be negative")

    @property
    def max_connections(self) -> int:
        """The most connections this process's engine will open."""
        return self.pool_size + self.max_overflow

    def as_dict(self, echo: bool = False) -> dict[str, bool | int]:
        return {
            "echo": echo,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
        }

    def describe(self) -> str:
        """Human-readable summary, logged when the engine is created."""
        return (
            f"pool_size={self.pool_size} max_overflow={self.max_overflow} "
            f"(at most {self.max_connections} connections) "
            f"pool_timeout={self.pool_timeout}s pool_recycle={self.pool_recycle}s"
        )
