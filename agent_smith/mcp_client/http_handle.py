from typing import Any
import subprocess
import socket
import time
from anyio.from_thread import BlockingPortal
from urllib.parse import urlparse

from mcp.client.streamable_http import streamable_http_client

class HttpHandleErr(Exception):
    pass

class HttpHandle:
    def __init__(self, portal: BlockingPortal, config: dict[str, Any]) -> None:
        self.portal = portal
        self.config = config
        self.http_context = None
        self.http_launched = False
        self.http_server_process = None


    def handle_http(self) -> tuple[Any, Any]:
        if self.is_server_reachable():
            return self.connect_http()
        if not self.config.get("args"):
            raise HttpHandleErr("Couldn't connect to http server (missing args)")
        self.start_http_server()
        self.http_launched = True
        self.wait_for_server()
        return self.connect_http()

    def wait_for_server(self) -> None:
        for _ in range(20):
            if self.is_server_reachable():
                return
            time.sleep(0.25)
        raise HttpHandleErr("HTTP MCP server did not start")

    def is_server_reachable(self) -> bool:
        parsed = urlparse(self.config["url"])
        if not parsed.hostname:
            return False
        if parsed.port is None:
            return False
        try:
            with socket.create_connection(
                (parsed.hostname, parsed.port),
                timeout=0.5,
            ):
                return True
        except OSError:
            return False

    def connect_http(self):
        url = self.config.get("url")
        if not url:
            raise HttpHandleErr("Missing URL")
        parsed = urlparse(url)
        if not parsed.path or parsed.path == "/":
            url = url.rstrip("/") + "/mcp"
        else:
            url = url.rstrip("/")

        self.http_context = self.portal.wrap_async_context_manager(
            streamable_http_client(url)
        )
        streams = self.http_context.__enter__()
        read_stream, write_stream = streams[:2]
        return read_stream, write_stream

    def start_http_server(self) -> None:
        parsed = urlparse(self.config["url"])
        if not parsed.hostname:
            raise HttpHandleErr("HTTP URL must include a hostname")
        if parsed.port is None:
            raise HttpHandleErr("HTTP URL must include a port")
        path = parsed.path
        if not path or path == "/":
            path = "/mcp"
        http_args = [
            *self.config.get("args", []),
            "--transport",
            "http",
            "--host",
            parsed.hostname,
            "--port",
            str(parsed.port),
            "--path",
            path,
        ]

        self.http_server_process = subprocess.Popen(
            [
                self.config["command"],
                *http_args,
            ],
            cwd=self.config.get("cwd"),
            start_new_session=True,
        )
        
    def stop(self) -> None:
        if self.http_context is not None:
            self.http_context.__exit__(None, None, None)
            self.http_context = None
        if self.http_launched and self.http_server_process is not None:
            try:
                self.http_server_process.terminate()
                self.http_server_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.http_server_process.kill()
                self.http_server_process.wait(timeout=2)
            finally:
                self.http_server_process = None
                self.http_launched = False