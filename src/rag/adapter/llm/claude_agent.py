import tempfile
from collections.abc import Mapping

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKError, ResultMessage, query

from rag.domain.errors import ModelFailure
from rag.domain.inference import Completion, StructuredRequest, Tier, Usage

DEFAULT_MODELS = {Tier.FAST: "haiku", Tier.SMART: "sonnet"}


class ClaudeAgentModel:
    def __init__(self, models: Mapping[Tier, str] = DEFAULT_MODELS) -> None:
        self._models = dict(models)

    def _options(self, request: StructuredRequest, cwd: str) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self._models[request.tier],
            effort=request.effort.value if request.effort else None,
            system_prompt=request.system,
            setting_sources=[],
            tools=[],
            cwd=cwd,
            output_format={"type": "json_schema", "schema": request.schema},
        )

    async def complete(self, request: StructuredRequest) -> Completion:
        result: ResultMessage | None = None
        try:
            with tempfile.TemporaryDirectory(prefix="rag-agent-") as cwd:
                async for message in query(
                    prompt=request.prompt, options=self._options(request, cwd)
                ):
                    if isinstance(message, ResultMessage):
                        result = message
        except ClaudeSDKError as exc:
            raise ModelFailure(f"ошибка модели: {exc}") from exc
        if result is None:
            raise ModelFailure("ошибка модели: нет ResultMessage")
        if result.is_error or not isinstance(result.structured_output, dict):
            raise ModelFailure(f"ошибка модели: {result.errors or result.result}")
        usage = result.usage or {}
        return Completion(
            output=result.structured_output,
            usage=Usage(
                model=self._models[request.tier],
                duration_ms=result.duration_ms,
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cost_usd=result.total_cost_usd,
            ),
        )
