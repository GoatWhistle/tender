"""Заглушки портов моделей для тестов сценариев и замеров: без моделей и сети, только домен и
порты. Тест задаёт каждой ответы, сбой (`fail`), таймаут (`time_out`) или невалидный ответ;
проверку ответа делает общая обёртка из `composition`, а не заглушка.
"""

from app.adapter.stub.decision import StubDecisionBackend
from app.adapter.stub.embeddings import StubEmbeddings
from app.adapter.stub.extractor import StubFactExtractor

__all__ = ["StubDecisionBackend", "StubEmbeddings", "StubFactExtractor"]
