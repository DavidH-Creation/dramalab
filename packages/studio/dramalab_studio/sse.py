"""Server-Sent Events helper."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from starlette.responses import StreamingResponse


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
                payload = json.dumps(data, ensure_ascii=False) if isinstance(data, dict) else str(data)
                yield f"event: {event_type}\ndata: {payload}\n\n"
        except asyncio.CancelledError:
            pass
