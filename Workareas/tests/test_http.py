"""Exercise the actual station HTTP boundary over a local TCP socket."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from Workareas.shared.configuration import StationConfig
from Workareas.shared.models import JsonObject
from Workareas.shared.server import StationServer, create_server
from Workareas.tests.test_events import print_request


def serve_once(config: StationConfig, ready: threading.Event, ports: list[int]) -> None:
    """
    Handle one actual request on the test worker that owns SQLite.

    :param config: Isolated station settings.
    :param ready: Listener-ready notification.
    :param ports: Selected ephemeral port for the client.
    :return: None.
    """
    server: StationServer = create_server(config)
    ports.append(server.server_port)
    ready.set()
    try:
        server.handle_request()
    finally:
        server.server_close()


class HttpTests(unittest.TestCase):
    """Authentication and malformed input must be enforced on the real socket."""

    def test_health_authentication_and_invalid_submission(self) -> None:
        """
        Use a real server worker with its own SQLite connection.

        :return: None.
        """
        with tempfile.TemporaryDirectory() as directory:
            token: str = "a-real-test-secret-with-at-least-32-characters"
            root: Path = Path(directory)
            token_file: Path = root / "api.token"
            token_file.write_text(token)
            config: StationConfig = StationConfig(
                station="WA1",
                database=root / "events.db",
                token_file=token_file,
                port=0,
                sources={
                    kind: kind for kind in ("printer", "meter", "thermal", "camera")
                },
            )
            request: JsonObject = print_request()
            record: JsonObject
            for record in cast(list[JsonObject], request["evidence"]):
                record["source_time"] = datetime.now(timezone.utc).isoformat()
            for path, body, authorized, expected in (
                ("/health", None, True, 200),
                ("/health", None, False, 401),
                ("/v1/events", "{}", True, 422),
                ("/v1/events", json.dumps(request), True, 201),
            ):
                ready: threading.Event = threading.Event()
                ports: list[int] = []
                worker: threading.Thread = threading.Thread(
                    target=serve_once, args=(config, ready, ports)
                )
                worker.start()
                self.assertTrue(ready.wait(5))
                connection: http.client.HTTPConnection = http.client.HTTPConnection(
                    "127.0.0.1", ports[0], timeout=5
                )
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if authorized:
                    headers["Authorization"] = "Bearer " + token
                connection.request(
                    "POST" if body else "GET", path, body=body, headers=headers
                )
                response: http.client.HTTPResponse = connection.getresponse()
                self.assertEqual(response.status, expected)
                response_data: JsonObject = json.loads(response.read())
                self.assertIsInstance(response_data, dict)
                if expected == 201:
                    self.assertEqual(response_data["activity"], "Print base")
                    self.assertEqual(response_data["authority"], "candidate")
                connection.close()
                worker.join(5)
                self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
