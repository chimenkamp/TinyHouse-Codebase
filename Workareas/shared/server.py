"""Authenticated loopback evidence API; device control is outside this service."""

from __future__ import annotations

import hmac
import json
import logging
import secrets
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TYPE_CHECKING, cast

from Workareas.shared.configuration import StationConfig
from Workareas.shared.events import EventService, encode
from Workareas.shared.models import JsonObject, ValidationError, mapping

if TYPE_CHECKING:
    from Workareas.shared.mqtt_delivery import MqttDelivery

BIND_HOST: str = "127.0.0.1"
MAX_REQUEST_BYTES: int = 1_048_576
REQUEST_TIMEOUT_SECONDS: float = 5.0
TOKEN_BYTES: int = 32
MIN_TOKEN_CHARACTERS: int = 32
POLL_SECONDS: float = 0.5
LOGGER: logging.Logger = logging.getLogger(__name__)


def load_token(path: Path | None) -> str:
    """
    Create or read a local secret without printing it or shipping a default.

    :param path: Explicit token-file location.
    :return: Nonempty authentication secret.
    """
    if path is None:
        raise ValidationError("configure token_file before starting the HTTP API")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch(mode=0o600, exist_ok=False)
        path.write_text(secrets.token_urlsafe(TOKEN_BYTES), encoding="utf-8")
    token: str = path.read_text(encoding="utf-8").strip()
    if len(token) < MIN_TOKEN_CHARACTERS:
        raise ValidationError("API token must contain at least 32 characters")
    return token


class StationServer(HTTPServer):
    """Single-threaded HTTP/SQLite ownership with asynchronous MQTT transport."""

    service: EventService
    api_token: str
    delivery: MqttDelivery | None

    def __init__(self, config: StationConfig) -> None:
        """
        Bind only the local machine and prepare the durable event service.

        :param config: Explicit station settings.
        :return: None.
        """
        self.api_token = load_token(config.token_file)
        self.service = EventService(config)
        self.delivery = None
        try:
            super().__init__((BIND_HOST, config.port), StationHandler)
            if config.broker is not None:
                from Workareas.shared.mqtt_delivery import MqttDelivery

                self.delivery = MqttDelivery(config.broker, config.station)
        except (OSError, ValueError, ImportError):
            self.service.close()
            raise

    def get_request(self) -> tuple[socket.socket, tuple[str, int]]:
        """
        Bound slow or incomplete HTTP clients before reading their bodies.

        :return: Accepted connection and client address.
        """
        connection: socket.socket
        address: tuple[str, int]
        connection, address = super().get_request()
        connection.settimeout(REQUEST_TIMEOUT_SECONDS)
        return connection, address

    def service_actions(self) -> None:
        """
        Drain acknowledged MQTT deliveries while keeping SQLite on this thread.

        :return: None.
        """
        if self.delivery is not None:
            self.delivery.publish_pending(self.service)

    def server_close(self) -> None:
        """
        Close MQTT, HTTP and the station database during normal shutdown.

        :return: None.
        """
        if self.delivery is not None:
            self.delivery.close()
        self.service.close()
        super().server_close()


class StationHandler(BaseHTTPRequestHandler):
    """Accept evidence bundles; reject missing source bindings and invalid facts."""

    def _station(self) -> StationServer:
        """
        Access the concrete server that owns this request handler.

        :return: Station server.
        """
        return cast(StationServer, self.server)

    def _authenticated(self) -> bool:
        """
        Check the local adapter token with a constant-time comparison.

        :return: Whether the request can access local evidence.
        """
        supplied: str = self.headers.get("Authorization", "")
        if not hmac.compare_digest(
            supplied.encode(), ("Bearer " + self._station().api_token).encode()
        ):
            self._reply(401, {"error": "authentication required"})
            return False
        return True

    def _reply(self, status: int, payload: JsonObject) -> None:
        """
        Return a bounded JSON response and close the request connection.

        :param status: HTTP response status.
        :param payload: JSON body.
        :return: None.
        """
        body: bytes = encode(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """
        Expose local health and immutable events for observer integrations.

        :return: None.
        """
        if not self._authenticated():
            return
        service: EventService = self._station().service
        if self.path == "/health":
            self._reply(
                200,
                {
                    "station": service.config.station,
                    "authority": "authoritative"
                    if service.config.commissioning
                    else "candidate",
                    "pending_batch_size": len(service.pending()),
                },
            )
        elif self.path.startswith("/v1/events/"):
            try:
                self._reply(
                    200,
                    mapping(
                        json.loads(
                            service.get_event(self.path.removeprefix("/v1/events/"))
                        ),
                        "event",
                    ),
                )
            except KeyError:
                self._reply(404, {"error": "event not found"})
        else:
            self._reply(404, {"error": "route not found"})

    def do_POST(self) -> None:
        """
        Validate a correlated evidence bundle and commit one abstracted event.

        :return: None.
        """
        if not self._authenticated():
            return
        if self.path != "/v1/events":
            self._reply(404, {"error": "route not found"})
            return
        try:
            request: JsonObject = self._read_json()
            event: JsonObject = self._station().service.submit(request)
            self._reply(201, event)
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self._reply(422, {"state": "unknown", "error": str(error)})

    def _read_json(self) -> JsonObject:
        """
        Reject ambiguous framing and oversized or non-object request bodies.

        :return: Decoded JSON object.
        """
        if self.headers.get_content_type() != "application/json" or self.headers.get(
            "Transfer-Encoding"
        ):
            raise ValidationError(
                "send application/json with Content-Length, no chunked encoding"
            )
        lengths: list[str] = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise ValidationError("one numeric Content-Length is required")
        length: int = int(lengths[0])
        if not 0 < length <= MAX_REQUEST_BYTES:
            raise ValidationError(f"body must contain 1..{MAX_REQUEST_BYTES} bytes")
        body: bytes = self.rfile.read(length)
        if len(body) != length:
            raise ValidationError("incomplete request body")
        return mapping(json.loads(body.decode("utf-8")), "request")

    def log_message(self, format: str, *args: str | int) -> None:
        """
        Log request results without including body contents or credentials.

        :param format: Standard HTTP log format.
        :param args: Request metadata.
        :return: None.
        """
        LOGGER.info(format, *args)


def create_server(config: StationConfig) -> StationServer:
    """
    Construct the explicitly configured API server.

    :param config: Local station settings.
    :return: Bound server ready to process evidence.
    """
    return StationServer(config)


def run(config: StationConfig) -> None:
    """
    Start the station API and stop cleanly when the operator interrupts it.

    :param config: Configuration constructed by main.py.
    :return: None.
    """
    logging.basicConfig(level=logging.INFO)
    server: StationServer = create_server(config)
    LOGGER.info(
        "%s listening on %s:%s; authority=%s; token file=%s",
        config.station,
        BIND_HOST,
        config.port,
        bool(config.commissioning),
        config.token_file,
    )
    try:
        server.serve_forever(poll_interval=POLL_SECONDS)
    except KeyboardInterrupt:
        LOGGER.info("Station stopped by operator")
    finally:
        server.server_close()
