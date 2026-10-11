import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from rag.adapter.analogs import TfidfAnalogs
from rag.adapter.embeddings import OpenAIEmbeddings
from rag.adapter.ktru_zip import ZipKtruSource
from rag.adapter.llm.claude_agent import ClaudeAgentModel
from rag.adapter.llm.openai_compatible import OpenAICompatibleModel
from rag.adapter.ste_xlsx import XlsxSteSource
from rag.adapter.vector_index import MissingVectorIndex, NumpyVectorIndex
from rag.composition import Ports, Usecases, build_usecases
from rag.controller.cli import commands
from rag.controller.cli.ask import Dialog
from rag.controller.http.catalog import router as catalog_router
from rag.controller.http.errors import install_error_handlers
from rag.controller.http.health import router as health_router
from rag.controller.http.searches import router as searches_router
from rag.controller.http.sessions import router as sessions_router
from rag.domain.inference import Tier
from rag.repository.files import (
    FileCatalog,
    FileCatalogStore,
    IndexFiles,
    MissingCatalog,
    NpyVectorStore,
)
from rag.repository.memory.sessions import MemoryDiscoveries, MemorySessions
from rag.settings import Settings, load_settings
from rag.usecase.indexing import BuildAnalogs, EmbedCatalog, ParseCatalog
from rag.usecase.interface import LanguageModel


def claude_model(settings: Settings) -> LanguageModel:
    return ClaudeAgentModel(
        {Tier.FAST: settings.claude_fast_model, Tier.SMART: settings.claude_smart_model}
    )


def openai_model(settings: Settings) -> LanguageModel:
    if not settings.llm_url:
        raise SystemExit("для OpenAI-совместимой модели задайте LLM_URL")
    return OpenAICompatibleModel(
        settings.llm_url,
        {Tier.FAST: settings.llm_fast_model, Tier.SMART: settings.llm_smart_model},
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        reasoning=settings.llm_reasoning,
    )


def language_model(settings: Settings) -> LanguageModel:
    return claude_model(settings)


def embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        settings.embeddings_url,
        settings.embeddings_model,
        api_key=settings.embeddings_api_key,
        query_instruction=settings.embeddings_query_instruction,
    )


def production_usecases(settings: Settings) -> Usecases:
    files = IndexFiles(settings.data)
    ready = files.ready
    return build_usecases(
        Ports(
            llm=language_model(settings),
            embeddings=embeddings(settings),
            catalog=FileCatalog(files) if ready else MissingCatalog(),
            vectors=NumpyVectorIndex(files.vectors, files.codes, files.vectors_f32)
            if ready
            else MissingVectorIndex(),
            analogs=TfidfAnalogs(files.ste),
            sessions=MemorySessions(),
            discoveries=MemoryDiscoveries(),
        )
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        usecases = await asyncio.to_thread(production_usecases, settings)
        app.state.usecases = usecases
        warm = asyncio.create_task(asyncio.to_thread(usecases.ports.analogs.warm))
        try:
            yield
        finally:
            warm.cancel()
            await usecases.ports.embeddings.aclose()

    app = FastAPI(title="RAG КТРУ", lifespan=lifespan)
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(sessions_router)
    app.include_router(searches_router)
    return app


def _text(default: str) -> str:
    return " ".join(sys.argv[1:]) or default


async def _with_usecases(
    settings: Settings, run: Callable[[Usecases], Awaitable[None]]
) -> None:
    usecases = production_usecases(settings)
    try:
        await run(usecases)
    finally:
        await usecases.ports.embeddings.aclose()


def run_api() -> None:
    settings = load_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


def run_ask() -> None:
    text = _text("струбцина винтовая")
    asyncio.run(_with_usecases(load_settings(), lambda u: Dialog(u.sessions).run(text)))


def run_search() -> None:
    text = _text("стул офисный на колёсах")
    asyncio.run(
        _with_usecases(load_settings(), lambda u: commands.search(u.search, text))
    )


def run_rerank() -> None:
    text = _text("стул офисный на колёсах")
    asyncio.run(
        _with_usecases(
            load_settings(),
            lambda u: commands.rerank(u.corrector, u.search, u.reranker, text),
        )
    )


def run_fix() -> None:
    text = _text("стул офисный на колесиках, высота сидения 45 метров, обивка экокожка")
    asyncio.run(
        _with_usecases(load_settings(), lambda u: commands.fix(u.corrector, text))
    )


def run_parse() -> None:
    files = IndexFiles(load_settings().data)
    report = ParseCatalog(
        ZipKtruSource(files.ktru_zip),
        FileCatalogStore(files),
        lambda m: print(m, flush=True),
    ).run()
    commands.print_parse(report)


def run_embed() -> None:
    settings = load_settings()
    files = IndexFiles(settings.data)
    asyncio.run(
        EmbedCatalog(
            embeddings(settings),
            FileCatalogStore(files),
            NpyVectorStore(files),
            lambda m: print(m, flush=True),
            settings.embed_batch,
            settings.embed_concurrency,
        ).run()
    )
    print(f"готово: {files.vectors}")


def run_ste() -> None:
    files = IndexFiles(load_settings().data)
    source = XlsxSteSource(Path(sys.argv[1]) if len(sys.argv) > 1 else files.ste_source)
    count = BuildAnalogs(
        source, TfidfAnalogs(files.ste), lambda m: print(m, flush=True)
    ).run()
    print(f"{files.ste}: {count} СТЕ")
