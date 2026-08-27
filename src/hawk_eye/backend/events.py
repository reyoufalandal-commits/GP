from __future__ import annotations

import asyncio
from typing import Any

from hawk_eye.backend.ws_hub import hub


def broadcast_sync(event: dict[str, Any]) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(hub.broadcast(event))
    else:
        loop.create_task(hub.broadcast(event))
