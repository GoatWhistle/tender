import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
import strict_api as api
from fastapi import HTTPException
from jsonschema import ValidationError

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "count"],
    "properties": {"kind": {"type": "string", "enum": ["table"]}, "count": {"type": "integer"}},
}


def completion(value, finish="stop"):
    return {
        "choices": [{"message": {"content": json.dumps(value)}, "finish_reason": finish}],
        "usage": {"completion_tokens": 10},
    }


class StrictTests(unittest.TestCase):
    def test_schema_validation(self):
        api.strict_schema(SCHEMA)
        for mutation in (
            {**SCHEMA, "additionalProperties": True},
            {**SCHEMA, "required": ["kind"]},
            {**SCHEMA, "patternProperties": {}},
            {**SCHEMA, "properties": {"x": {"type": "string", "pattern": "x"}}},
            {
                **SCHEMA,
                "properties": {"kind": {"properties": {"open": {"type": "string"}}}},
                "required": ["kind"],
            },
        ):
            with self.subTest(schema=mutation), self.assertRaises(ValueError):
                api.strict_schema(mutation)

    def test_invalid_responses(self):
        for value in (
            {"kind": "table"},
            {"kind": "chair", "count": 2},
            {"kind": "table", "count": "2"},
            {"kind": "table", "count": 2, "extra": 1},
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                api.validate_completion(completion(value), SCHEMA)

    def test_truncation_fails_even_with_valid_json(self):
        with self.assertRaises(ValueError):
            api.validate_completion(completion({"kind": "table", "count": 2}, "length"), SCHEMA)

    def test_non_json_and_nonfinite_fail(self):
        for content in (
            "invalid",
            '{"kind":"table","count":NaN}',
            '{"kind":"table","count":1,"count":2}',
            '{"kind":"table","count":1e999}',
        ):
            result = completion({})
            result["choices"][0]["message"]["content"] = content
            with self.assertRaises(ValueError):
                api.validate_completion(result, SCHEMA)

    def test_valid_output(self):
        value = {"kind": "table", "count": 2}
        self.assertEqual(api.validate_completion(completion(value), SCHEMA), value)


class APITests(unittest.IsolatedAsyncioTestCase):
    async def call(self, result, body):
        async def handle(request):
            return httpx.Response(200, json=result)

        async with httpx.AsyncClient(
            base_url="http://engine", transport=httpx.MockTransport(handle)
        ) as client:
            with patch.object(api, "client", client):
                return await api.complete(body)

    def body(self):
        return {
            "model": api.MODEL,
            "messages": [{"role": "user", "content": "table"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "test", "strict": True, "schema": SCHEMA},
            },
        }

    async def test_strict_required(self):
        for body in (
            {},
            {"response_format": {"type": "json_object"}},
            {**self.body(), "stream": True},
        ):
            with self.subTest(body=body), self.assertRaises(HTTPException) as error:
                await api.complete(body)
            self.assertEqual(error.exception.status_code, 422)

    async def test_engine_output_revalidated(self):
        with self.assertRaises(HTTPException) as error:
            await self.call(completion({"kind": "chair", "count": 1}), self.body())
        self.assertEqual(error.exception.status_code, 502)

    async def test_bounded_queue(self):
        with patch.object(api, "slots", asyncio.Semaphore(0)):
            with self.assertRaises(HTTPException) as error:
                await api.complete(self.body())
            self.assertEqual(error.exception.status_code, 429)

    async def test_engine_failure(self):
        async def handle(request):
            raise httpx.ConnectError("offline")

        async with httpx.AsyncClient(
            base_url="http://engine", transport=httpx.MockTransport(handle)
        ) as client:
            with patch.object(api, "client", client), self.assertRaises(HTTPException) as error:
                await api.complete(self.body())
        self.assertEqual(error.exception.status_code, 503)

    async def test_extraction_quote_and_subject(self):
        request = api.ExtractRequest(
            messages=[{"id": "m1", "text": "Высота стола 70 см"}],
            targets=[{"attribute_ref": "height", "subject_ref": "table", "description": "Высота"}],
        )
        schema = api.extraction_schema(request)
        api.strict_schema(schema)
        fact = {
            "attribute_ref": "height",
            "subject_ref": "table",
            "raw_value": "70",
            "raw_unit": "см",
            "source_quote": "Высота стола 70 см",
            "source_message_id": "m1",
            "negated": False,
            "uncertain": False,
        }
        for quote, expected in (("Высота стола 70 см", None), ("Высота 100 см", 502)):
            fact["source_quote"] = quote
            with patch.object(api, "complete", return_value=completion({"facts": [fact]})):
                if expected:
                    with self.assertRaises(HTTPException) as error:
                        await api.extract(request)
                    self.assertEqual(error.exception.status_code, expected)
                else:
                    result = await api.extract(request)
                    self.assertEqual(result["status"], "proposed")


if __name__ == "__main__":
    unittest.main()
