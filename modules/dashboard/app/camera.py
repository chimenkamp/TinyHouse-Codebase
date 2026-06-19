from __future__ import annotations

import base64
import ssl
import socket
import time
import urllib.error
import urllib.request
from contextlib import closing
from typing import Any, Dict, Generator, Tuple
from urllib.parse import urlsplit, urlunsplit

from .ssh_backend import SSHBackend


class CameraConfigError(ValueError):
    pass


def camera_url(config: Dict[str, Any]) -> str:
    camera = config.get("camera", {})
    return _camera_url(camera)


def _camera_url(
    camera: Dict[str, Any],
    host: str | None = None,
    port: int | None = None,
    scheme: str | None = None,
    path: str | None = None,
) -> str:
    ip = str(camera.get("ip") or "").strip()

    if not ip:
        return ""

    target_scheme = (scheme or str(camera.get("scheme") or "http")).strip().lower()
    target_port = int(port or camera.get("port") or _default_port(target_scheme))
    target_host = host or ip
    path = str(path if path is not None else camera.get("path") or "/")

    if not path.startswith("/"):
        path = f"/{path}"

    port_part = "" if target_port == _default_port(target_scheme) else f":{target_port}"
    return f"{target_scheme}://{target_host}{port_part}{path}"


def stream_camera(
    config: Dict[str, Any],
    mode: str,
    path: str | None = None,
) -> Tuple[str, Generator[bytes, None, None]]:
    camera = config.get("camera", {})
    ip = str(camera.get("ip") or "").strip()

    if not ip:
        raise CameraConfigError("camera ip is not configured")

    scheme = str(camera.get("scheme") or "http").strip().lower()
    port = int(camera.get("port") or _default_port(scheme))
    path = str(path if path is not None else camera.get("path") or "/")

    if not path.startswith("/"):
        path = f"/{path}"

    access_mode = str(camera.get("access_mode") or "direct").lower()

    if access_mode == "direct" or mode == "local":
        return _stream_direct_http(config, path)

    ssh = SSHBackend(config)

    if ssh._connection_backend() == "openssh":
        return _stream_openssh_forward(config, ssh, ip, port, path)

    if scheme == "https":
        raise CameraConfigError(
            "HTTPS camera access through the Paramiko tunnel is not supported. "
            "Use management_pc.connection_backend: openssh or set camera.access_mode: direct."
        )

    request = _build_http_request(config, path)

    client = ssh.connect()
    transport = client.get_transport()

    if transport is None:
        client.close()
        raise CameraConfigError("ssh transport is not available")

    channel = transport.open_channel(
        "direct-tcpip",
        (ip, port),
        ("127.0.0.1", 0),
    )
    channel.sendall(request)
    content_type, body = _read_headers(channel)
    return content_type, _camera_generator(channel, body, client)


def _stream_direct_http(
    config: Dict[str, Any],
    path: str | None = None,
) -> Tuple[str, Generator[bytes, None, None]]:
    url = _camera_url(config.get("camera", {}), path=path)

    if not url:
        raise CameraConfigError("camera url is not configured")

    return _stream_camera_url(config, url)


def _stream_camera_url(
    config: Dict[str, Any],
    url: str,
    host_header: str = "",
    allow_http_retry: bool = True,
) -> Tuple[str, Generator[bytes, None, None]]:
    camera = config.get("camera", {})
    username = str(camera.get("username") or "")
    password = str(camera.get("password") or "")
    opener = urllib.request.build_opener()
    handlers = []

    if username or password:
        password_manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, url, username, password)
        configured_url = camera_url(config)
        if configured_url and configured_url != url:
            password_manager.add_password(None, configured_url, username, password)
        handlers.extend([
            urllib.request.HTTPBasicAuthHandler(password_manager),
            urllib.request.HTTPDigestAuthHandler(password_manager),
        ])

    if not bool(camera.get("verify_tls", True)):
        context = ssl._create_unverified_context()
        handlers.append(urllib.request.HTTPSHandler(context=context))

    if handlers:
        opener = urllib.request.build_opener(*handlers)

    headers = {
        "User-Agent": "TinyHouse-Dashboard/1.0",
        "Accept": "*/*",
    }

    if host_header:
        headers["Host"] = host_header

    request = urllib.request.Request(url, headers=headers)

    try:
        response = opener.open(request, timeout=10)
    except urllib.error.HTTPError as error:
        raise CameraConfigError(f"camera returned HTTP {error.code}") from error
    except urllib.error.URLError as error:
        if allow_http_retry and _is_ssl_wrong_version(error) and url.startswith("https://"):
            return _retry_plain_http(config, url, host_header, error)

        raise CameraConfigError(f"camera connection failed: {_format_url_error(error)}") from error
    except ssl.SSLError as error:
        if allow_http_retry and _is_ssl_wrong_version(error) and url.startswith("https://"):
            return _retry_plain_http(config, url, host_header, error)

        raise CameraConfigError(f"camera connection failed: {_format_url_error(error)}") from error

    content_type = response.headers.get_content_type() or "application/octet-stream"
    return content_type, _url_response_generator(response)


def _retry_plain_http(
    config: Dict[str, Any],
    url: str,
    host_header: str,
    original_error: BaseException,
) -> Tuple[str, Generator[bytes, None, None]]:
    parts = urlsplit(url)
    retry_url = urlunsplit(("http", parts.netloc, parts.path, parts.query, parts.fragment))

    try:
        return _stream_camera_url(
            config,
            retry_url,
            host_header=host_header,
            allow_http_retry=False,
        )
    except CameraConfigError as retry_error:
        raise CameraConfigError(
            "camera TLS handshake failed. The camera answered like plain HTTP on an HTTPS URL. "
            "Use scheme http for port 80, or use scheme https with the camera's HTTPS port. "
            f"Retrying {retry_url} also failed: {retry_error}"
        ) from original_error


def _is_ssl_wrong_version(error: Any) -> bool:
    reason = getattr(error, "reason", error)
    return isinstance(reason, ssl.SSLError) and "WRONG_VERSION_NUMBER" in str(reason)


def _format_url_error(error: Any) -> str:
    if _is_ssl_wrong_version(error):
        reason = getattr(error, "reason", error)
        return (
            f"{reason}. The camera likely received HTTPS on a plain HTTP port. "
            "Try scheme http on port 80, or scheme https on port 443."
        )

    return str(getattr(error, "reason", error))


def _stream_openssh_forward(
    config: Dict[str, Any],
    ssh: SSHBackend,
    ip: str,
    port: int,
    path: str,
) -> Tuple[str, Generator[bytes, None, None]]:
    try:
        import pexpect
    except ImportError as error:
        raise CameraConfigError(f"OpenSSH camera tunnel requires pexpect: {error}") from error

    local_port = _reserve_local_port()
    forward = f"127.0.0.1:{local_port}:{ip}:{port}"
    command_parts = _with_ssh_option(ssh._ssh_command_parts(), ["-L", forward])
    password = str(config.get("management_pc", {}).get("password") or "")

    try:
        child = pexpect.spawn(
            command_parts[0],
            command_parts[1:],
            encoding="utf-8",
            timeout=8,
            dimensions=(40, 160),
        )
    except Exception as error:
        raise CameraConfigError(f"SSH camera tunnel could not start: {error}") from error

    transcript = ""

    try:
        transcript = ssh._drive_openssh_login(child, password, 24)

        if not _wait_for_tcp("127.0.0.1", local_port, 8):
            detail = transcript.strip() or "no SSH output was captured"
            raise CameraConfigError(f"SSH camera tunnel did not open {forward}. {detail}")

        camera = config.get("camera", {})
        url = _camera_url(camera, host="127.0.0.1", port=local_port, path=path)
        content_type, iterator = _stream_camera_url(
            config,
            url,
            host_header=_camera_host_header(camera),
        )
        return content_type, _close_with_ssh_child(iterator, child)
    except Exception:
        child.close(force=True)
        raise


def _build_http_request(config: Dict[str, Any], path: str) -> bytes:
    camera = config.get("camera", {})
    ip = str(camera.get("ip") or "")
    scheme = str(camera.get("scheme") or "http").strip().lower()
    port = int(camera.get("port") or _default_port(scheme))
    username = str(camera.get("username") or "")
    password = str(camera.get("password") or "")
    headers = [
        f"GET {path} HTTP/1.1",
        f"Host: {_camera_host_header({'ip': ip, 'port': port, 'scheme': scheme})}",
        "User-Agent: TinyHouse-Dashboard/1.0",
        "Accept: */*",
        "Connection: close",
    ]

    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        headers.append(f"Authorization: Basic {token}")

    return ("\r\n".join(headers) + "\r\n\r\n").encode("utf-8")


def _http_stream_response(stream: socket.socket) -> Tuple[str, Generator[bytes, None, None]]:
    content_type, body = _read_headers(stream)
    return content_type, _camera_generator(stream, body, None)


def _read_headers(stream: Any) -> Tuple[str, bytes]:
    data = b""

    while b"\r\n\r\n" not in data:
        chunk = stream.recv(4096)

        if not chunk:
            break

        data += chunk

        if len(data) > 65536:
            break

    header_bytes, _, body = data.partition(b"\r\n\r\n")
    content_type = "application/octet-stream"

    for line in header_bytes.decode("iso-8859-1", errors="replace").splitlines():
        if line.lower().startswith("content-type:"):
            content_type = line.split(":", 1)[1].strip()
            break

    return content_type, body


def _camera_generator(
    stream: Any,
    first_body: bytes,
    ssh_client: Any | None,
) -> Generator[bytes, None, None]:
    try:
        if first_body:
            yield first_body

        while True:
            chunk = stream.recv(8192)

            if not chunk:
                break

            yield chunk
    finally:
        stream.close()

        if ssh_client is not None:
            ssh_client.close()


def _url_response_generator(response: Any) -> Generator[bytes, None, None]:
    try:
        while True:
            chunk = response.read(8192)

            if not chunk:
                break

            yield chunk
    finally:
        response.close()


def _close_with_ssh_child(
    iterator: Generator[bytes, None, None],
    child: Any,
) -> Generator[bytes, None, None]:
    try:
        yield from iterator
    finally:
        child.close(force=True)


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def _camera_host_header(camera: Dict[str, Any]) -> str:
    ip = str(camera.get("ip") or "").strip()
    scheme = str(camera.get("scheme") or "http").strip().lower()
    port = int(camera.get("port") or _default_port(scheme))
    return ip if port == _default_port(scheme) else f"{ip}:{port}"


def _reserve_local_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_tcp(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.1)

    return False


def _with_ssh_option(command_parts: list[str], option: list[str]) -> list[str]:
    insert_at = _ssh_option_insert_index(command_parts)
    return command_parts[:insert_at] + option + command_parts[insert_at:]


def _ssh_option_insert_index(command_parts: list[str]) -> int:
    options_with_values = {
        "-b",
        "-c",
        "-D",
        "-E",
        "-e",
        "-F",
        "-I",
        "-i",
        "-J",
        "-L",
        "-l",
        "-m",
        "-O",
        "-o",
        "-p",
        "-Q",
        "-R",
        "-S",
        "-W",
        "-w",
    }
    index = 1

    while index < len(command_parts):
        part = command_parts[index]

        if not part.startswith("-"):
            return index

        if part in options_with_values and index + 1 < len(command_parts):
            index += 2
            continue

        index += 1

    return len(command_parts)
