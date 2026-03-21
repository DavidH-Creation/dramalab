"""Server-Sent Events helper."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from starlette.responses import StreamingResponse

logger = logging.getLogger(__name__)


class EventSourceResponse(StreamingResponse):
    """SSE response that streams events to the client."""

    def __init__(self, generator: AsyncIterator, **kwargs):
        super().__init__(
            self._wrap(generator),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
            **kwargs,
        )

    @staticmethod
    async def _wrap(generator: AsyncIterator):
        try:
            async for event_type, data in generator:
                try:
                    payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
                except (TypeError, ValueError) as exc:
                    logger.error("JSON serialization failed for event '%s': %s", event_type, exc)
                    payload = json.dumps({"error": f"Serialization error: {exc}"})
                yield f"event: {event_type}\ndata: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected error in SSE stream")
