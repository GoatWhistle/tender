import math

from ..config import CHOICE_TEMPLATE, LABELS, REVISION
from ..errors import ServiceError
from .cache import ContextCache
from .interface import Runtime


class DecisionEngine:
    def __init__(self, runtime: Runtime, settings, clock=None):
        self.runtime, self.settings = runtime, settings
        kwargs = {} if clock is None else {"clock": clock}
        self.cache = ContextCache(settings, runtime.identity, **kwargs)

    def metadata(self, entry, hit):
        return {
            "id": entry.context_id,
            "reused": hit,
            "prefix_tokens": len(entry.prepared.prefix_ids),
            "retained_bytes": entry.prepared.bytes_size,
            "expires_in_seconds": max(0, math.ceil(entry.expires - self.cache.clock())),
        }

    def prepare(self, premise):
        entry = self.cache.find(premise)
        hit = entry is not None
        if entry is None:
            ids = self.runtime.prefix_ids(premise)
            if not ids or len(ids) >= self.settings.max_tokens:
                raise ServiceError("input_too_large", "Контекст не оставляет места для гипотезы")
            if len(ids) > self.settings.cache_tokens:
                raise ServiceError("context_too_large", "Контекст превышает бюджет токенов кеша")
            entry = self.cache.put(premise, self.runtime.prepare(ids))
        return {"context": self.metadata(entry, hit), "model_revision": REVISION}

    def predict(self, request, hypotheses):
        if len(hypotheses) > self.settings.max_batch:
            raise ServiceError("batch_too_large", "Число гипотез превышает OPENJEV_MAX_BATCH")
        entry = self.cache.get(request.context_id) if request.context_id else None
        premise = entry.premise if entry else request.premise
        sequences = self.runtime.encode(premise, hypotheses)
        if any(not s or len(s) > self.settings.max_tokens for s in sequences):
            raise ServiceError(
                "input_too_large",
                "Полная пара описания и гипотезы превышает OPENJEV_MAX_TOKENS",
            )
        hit = entry is not None
        if request.use_cache and entry is None:
            entry = self.cache.find(premise)
            hit = entry is not None
            if entry is None:
                # Проверить точную границу токенов до выделения GPU-состояния.
                prefix = self.runtime.prefix_ids(premise)
                self.validate_prefix(prefix, sequences)
                self.prepare(premise)
                entry = self.cache.find(premise)
        prepared = entry.prepared if entry is not None else None
        if prepared is not None:
            self.validate_prefix(prepared.prefix_ids, sequences)
        rows = []
        chunk = []
        width = 0
        for sequence in sequences:
            new_width = max(width, len(sequence))
            if chunk and (
                len(chunk) >= self.settings.microbatch
                or new_width * (len(chunk) + 1) > self.settings.microbatch_tokens
            ):
                rows.extend(self.runtime.predict(prepared, chunk))
                chunk, width = [], 0
            chunk.append(sequence)
            width = max(width, len(sequence))
        if chunk:
            rows.extend(self.runtime.predict(prepared, chunk))
        if len(rows) != len(hypotheses) or any(
            len(row) != 3
            or any(not math.isfinite(p) or p < 0 or p > 1 for p in row)
            or abs(sum(row) - 1) > 1e-4
            for row in rows
        ):
            raise RuntimeError("Модель вернула некорректные вероятности NLI")
        context = self.metadata(entry, hit) if entry is not None else None
        return rows, context

    @staticmethod
    def validate_prefix(prefix, sequences):
        if not prefix or any(
            tuple(s[: len(prefix)]) != tuple(prefix) or len(s) <= len(prefix) for s in sequences
        ):
            raise ServiceError(
                "prefix_mismatch", "Полная пара не совпадает с подготовленным префиксом токенов"
            )

    def nli(self, request):
        rows, context = self.predict(request, request.hypotheses)
        return {
            "results": [
                {
                    "hypothesis": h,
                    "label": LABELS[max(range(3), key=row.__getitem__)],
                    "probabilities": dict(zip(LABELS, row, strict=True)),
                }
                for h, row in zip(request.hypotheses, rows, strict=True)
            ],
            "context": context,
            "model_revision": REVISION,
        }

    def choice(self, request):
        # Внешние ID могут иметь произвольный или противоречащий критерию смысл.
        # В prompt передаются нейтральные метки и только явные критерии клиента.
        hypotheses = [
            CHOICE_TEMPLATE.format(instr=request.instructions, label=f"o{i}", crit=option.criterion)
            for i, option in enumerate(request.options)
        ]
        rows, context = self.predict(request, hypotheses)
        support = [row[1] for row in rows]
        total = sum(support)
        if total <= 0:
            raise RuntimeError("Все вероятности подтверждения равны нулю")
        probabilities = {o.id: p / total for o, p in zip(request.options, support, strict=True)}
        return {
            "choice": max(probabilities, key=probabilities.get),
            "probabilities": probabilities,
            "support_probabilities": {
                o.id: p for o, p in zip(request.options, support, strict=True)
            },
            "context": context,
            "model_revision": REVISION,
        }

    def close(self):
        self.cache.clear()
        self.runtime.close()

    def delete(self, context_id):
        self.cache.prune()
        if not self.cache.remove(context_id):
            raise ServiceError("context_missing", "Подготовленный контекст не существует")
