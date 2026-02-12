"""Web chat channel using aiohttp + WebSocket."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

from aiohttp import web, WSMsgType
from loguru import logger

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel

if TYPE_CHECKING:
    from nanobot.config.schema import WebConfig
    from nanobot.session.manager import SessionManager


# Path to bundled static files
_STATIC_DIR = Path(__file__).parent / "web_static"


class WebChannel(BaseChannel):
    """Browser-based chat channel served over HTTP + WebSocket."""

    name = "web"

    def __init__(
        self,
        config: "WebConfig",
        bus: MessageBus,
        session_manager: "SessionManager | None" = None,
    ):
        super().__init__(config, bus)
        self.config: "WebConfig" = config
        self.session_manager = session_manager
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        # chat_id -> WebSocketResponse
        self._ws_clients: dict[str, web.WebSocketResponse] = {}

    # ------------------------------------------------------------------
    # BaseChannel interface
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True

        self._app = web.Application()
        self._app.router.add_get("/", self._serve_index)
        self._app.router.add_get("/ws", self._ws_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        site = web.TCPSite(
            self._runner,
            self.config.host,
            self.config.port,
        )
        await site.start()
        logger.info(
            f"Web channel listening on http://{self.config.host}:{self.config.port}"
        )

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self._running = False
        # Close all WebSocket connections
        for chat_id, ws in list(self._ws_clients.items()):
            if not ws.closed:
                await ws.close()
        self._ws_clients.clear()

        if self._runner:
            await self._runner.cleanup()
        logger.info("Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        ws = self._ws_clients.get(msg.chat_id)
        if ws and not ws.closed:
            try:
                await ws.send_json({
                    "type": "message",
                    "content": msg.content,
                })
            except Exception as e:
                logger.error(f"Error sending to web client {msg.chat_id}: {e}")
        else:
            logger.warning(f"Web client {msg.chat_id} not connected")

    # ------------------------------------------------------------------
    # HTTP handlers
    # ------------------------------------------------------------------

    async def _serve_index(self, request: web.Request) -> web.Response:
        """Serve the single-page chat UI."""
        index_path = _STATIC_DIR / "index.html"
        if not index_path.exists():
            return web.Response(text="Web UI not found", status=404)
        return web.Response(
            body=index_path.read_bytes(),
            content_type="text/html",
        )

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        """Handle WebSocket connections for real-time chat."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        # --- Authentication ---
        token = request.query.get("token", "")
        if self.config.token and token != self.config.token:
            await ws.send_json({"type": "error", "content": "Invalid token"})
            await ws.close()
            return ws

        # Assign a stable chat ID for this connection
        chat_id = f"web_{uuid.uuid4().hex[:8]}"
        self._ws_clients[chat_id] = ws
        logger.info(f"Web client connected: {chat_id}")

        await ws.send_json({
            "type": "system",
            "content": "Connected to nanobot",
            "chatId": chat_id,
        })

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._on_ws_message(chat_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(
                        f"WebSocket error for {chat_id}: {ws.exception()}"
                    )
        except Exception as e:
            logger.error(f"WebSocket handler error for {chat_id}: {e}")
        finally:
            self._ws_clients.pop(chat_id, None)
            logger.info(f"Web client disconnected: {chat_id}")

        return ws

    async def _on_ws_message(self, chat_id: str, raw: str) -> None:
        """Process a WebSocket message from the client."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from web client {chat_id}")
            return

        msg_type = data.get("type", "")

        if msg_type == "message":
            content = data.get("content", "").strip()
            if not content:
                return
            await self._handle_message(
                sender_id="web_user",
                chat_id=chat_id,
                content=content,
                metadata={"source": "web"},
            )

        elif msg_type == "reset":
            # Reset session
            if self.session_manager:
                session_key = f"web:{chat_id}"
                session = self.session_manager.get_or_create(session_key)
                session.clear()
                self.session_manager.save(session)
            ws = self._ws_clients.get(chat_id)
            if ws and not ws.closed:
                await ws.send_json({
                    "type": "system",
                    "content": "Session reset",
                })
