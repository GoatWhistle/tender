from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, strict=True)]
Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Input(StrictModel):
    premise: Text | None = None
    context_id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")] | None = None
    use_cache: bool = True

    @model_validator(mode="after")
    def validate_source(self):
        if (self.premise is None) == (self.context_id is None):
            raise ValueError("Передайте ровно одно поле: premise или context_id")
        if self.premise is not None and not self.premise.strip():
            raise ValueError("premise не должно быть пустым")
        if self.context_id is not None and not self.use_cache:
            raise ValueError("Для context_id требуется use_cache=true")
        return self


class NLIRequest(Input):
    hypotheses: Annotated[list[Text], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def nonblank(self):
        if any(not h.strip() for h in self.hypotheses):
            raise ValueError("Гипотезы не должны быть пустыми")
        return self


class Option(StrictModel):
    id: Annotated[str, Field(min_length=1, max_length=128, strict=True)]
    criterion: Text


class ChoiceRequest(Input):
    instructions: Text
    options: Annotated[list[Option], Field(min_length=2, max_length=256)]

    @model_validator(mode="after")
    def valid_options(self):
        if len({o.id for o in self.options}) != len(self.options):
            raise ValueError("ID опций должны быть уникальны")
        if not self.instructions.strip() or any(
            not o.id.strip() or not o.criterion.strip() for o in self.options
        ):
            raise ValueError("Инструкция, ID опций и критерии не должны быть пустыми")
        return self


class PrepareRequest(StrictModel):
    premise: Text

    @model_validator(mode="after")
    def nonblank(self):
        if not self.premise.strip():
            raise ValueError("premise не должно быть пустым")
        return self


class ContextInfo(StrictModel):
    id: str
    reused: bool
    prefix_tokens: int
    retained_bytes: int
    expires_in_seconds: int


class PreparedResponse(StrictModel):
    context: ContextInfo
    model_revision: str


class NLIResult(StrictModel):
    hypothesis: str
    label: Literal["contradicted", "supported", "not_stated"]
    probabilities: dict[Literal["contradicted", "supported", "not_stated"], Probability]


class NLIResponse(StrictModel):
    results: list[NLIResult]
    context: ContextInfo | None
    model_revision: str


class ChoiceResponse(StrictModel):
    choice: str
    probabilities: dict[str, Probability]
    support_probabilities: dict[str, Probability]
    context: ContextInfo | None
    model_revision: str
