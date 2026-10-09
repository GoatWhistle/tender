import asyncio
import json
import unittest
from unittest.mock import patch

import strict_api as api
import test_strict as fixtures
from fastapi import HTTPException


class HTTPRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejected_request_does_not_poison_next_request(self):
        async def handle(reader, writer):
            try:
                headers = await reader.readuntil(b"\r\n\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in headers.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                body = json.loads(await reader.readexactly(length))
                rejected = body["messages"][0]["content"] == "too long"
                value = (
                    {"error": "overlength"}
                    if rejected
                    else fixtures.completion({"kind": "table", "count": 2})
                )
                data = json.dumps(value).encode()
                status = b"400 Bad Request" if rejected else b"200 OK"
                writer.write(
                    b"HTTP/1.1 "
                    + status
                    + b"\r\nContent-Type: application/json\r\n"
                    + f"Content-Length: {len(data)}\r\nConnection: keep-alive\r\n\r\n".encode()
                    + data
                )
                await writer.drain()
                if rejected:
                    # Upstream fails after sending 400; a reused socket gets EOF.
                    await reader.readuntil(b"\r\n\r\n")
            except asyncio.IncompleteReadError:
                pass
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            with patch.object(api, "ENGINE_URL", f"http://127.0.0.1:{port}"):
                async with api.engine_client() as client:
                    with patch.object(api, "client", client):
                        body = fixtures.APITests().body()
                        invalid = {**body, "messages": [{"role": "user", "content": "too long"}]}
                        with self.assertRaises(HTTPException) as error:
                            await api.complete(invalid)
                        self.assertEqual(error.exception.status_code, 400)
                        response = await api.complete(body)
                        self.assertEqual(
                            json.loads(response["choices"][0]["message"]["content"]),
                            {"kind": "table", "count": 2},
                        )


if __name__ == "__main__":
    unittest.main()
