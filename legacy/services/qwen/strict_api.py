"""Fail closed strict JSON Schema API around the private vLLM engine."""

import asyncio
import json
import logging
import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from jsonschema import Draft202012Validator, SchemaError, ValidationError
from pydantic import BaseModel, ConfigDict, Field

ENGINE_URL = os.getenv("QWEN_ENGINE_URL", "http://127.0.0.1:8083")
MODEL = "qwen-extractor"
MANIFEST_DIR = Path(os.getenv("QWEN_MANIFEST_DIR", Path(__file__).parent))
REVISION = json.loads((MANIFEST_DIR / "model-manifest.json").read_text())["extractor"]["revision"]
SYSTEM = (
    "Извлекай только явно указанные факты из исходных сообщений. "
    "Возвращай JSON по схеме. Не придумывай значения. Цитата должна дословно "
    "присутствовать в сообщении. Сохраняй отрицание, неопределённость и часть товара. "
    "Принятые факты — контекст, а не источник новых цитат. "
    "Если подходящих фактов нет, верни пустой список facts."
    "\nraw_value — только значение, raw_unit — единица измерения или null."
)
logger = logging.getLogger(__name__)


def strict_schema(schema):
    """Reject unsupported keywords instead of accepting unenforced constraints."""
    Draft202012Validator.check_schema(schema)
    allowed = {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "anyOf",
        "$defs",
        "$ref",
        "title",
        "description",
    }

    def walk(node):
        if not isinstance(node, dict) or set(node) - allowed:
            raise ValueError("Unsupported JSON Schema keyword")
        if "$ref" in node and not node["$ref"].startswith("#/$defs/"):
            raise ValueError("Only local $defs references are supported")
        types = node.get("type", [])
        types = [types] if isinstance(types, str) else types
        if {"properties", "required", "additionalProperties"} & set(node) and "object" not in types:
            raise ValueError("Object constraints require an explicit object type")
        if "object" in types:
            props = node.get("properties", {})
            if node.get("additionalProperties") is not False:
                raise ValueError("Every object requires additionalProperties=false")
            if set(node.get("required", [])) != set(props):
                raise ValueError("Every property must be required; use nullable types")
        for child in node.get("properties", {}).values():
            walk(child)
        for child in node.get("$defs", {}).values():
            walk(child)
        if "items" in node:
            walk(node["items"])
        for child in node.get("anyOf", []):
            walk(child)

    walk(schema)
    if schema.get("type") != "object":
        raise ValueError("Root schema must be an object")


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON property")
        value[key] = item
    return value


def finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")
    return value


def invalid_constant(text):
    raise ValueError(f"Invalid JSON constant: {text}")


def validate_completion(result, schema):
    choice = result["choices"][0]
    if choice["finish_reason"] != "stop":
        raise ValueError("Incomplete generation; no extraction returned")
    content = choice["message"]["content"]
    value = json.loads(
        content,
        parse_constant=invalid_constant,
        object_pairs_hook=unique_object,
        parse_float=finite_float,
    )
    Draft202012Validator(schema).validate(value)
    return value


client = None
slots = asyncio.Semaphore(16)
ready = False


def engine_client():
    # vLLM can close a socket after sending a validation error. Never reuse it.
    return httpx.AsyncClient(
        base_url=ENGINE_URL,
        timeout=120,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=0),
    )


async def complete(body):
    if body.get("stream", False) or body.get("tools"):
        raise HTTPException(422, "Streaming and tools are not supported by strict API")
    fmt = body.get("response_format", {})
    if not isinstance(fmt, dict):
        raise HTTPException(422, "Invalid response_format")
    spec = fmt.get("json_schema", {})
    if not isinstance(spec, dict):
        raise HTTPException(422, "Invalid json_schema")
    if fmt.get("type") != "json_schema" or spec.get("strict") is not True:
        raise HTTPException(422, "response_format=json_schema and strict=true are required")
    try:
        schema = spec["schema"]
        strict_schema(schema)
    except (KeyError, ValueError, SchemaError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if body.get("model", MODEL) != MODEL:
        raise HTTPException(422, "Unknown model")
    max_tokens = body.get("max_tokens", 1024)
    if type(max_tokens) is not int or not 1 <= max_tokens <= 2048:
        raise HTTPException(422, "max_tokens must be an integer in 1..2048")
    if slots.locked():
        raise HTTPException(429, "Extractor queue is full")
    payload = {
        "model": MODEL,
        "messages": body.get("messages", []),
        "response_format": fmt,
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    async with slots:
        try:
            response = await client.post("/v1/chat/completions", json=payload)
        except httpx.RequestError as exc:
            logger.warning("Inference transport failed: %s: %s", type(exc).__name__, str(exc))
            raise HTTPException(503, "Inference engine unavailable or timed out") from exc
    if response.status_code != 200:
        raise HTTPException(response.status_code, response.text[:2000])
    try:
        result = response.json()
    except ValueError as exc:
        raise HTTPException(502, "Engine returned invalid JSON") from exc
    try:
        validate_completion(result, schema)
    except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
        raise HTTPException(502, "Incomplete or schema-invalid generation") from exc
    return result


@asynccontextmanager
async def lifespan(app):
    global client, ready
    client = engine_client()
    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["ok"]}},
        "required": ["status"],
        "additionalProperties": False,
    }
    for _ in range(300):
        try:
            await complete(
                {
                    "messages": [{"role": "user", "content": "Return status=ok."}],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "readiness",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                    "max_tokens": 32,
                }
            )
            ready = True
            break
        except HTTPException:
            await asyncio.sleep(2)
    if not ready:
        await client.aclose()
        raise RuntimeError("Strict inference readiness probe failed")
    yield
    ready = False
    await client.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/health/ready")
async def health():
    if not ready:
        raise HTTPException(503, "Not ready")
    try:
        response = await client.get("/health", timeout=3)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Engine not ready") from exc
    return {
        "status": "ready",
        "model": MODEL,
        "revision": REVISION,
        "strict": True,
        "backend": "xgrammar",
        "thinking": False,
    }


@app.post("/v1/chat/completions")
async def chat(body: dict):
    return await complete(body)


@app.get("/v1/models")
async def models():
    return {
        "object": "list",
        "data": [
            {"id": MODEL, "object": "model", "created": 0, "owned_by": "Qwen", "revision": REVISION}
        ],
    }


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str = Field(min_length=1, max_length=20000)


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attribute_ref: str
    description: str
    subject_ref: str


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[Message] = Field(min_length=1, max_length=16)
    targets: list[Target] = Field(min_length=1, max_length=64)
    accepted_facts: list[dict] = Field(default_factory=list, max_length=64)


def extraction_schema(request):
    props = {
        "attribute_ref": {
            "type": "string",
            "enum": list(dict.fromkeys(t.attribute_ref for t in request.targets)),
        },
        "raw_value": {"type": "string"},
        "raw_unit": {"type": ["string", "null"]},
        "source_quote": {"type": "string"},
        "source_message_id": {"type": "string", "enum": [m.id for m in request.messages]},
        "negated": {"type": "boolean"},
        "uncertain": {"type": "boolean"},
        "subject_ref": {
            "type": "string",
            "enum": list(dict.fromkeys(t.subject_ref for t in request.targets)),
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["facts"],
        "properties": {
            "facts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": props,
                    "required": list(props),
                    "additionalProperties": False,
                },
            }
        },
    }


@app.post("/v1/extract")
async def extract(request: ExtractRequest):
    schema = extraction_schema(request)
    result = await complete(
        {
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM
                    + "\nСхема ответа:\n"
                    + json.dumps(schema, ensure_ascii=False),
                },
                {
                    "role": "user",
                    "content": request.model_dump_json(),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "facts",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
    )
    value = validate_completion(result, schema)
    sources = {m.id: m.text for m in request.messages}
    targets = {(t.attribute_ref, t.subject_ref) for t in request.targets}
    for fact in value["facts"]:
        if (fact["attribute_ref"], fact["subject_ref"]) not in targets:
            raise HTTPException(502, "Attribute/subject pair is outside targets")
        if (
            not fact["source_quote"]
            or fact["source_quote"] not in sources[fact["source_message_id"]]
        ):
            raise HTTPException(502, "Source quote is absent from source message")
    return {**value, "status": "proposed", "model_revision": REVISION, "usage": result["usage"]}
