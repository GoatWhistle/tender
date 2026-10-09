import asyncio
import copy
import hashlib
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from openjev_service.adapter.runtime import OpenJevRuntime
from openjev_service.adapter.weights import ensure_weights
from openjev_service.config import Settings
from openjev_service.controller.api import create_app
from openjev_service.controller.schemas import ChoiceRequest, NLIRequest
from openjev_service.errors import ServiceError
from openjev_service.usecase.engine import DecisionEngine
from openjev_service.usecase.worker import GPUWorker
from pydantic import ValidationError


class FakePrepared:
    def __init__(self, prefix_ids, size=100):
        self.prefix_ids = tuple(prefix_ids)
        self.bytes_size = size
        self.state = {"kv": [1], "recurrent": [2]}
        self.released = False

    def release(self):
        self.released = True


class FakeRuntime:
    identity = "Premise: {premise}\nHypothesis: {hypothesis}"

    def __init__(self, settings=None):
        self.preparations = []
        self.forwards = []
        self.hypotheses = []
        self.closed = False
        self.mismatch = False

    def prefix_ids(self, premise):
        return tuple([1, *list(premise.encode()), 2])

    def encode(self, premise, hypotheses):
        self.hypotheses.append(list(hypotheses))
        prefix = self.prefix_ids(premise)
        if self.mismatch:
            prefix = (9, *prefix[1:])
        return [list(prefix) + list(h.encode()) for h in hypotheses]

    def prepare(self, prefix_ids):
        context = FakePrepared(prefix_ids)
        self.preparations.append(context)
        return context

    def predict(self, prepared, sequences):
        if prepared:
            branch = copy.deepcopy(prepared.state)
            branch["kv"].append(99)
            branch["recurrent"].append(99)
        self.forwards.append((prepared, copy.deepcopy(sequences), threading.get_ident()))
        return [[0.1, 0.8, 0.1] if b"red" in bytes(s[1:]) else [0.1, 0.1, 0.8] for s in sequences]

    def close(self):
        self.closed = True


class EngineTests(unittest.TestCase):
    def engine(self, **kwargs):
        settings = Settings(**kwargs)
        runtime = FakeRuntime(settings)
        engine = DecisionEngine(runtime, settings)
        return engine, runtime

    def test_cross_call_reuse_and_fresh_hypotheses(self):
        engine, runtime = self.engine()
        first = engine.nli(NLIRequest(premise="device", hypotheses=["red"]))
        second = engine.nli(NLIRequest(context_id=first["context"]["id"], hypotheses=["blue"]))
        self.assertEqual(first["results"][0]["label"], "supported")
        self.assertEqual(second["results"][0]["label"], "not_stated")
        self.assertTrue(second["context"]["reused"])
        self.assertEqual(len(runtime.preparations), 1)
        self.assertEqual(len(runtime.forwards), 2)
        self.assertEqual(runtime.preparations[0].state, {"kv": [1], "recurrent": [2]})
        full = engine.nli(NLIRequest(premise="device", hypotheses=["blue"], use_cache=False))
        self.assertEqual(full["results"], second["results"])
        self.assertIsNone(full["context"])
        self.assertIsNone(runtime.forwards[-1][0])

    def test_exact_premise_identity_changes_preparation(self):
        engine, runtime = self.engine()
        a = engine.prepare("device")
        b = engine.prepare(" device ")
        c = engine.prepare("device")
        self.assertNotEqual(a["context"]["id"], b["context"]["id"])
        self.assertTrue(c["context"]["reused"])
        self.assertEqual(len(runtime.preparations), 2)

    def test_new_choice_options_are_scored_with_neutral_labels(self):
        engine, runtime = self.engine()
        first = engine.choice(
            ChoiceRequest(
                premise="device",
                instructions="Colour?",
                options=[{"id": "blue", "criterion": "red"}, {"id": "red", "criterion": "blue"}],
            )
        )
        second = engine.choice(
            ChoiceRequest(
                context_id=first["context"]["id"],
                instructions="Other?",
                options=[{"id": "blue", "criterion": "blue"}, {"id": "red", "criterion": "red"}],
            )
        )
        self.assertEqual(first["choice"], "blue")
        self.assertEqual(second["choice"], "red")
        self.assertAlmostEqual(sum(first["probabilities"].values()), 1)
        self.assertIn("is o0: red", runtime.hypotheses[0][0])
        self.assertIn('"Other?"', runtime.hypotheses[1][0])
        self.assertEqual(len(runtime.preparations), 1)
        self.assertEqual(len(runtime.forwards), 2)

    def test_whole_batch_length_rejected_before_any_gpu_work(self):
        engine, runtime = self.engine(max_tokens=10, microbatch_tokens=20)
        with self.assertRaises(ServiceError) as caught:
            engine.nli(NLIRequest(premise="abc", hypotheses=["ok", "x" * 20]))
        self.assertEqual(caught.exception.code, "input_too_large")
        self.assertEqual(runtime.preparations, [])
        self.assertEqual(runtime.forwards, [])

    def test_batch_and_context_limits(self):
        engine, runtime = self.engine(max_batch=2, microbatch=2, max_tokens=10)
        with self.assertRaises(ServiceError) as caught:
            engine.nli(NLIRequest(premise="a", hypotheses=["a", "b", "c"]))
        self.assertEqual(caught.exception.code, "batch_too_large")
        with self.assertRaises(ServiceError):
            engine.prepare("x" * 9)
        self.assertFalse(runtime.preparations)

    def test_microbatch_limits_padded_complete_pair_tokens(self):
        engine, runtime = self.engine(max_tokens=20, microbatch=3, microbatch_tokens=20)
        engine.nli(NLIRequest(premise="a", hypotheses=["x" * 8, "x", "x", "x" * 8, "x"]))
        self.assertGreater(len(runtime.forwards), 1)
        for _, sequences, _ in runtime.forwards:
            self.assertLessEqual(len(sequences), 3)
            self.assertLessEqual(len(sequences) * max(map(len, sequences)), 20)

    def test_prefix_mismatch_rejects_before_prepare_and_continuation(self):
        engine, runtime = self.engine()
        runtime.mismatch = True
        with self.assertRaises(ServiceError) as caught:
            engine.nli(NLIRequest(premise="a", hypotheses=["red"]))
        self.assertEqual(caught.exception.code, "prefix_mismatch")
        self.assertFalse(runtime.preparations)
        runtime.mismatch = False
        context_id = engine.prepare("a")["context"]["id"]
        runtime.mismatch = True
        with self.assertRaises(ServiceError):
            engine.nli(NLIRequest(context_id=context_id, hypotheses=["red"]))
        self.assertFalse(runtime.forwards)

    def test_lru_eviction_and_shutdown_release(self):
        engine, runtime = self.engine(cache_entries=2)
        a, b = engine.prepare("a"), engine.prepare("b")
        engine.prepare("a")
        engine.prepare("c")
        self.assertFalse(runtime.preparations[0].released)
        self.assertTrue(runtime.preparations[1].released)
        with self.assertRaises(ServiceError):
            engine.cache.get(b["context"]["id"])
        self.assertEqual(engine.cache.get(a["context"]["id"]).premise, "a")
        engine.close()
        self.assertTrue(all(p.released for p in runtime.preparations))
        self.assertTrue(runtime.closed)
        self.assertEqual(engine.cache.bytes, 0)

    def test_byte_and_token_budget_and_absolute_ttl(self):
        settings = Settings(cache_bytes=150, cache_tokens=5, cache_ttl=10)
        runtime = FakeRuntime()
        now = [0]
        engine = DecisionEngine(runtime, settings, clock=lambda: now[0])
        a = engine.prepare("a")
        engine.prepare("b")
        self.assertTrue(runtime.preparations[0].released)
        now[0] = 9
        b = engine.prepare("b")
        self.assertEqual(b["context"]["expires_in_seconds"], 1)
        now[0] = 10
        with self.assertRaises(ServiceError) as caught:
            engine.cache.get(b["context"]["id"])
        self.assertEqual(caught.exception.code, "context_missing")
        self.assertEqual(engine.cache.tokens, 0)
        self.assertTrue(runtime.preparations[1].released)
        self.assertNotEqual(a["context"]["id"], b["context"]["id"])
        with self.assertRaises(ServiceError):
            engine.prepare("long")
        self.assertEqual(len(runtime.preparations), 2)

    def test_single_context_exceeding_byte_budget_releases(self):
        engine, runtime = self.engine(cache_bytes=99)
        with self.assertRaises(ServiceError) as caught:
            engine.prepare("a")
        self.assertEqual(caught.exception.code, "context_too_large")
        self.assertTrue(runtime.preparations[0].released)
        self.assertFalse(engine.cache.entries)

    def test_total_prefix_token_budget_evicts_without_byte_pressure(self):
        engine, runtime = self.engine(cache_tokens=6, cache_bytes=10000)
        engine.prepare("a")
        engine.prepare("b")
        engine.prepare("c")
        self.assertEqual(engine.cache.tokens, 6)
        self.assertEqual(engine.cache.bytes, 200)
        self.assertTrue(runtime.preparations[0].released)
        self.assertFalse(runtime.preparations[1].released)


class ContractTests(unittest.TestCase):
    def test_invalid_schema(self):
        invalid = [
            {"hypotheses": ["a"]},
            {"premise": "a", "context_id": "a" * 32, "hypotheses": ["a"]},
            {"premise": " ", "hypotheses": ["a"]},
            {"premise": "a", "hypotheses": []},
            {"premise": "a", "hypotheses": [" "]},
            {"context_id": "a" * 32, "hypotheses": ["a"], "use_cache": False},
            {"premise": "a", "hypotheses": ["a"], "unknown": True},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                NLIRequest(**values)
        with self.assertRaises(ValidationError):
            ChoiceRequest(
                premise="a",
                instructions="q",
                options=[{"id": "same", "criterion": "a"}, {"id": "same", "criterion": "b"}],
            )

    def wait_ready(self, client):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if client.get("/health/ready").status_code == 200:
                return
            time.sleep(0.005)
        self.fail("Fake runtime did not become ready")

    def test_http_nli_choice_context_delete_and_errors(self):
        runtime = FakeRuntime()
        with TestClient(create_app(Settings(), lambda _: runtime)) as client:
            self.wait_ready(client)
            prepared = client.post("/v1/contexts", json={"premise": "device"})
            self.assertEqual(prepared.status_code, 200)
            context_id = prepared.json()["context"]["id"]
            r = client.post(
                "/v1/nli", json={"context_id": context_id, "hypotheses": ["red", "blue"]}
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(
                set(r.json()["results"][0]["probabilities"]),
                {"contradicted", "supported", "not_stated"},
            )
            r = client.post(
                "/v1/choice",
                json={
                    "context_id": context_id,
                    "instructions": "Colour?",
                    "options": [{"id": "a", "criterion": "red"}, {"id": "b", "criterion": "blue"}],
                },
            )
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["choice"], "a")
            self.assertEqual(client.delete(f"/v1/contexts/{context_id}").status_code, 204)
            r = client.post("/v1/nli", json={"context_id": context_id, "hypotheses": ["red"]})
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.json()["error"]["code"], "context_missing")
            self.assertEqual(client.post("/v1/nli", json={"premise": "a"}).status_code, 422)
        self.assertTrue(runtime.closed)
        self.assertEqual(len({call[2] for call in runtime.forwards}), 1)

    def test_body_limit(self):
        with TestClient(create_app(Settings(max_body_bytes=32), FakeRuntime)) as client:
            self.wait_ready(client)
            r = client.post("/v1/nli", content=b"x" * 33)
            self.assertEqual(r.status_code, 413)
            self.assertEqual(r.json()["error"]["code"], "body_too_large")

    def test_failed_load_remains_live_but_unready(self):
        def fail(_):
            raise RuntimeError("Fake missing GPU")

        with TestClient(create_app(Settings(), fail)) as client:
            self.assertEqual(client.get("/health/live").status_code, 200)
            self.assertEqual(client.get("/health/ready").status_code, 503)
            self.assertEqual(
                client.post("/v1/nli", json={"premise": "a", "hypotheses": ["b"]}).status_code, 503
            )


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def until(self, predicate):
        async with asyncio.timeout(3):
            while not predicate():
                await asyncio.sleep(0.005)

    async def test_bounded_queue_cancellation_and_single_gpu_owner(self):
        settings = Settings(queue_size=1)
        runtime = FakeRuntime()
        gate = threading.Event()
        entered = threading.Event()
        predict = runtime.predict

        def block(prepared, sequences):
            entered.set()
            gate.wait(3)
            return predict(prepared, sequences)

        runtime.predict = block
        worker = GPUWorker(settings, lambda _: runtime)
        worker.start()
        await self.until(lambda: worker.state == "ready")
        request = NLIRequest(premise="a", hypotheses=["red"])
        first = asyncio.create_task(worker.submit("nli", request))
        await self.until(entered.is_set)
        waiting = asyncio.create_task(worker.submit("nli", request))
        await self.until(worker.queue.full)
        with self.assertRaises(ServiceError) as caught:
            await worker.submit("nli", request)
        self.assertEqual(caught.exception.code, "queue_full")
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await waiting
        gate.set()
        await first
        await worker.queue.join()
        self.assertEqual(len(runtime.forwards), 1)
        await worker.stop()
        self.assertTrue(runtime.closed)
        self.assertTrue(runtime.preparations[0].released)

    async def test_timeout_does_not_admit_parallel_work(self):
        runtime = FakeRuntime()
        gate = threading.Event()
        entered = threading.Event()
        predict = runtime.predict

        def block(prepared, sequences):
            entered.set()
            gate.wait(3)
            return predict(prepared, sequences)

        runtime.predict = block
        worker = GPUWorker(Settings(request_timeout=1, queue_size=1), lambda _: runtime)
        worker.start()
        await self.until(lambda: worker.state == "ready")
        with self.assertRaises(ServiceError) as caught:
            await worker.submit("nli", NLIRequest(premise="a", hypotheses=["red"]))
        self.assertEqual(caught.exception.code, "request_timeout")
        self.assertTrue(worker.active)
        self.assertTrue(entered.is_set())
        gate.set()
        await worker.queue.join()
        await worker.stop()

    async def test_runtime_failure_releases_cache_and_marks_worker_unready(self):
        runtime = FakeRuntime()

        def fail(prepared, sequences):
            raise RuntimeError("Fake CUDA failure")

        runtime.predict = fail
        worker = GPUWorker(Settings(), lambda _: runtime)
        worker.start()
        await self.until(lambda: worker.state == "ready")
        with (
            self.assertLogs("openjev_service.usecase.worker", level="ERROR"),
            self.assertRaises(ServiceError) as caught,
        ):
            await worker.submit("nli", NLIRequest(premise="a", hypotheses=["red"]))
        self.assertEqual(caught.exception.code, "inference_failed")
        self.assertEqual(worker.state, "failed")
        self.assertTrue(runtime.preparations[0].released)
        with self.assertRaises(ServiceError) as caught:
            await worker.submit("prepare", "b")
        self.assertEqual(caught.exception.code, "not_ready")
        await worker.stop()


class LoaderTests(unittest.TestCase):
    def test_no_cuda_rejected_before_model_directory_or_download(self):
        fake_torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with tempfile.TemporaryDirectory() as directory:
            model_dir = Path(directory) / "model"
            with (
                patch.dict("sys.modules", {"torch": fake_torch}),
                self.assertRaisesRegex(RuntimeError, "выполнение на CPU запрещено"),
            ):
                OpenJevRuntime(Settings(model_dir=str(model_dir)))
            self.assertFalse(model_dir.exists())

    def test_pinned_urls_verified_reuse_and_corruption(self):
        content = b"pinned artifact"
        manifest = {
            "model/file": {"size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        }
        calls = []

        def download(url, path):
            calls.append(url)
            Path(path).write_bytes(content)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ensure_weights(root, manifest=manifest, download=download)
            ensure_weights(root, manifest=manifest, download=download)
            self.assertEqual(len(calls), 1)
            self.assertIn("a20448012c213128955ca0c693e7c943865cab77", calls[0])
            (root / "model/file").write_bytes(b"corrupt")
            with self.assertRaises(RuntimeError):
                ensure_weights(root, offline=True, manifest=manifest)
            ensure_weights(root, manifest=manifest, download=download)
            self.assertEqual(len(calls), 2)

    def test_checksum_failure_is_atomic_and_removes_partial(self):
        manifest = {"file": {"size": 3, "sha256": hashlib.sha256(b"yes").hexdigest()}}

        def download(url, path):
            Path(path).write_bytes(b"bad")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "Контрольная сумма не совпадает"):
                ensure_weights(root, manifest=manifest, download=download)
            self.assertFalse((root / "file").exists())
            self.assertFalse((root / "file.partial").exists())


if __name__ == "__main__":
    unittest.main()
