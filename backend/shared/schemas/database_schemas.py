from dataclasses import dataclass


@dataclass(frozen=True)
class PoolSettings:
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool

    def as_dict(self, echo: bool = False) -> dict[str, str | int]:
        return {
            "echo": echo,
            "pool_pre_ping": self.pool_pre_ping,
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
        }