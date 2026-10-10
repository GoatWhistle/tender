import asyncio
import json
import pickle
import sys
import time
from dataclasses import dataclass, replace
from typing import Any

import aiohttp
import numpy as np

from rag.index import CODES, POSITIONS, RAW, VECTORS, VECTORS_F32
from rag.ktru import value_text
from rag.main import embed
from rag.models import Position

INSTRUCTION = "Given a product description from a supplier, retrieve the matching KTRU catalog position"
TOP_K = 20
CANDIDATES = 200


@dataclass(frozen=True, slots=True)
class Member:
    row: int
    score: float
    position: Position
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Hit:
    row: int
    score: float
    position: Position
    raw: dict[str, Any]
    members: tuple[Member, ...]

    @property
    def siblings(self) -> int:
        return len(self.members)


class Index:
    def __init__(self) -> None:
        if not VECTORS_F32.exists() or VECTORS_F32.stat().st_mtime < VECTORS.stat().st_mtime:
            np.save(VECTORS_F32, np.load(VECTORS).astype(np.float32))
        self.vectors = np.load(VECTORS_F32, mmap_mode="r")
        self.codes: list[str] = json.loads(CODES.read_text())
        with POSITIONS.open("rb") as f:
            self.positions: dict[str, Position] = pickle.load(f)
        with RAW.open("rb") as f:
            self.raw: dict[str, dict[str, Any]] = pickle.load(f)
        self.children: dict[str, list[str]] = {}
        for p in self.positions.values():
            if p.parent:
                self.children.setdefault(p.parent, []).append(p.code)

    def leaves(self, p: Position) -> list[Position]:
        group = p.parent if p.parent in self.positions else p.code
        kids = sorted(self.children.get(group, []))
        return [self.positions[c] for c in kids] or [self.positions[group]]

    def row(self, i: int) -> tuple[Position, dict[str, Any]]:
        code = self.codes[i]
        return self.positions[code], self.raw[code]

    def search(self, query_vec: list[float], k: int = TOP_K) -> list[Hit]:
        q = np.asarray(query_vec, dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = self.vectors @ q
        top = np.argpartition(-scores, CANDIDATES)[:CANDIDATES]
        top = top[np.argsort(-scores[top])]
        groups: dict[str, Hit] = {}
        for i in top:
            p, raw = self.row(int(i))
            member = Member(int(i), float(scores[i]), p, raw)
            hit = groups.get(p.name)
            if hit is None:
                if len(groups) == k:
                    continue
                groups[p.name] = Hit(member.row, member.score, p, raw, (member,))
            else:
                groups[p.name] = replace(hit, members=(*hit.members, member))
        return list(groups.values())


def expand(hit: Hit) -> list[tuple[Member, dict[str, str]]]:
    per_member = [
        {c.name: "; ".join(value_text(v) for v in c.values) for c in m.position.characteristics}
        for m in hit.members
    ]
    names = {n for chars in per_member for n in chars}
    differing = sorted(n for n in names if len({chars.get(n) for chars in per_member}) > 1)
    return [
        (m, {n: chars.get(n, "—") for n in differing})
        for m, chars in zip(hit.members, per_member, strict=True)
    ]


async def query_vector(text: str) -> list[float]:
    async with aiohttp.ClientSession() as session:
        resp = await embed(session, [f"Instruct: {INSTRUCTION}\nQuery: {text}"])
    return resp.data[0].embedding


def run() -> None:
    text = " ".join(sys.argv[1:]) or "стул офисный на колёсах"
    t0 = time.perf_counter()
    index = Index()
    t1 = time.perf_counter()
    vec = asyncio.run(query_vector(text))
    t2 = time.perf_counter()
    hits = index.search(vec)
    t3 = time.perf_counter()
    print(f"load={t1 - t0:.2f}s embed={t2 - t1:.2f}s search={(t3 - t2) * 1000:.0f}ms\n")
    for n, h in enumerate(hits, 1):
        p = h.position
        print(f"{n:2}. {h.score:.3f} [{h.row}] {p.code} {p.name} (вариантов: {h.siblings})")
        print(f"    ОКПД2 {p.okpd2} {p.okpd2_name}")
        for c in p.characteristics:
            if c.required:
                values = "; ".join(t for t in (value_text(v) for v in c.values[:5]) if t)
                print(f"    * {c.name}: {values}")
