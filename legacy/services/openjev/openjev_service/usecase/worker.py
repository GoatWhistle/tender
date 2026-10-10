import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from ..errors import ServiceError
from .engine import DecisionEngine

logger = logging.getLogger(__name__)


class GPUWorker:
    """Один поток GPU, ограниченная очередь, последовательные forward."""

    def __init__(self, settings, factory):
        self.settings, self.factory = settings, factory
        self.queue = asyncio.Queue(maxsize=settings.queue_size)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu-owner")
        self.state = "initializing"
        self.engine = None
        self.active = False
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self.run())

    async def on_owner(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(self.executor, function, *args)

    def load(self):
        return DecisionEngine(self.factory(self.settings), self.settings)

    async def run(self):
        try:
            self.engine = await self.on_owner(self.load)
            if self.state != "stopping":
                self.state = "ready"
        except Exception:
            logger.exception("Не удалось инициализировать GPU runtime")
            if self.state != "stopping":
                self.state = "failed"
        while True:
            try:
                job = await asyncio.wait_for(self.queue.get(), timeout=5)
            except TimeoutError:
                if self.engine:
                    await self.on_owner(self.engine.cache.prune)
                continue
            if job is None:
                self.queue.task_done()
                break
            method, args, future = job
            try:
                if future.cancelled():
                    continue
                if self.state != "ready":
                    raise ServiceError("not_ready", "GPU worker ещё не готов")
                self.active = True
                result = await self.on_owner(getattr(self.engine, method), *args)
                if not future.done():
                    future.set_result(result)
            except ServiceError as error:
                if not future.done():
                    future.set_exception(error)
            except Exception:
                logger.exception("GPU worker завершился с ошибкой; требуется перезапуск")
                self.state = "failed"
                await self.on_owner(self.engine.cache.clear)
                if not future.done():
                    future.set_exception(
                        ServiceError(
                            "inference_failed", "Ошибка GPU inference; требуется перезапуск worker"
                        )
                    )
            finally:
                self.active = False
                self.queue.task_done()
        if self.engine:
            await self.on_owner(self.engine.close)

    async def submit(self, method, *args):
        if self.state != "ready":
            raise ServiceError(
                "not_ready", "GPU worker загружается, недоступен или останавливается"
            )
        future = asyncio.get_running_loop().create_future()
        try:
            self.queue.put_nowait((method, args, future))
        except asyncio.QueueFull:
            raise ServiceError("queue_full", "Очередь запросов GPU заполнена") from None
        try:
            return await asyncio.wait_for(asyncio.shield(future), self.settings.request_timeout)
        except TimeoutError:
            future.cancel()
            raise ServiceError(
                "request_timeout", "Превышено время ожидания и выполнения запроса GPU"
            ) from None
        except asyncio.CancelledError:
            future.cancel()
            raise

    async def stop(self):
        self.state = "stopping"
        # Прекратить приём, отклонить очередь и завершить текущую CUDA-операцию.
        while not self.queue.empty():
            _, _, future = self.queue.get_nowait()
            if not future.done():
                future.set_exception(ServiceError("stopping", "GPU worker останавливается"))
            self.queue.task_done()
        await self.queue.put(None)
        await self.task
        self.executor.shutdown(wait=True)
        self.state = "stopped"
