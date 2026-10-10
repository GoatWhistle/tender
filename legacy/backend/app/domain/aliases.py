"""Проверенные бытовые названия группы и происхождение записи словаря."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Alias:
    group_code: str
    alias: str
    source: str
    reviewed: bool
