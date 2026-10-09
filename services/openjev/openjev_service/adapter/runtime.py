"""Официальная трёхклассовая голова с полной токенизацией и ветвлением кеша.

Torch импортируется только в потоке GPU. API и контрактные тесты не требуют
CUDA, весов или имитации рабочей модели на CPU.
"""

import copy
import importlib.util
from pathlib import Path

from ..config import SUBFOLDER
from ..errors import ServiceError
from .weights import ensure_weights


def cache_storage_bytes(cache, torch):
    objects, storages = set(), set()
    total = 0

    def walk(value):
        nonlocal total
        if id(value) in objects:
            return
        objects.add(id(value))
        if isinstance(value, torch.Tensor):
            storage = value.untyped_storage()
            identity = (str(value.device), storage.data_ptr(), storage.nbytes())
            if identity not in storages:
                storages.add(identity)
                total += storage.nbytes()
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                walk(child)
        elif hasattr(value, "__dict__"):
            for child in vars(value).values():
                walk(child)

    walk(cache)
    return total


class Prepared:
    def __init__(self, prefix_ids, cache, size):
        self.prefix_ids = tuple(prefix_ids)
        self.cache = cache
        self.bytes_size = size

    def release(self):
        self.cache = None


class OpenJevRuntime:
    def __init__(self, settings):
        import fcntl

        import torch

        self.torch = torch
        self.ce = None
        self.owner_lock = None
        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("Требуется CUDA GPU с поддержкой BF16; выполнение на CPU запрещено")
        if importlib.util.find_spec("causal_conv1d") is not None:
            raise RuntimeError("Требуется FLA-only runtime с эталонной causal convolution")
        import fla  # noqa: F401 -- прервать загрузку без требуемых GPU kernels

        root = Path(settings.model_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.owner_lock = (root / ".worker.lock").open("a")
        try:
            fcntl.flock(self.owner_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.owner_lock.close()
            raise RuntimeError(
                "Только один процесс GPU-сервиса может использовать этот том модели"
            ) from None
        try:
            self.initialize(settings)
        except Exception:
            self.close()
            raise

    def initialize(self, settings):
        torch = self.torch
        root = ensure_weights(Path(settings.model_dir))
        spec = importlib.util.spec_from_file_location(
            "_pinned_openjev", root / "modeling_openjev.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.ce = module.OpenJevCrossEncoder(
            str(root / SUBFOLDER),
            device="cuda",
            dtype=torch.bfloat16,
            bs=settings.microbatch,
            max_len=settings.max_tokens,
        )
        self.ce.model.set_attn_implementation("sdpa")
        if self.ce.model.config.get_text_config()._attn_implementation != "sdpa":
            raise RuntimeError("Требуется attention SDPA")
        if any(p.device.type != "cuda" for p in self.ce.model.parameters()):
            raise RuntimeError("Все параметры модели должны находиться на CUDA")
        self.identity = self.ce.template
        # Readiness требует прогрева полного forward и prepared continuation.
        sequences = self.encode("A device is red.", ["The device is red."])
        self.predict(None, sequences)
        prepared = self.prepare(self.prefix_ids("A device is red."))
        try:
            self.predict(prepared, sequences)
        finally:
            prepared.release()
        torch.cuda.synchronize()

    def prefix_ids(self, premise):
        text = self.ce.template.format(premise=premise.strip(), hypothesis="").rstrip()
        return tuple(self.ce.tok(text, truncation=False)["input_ids"])

    def encode(self, premise, hypotheses):
        return [
            self.ce.tok(
                self.ce.template.format(premise=premise.strip(), hypothesis=h.strip()),
                truncation=False,
            )["input_ids"]
            for h in hypotheses
        ]

    def prepare(self, prefix_ids):
        torch, ce = self.torch, self.ce
        with torch.inference_mode():
            ids = torch.tensor([prefix_ids], device=ce.device)
            positions = torch.arange(ids.shape[1], device=ce.device).unsqueeze(0)
            cache = ce.backbone(
                input_ids=ids, position_ids=positions, use_cache=True
            ).past_key_values
            if cache is None:
                raise RuntimeError("Backbone не вернул подготовленный кеш")
            return Prepared(prefix_ids, cache, cache_storage_bytes(cache, torch))

    def predict(self, prepared, sequences):
        torch, ce = self.torch, self.ce
        common = len(prepared.prefix_ids) if prepared is not None else 0
        if prepared is not None and any(
            tuple(s[:common]) != prepared.prefix_ids or len(s) <= common for s in sequences
        ):
            raise ServiceError(
                "prefix_mismatch", "Полная пара не совпадает с подготовленным префиксом токенов"
            )
        with torch.inference_mode():
            suffixes = [s[common:] for s in sequences]
            lengths = torch.tensor([len(s) for s in suffixes], device=ce.device)
            width = max(map(len, suffixes))
            ids = torch.full(
                (len(suffixes), width), ce.tok.pad_token_id, dtype=torch.long, device=ce.device
            )
            for i, suffix in enumerate(suffixes):
                ids[i, : len(suffix)] = torch.tensor(suffix, device=ce.device)
            offsets = torch.arange(width, device=ce.device).unsqueeze(0)
            valid = offsets < lengths.unsqueeze(1)
            mask = torch.cat(
                (
                    torch.ones((len(suffixes), common), dtype=torch.long, device=ce.device),
                    valid.long(),
                ),
                dim=1,
            )
            kwargs = {}
            if prepared is not None:
                # Qwen3.5 меняет attention KV, recurrent и convolution states.
                # Не продолжать удерживаемый кеш напрямую, даже при batch=1.
                cache = copy.deepcopy(prepared.cache)
                cache.reorder_cache(torch.zeros(len(suffixes), dtype=torch.long, device=ce.device))
                kwargs["past_key_values"] = cache
            positions = (common + offsets).expand(len(suffixes), -1)
            hidden = ce.backbone(
                input_ids=ids,
                attention_mask=mask,
                position_ids=positions,
                use_cache=prepared is not None,
                **kwargs,
            ).last_hidden_state
            pooled = hidden[torch.arange(len(suffixes), device=ce.device), lengths - 1]
            result = torch.softmax(ce.model.score(pooled).float(), -1).cpu().tolist()
            torch.cuda.synchronize()
            return result

    def recover(self):
        self.torch.cuda.empty_cache()

    def close(self):
        self.ce = None
        self.recover()
        if self.owner_lock is not None:
            self.owner_lock.close()
