"""Извлекатель фактов без модели — реализация порта `ModelFactExtractor`: отдаёт заданные тестом
факты (по умолчанию — ни одного) и запоминает запросы."""

from app.adapter.stub.fault import Scripted
from app.domain.inference import ExtractedFact, Extraction, ExtractionRequest


class StubFactExtractor(Scripted):
    model = "stub-extractor"

    def __init__(self, revision: str = "stub-1") -> None:
        super().__init__(revision)
        self.facts: list[ExtractedFact] = []
        self.requests: list[ExtractionRequest] = []

    def extract(self, request: ExtractionRequest) -> Extraction:
        self.requests.append(request)
        self._raise_fault()
        return Extraction(facts=tuple(self.facts), revision=self.revision)
