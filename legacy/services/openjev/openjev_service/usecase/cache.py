import hashlib
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass

from ..config import REVISION
from ..errors import ServiceError
from .interface import PreparedContext


@dataclass
class Entry:
    context_id: str
    key: str
    premise: str
    prepared: PreparedContext
    expires: float


class ContextCache:
    """Кеш потока GPU; TTL абсолютный, попадания обновляют порядок LRU."""

    def __init__(self, settings, identity, clock=time.monotonic):
        self.settings, self.identity, self.clock = settings, identity, clock
        self.entries = OrderedDict()
        self.keys = {}
        self.bytes = self.tokens = 0

    def key(self, premise):
        return hashlib.sha256(
            (REVISION + "\0bf16/sdpa\0" + self.identity + "\0" + premise).encode()
        ).hexdigest()

    def remove(self, context_id):
        entry = self.entries.pop(context_id, None)
        if entry is None:
            return False
        del self.keys[entry.key]
        self.bytes -= entry.prepared.bytes_size
        self.tokens -= len(entry.prepared.prefix_ids)
        entry.prepared.release()
        return True

    def prune(self):
        for context_id, entry in list(self.entries.items()):
            if entry.expires <= self.clock():
                self.remove(context_id)

    def get(self, context_id):
        self.prune()
        entry = self.entries.get(context_id)
        if entry is None:
            raise ServiceError(
                "context_missing", "Подготовленный контекст истёк, вытеснен или не существует"
            )
        self.entries.move_to_end(context_id)
        return entry

    def find(self, premise):
        self.prune()
        context_id = self.keys.get(self.key(premise))
        return self.get(context_id) if context_id is not None else None

    def put(self, premise, prepared):
        size, tokens = prepared.bytes_size, len(prepared.prefix_ids)
        if size > self.settings.cache_bytes or tokens > self.settings.cache_tokens:
            prepared.release()
            raise ServiceError(
                "context_too_large",
                "Подготовленный контекст превышает бюджет байтов или токенов кеша",
            )
        self.prune()
        while self.entries and (
            len(self.entries) >= self.settings.cache_entries
            or self.bytes + size > self.settings.cache_bytes
            or self.tokens + tokens > self.settings.cache_tokens
        ):
            self.remove(next(iter(self.entries)))
        key = self.key(premise)
        context_id = uuid.uuid4().hex
        entry = Entry(context_id, key, premise, prepared, self.clock() + self.settings.cache_ttl)
        self.entries[context_id] = entry
        self.keys[key] = context_id
        self.bytes += size
        self.tokens += tokens
        return entry

    def clear(self):
        for context_id in list(self.entries):
            self.remove(context_id)
