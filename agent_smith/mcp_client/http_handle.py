from typing import Any
import subprocess
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
        try:
            return self.connect_http()
        except Exception:
            if not self.config.get("args"):
                raise HttpHandleErr("Need args to connect to Http MCP")
            self.start_http_server()
            self.http_launched = True
        for _ in range(20):
            time.sleep(0.25)
            try:
                return self.connect_http()
            except Exception:
                continue
        raise HttpHandleErr("HTTP MCP not started")

    def connect_http(self):
        url = self.config.get("url")
        if not url:
            raise HttpHandleErr("Missing URL")
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

        path = parsed.path or "/mcp"

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
        )
        
    def stop(self) -> None:
        if self.http_context is not None:
            self.http_context.__exit__(None, None, None)
            self.http_context = None
        if self.http_launched and self.http_server_process is not None:
            self.http_server_process.terminate()