import os
from dataclasses import dataclass, fields

REVISION = "a20448012c213128955ca0c693e7c943865cab77"
SUBFOLDER = "qwen3.5-4b-nli-v5"
LABELS = ("contradicted", "supported", "not_stated")
CHOICE_TEMPLATE = 'The answer to "{instr}" is {label}: {crit}'


@dataclass(frozen=True)
class Settings:
    model_dir: str = "/models/openjev"
    max_tokens: int = 4096
    max_batch: int = 32
    microbatch: int = 4
    microbatch_tokens: int = 16384
    queue_size: int = 8
    request_timeout: int = 120
    max_body_bytes: int = 1048576
    cache_entries: int = 8
    cache_bytes: int = 1073741824
    cache_tokens: int = 32768
    cache_ttl: int = 300

    def __post_init__(self):
        for field in fields(self):
            if field.name != "model_dir" and getattr(self, field.name) < 1:
                raise ValueError(f"OPENJEV_{field.name.upper()} должно быть положительным")
        if self.microbatch > self.max_batch:
            raise ValueError("microbatch не должен превышать max_batch")
        if self.microbatch_tokens < self.max_tokens:
            raise ValueError("microbatch_tokens должен вмещать одну полную пару max_tokens")

    @classmethod
    def from_env(cls):
        values = {}
        for field in fields(cls):
            raw = os.getenv(f"OPENJEV_{field.name.upper()}")
            if raw is not None:
                values[field.name] = raw if field.name == "model_dir" else int(raw)
        return cls(**values)
