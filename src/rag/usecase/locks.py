import asyncio


class KeyedLocks:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def __call__(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    def drop(self, key: str) -> None:
        self._locks.pop(key, None)
