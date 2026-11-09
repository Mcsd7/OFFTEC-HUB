import asyncio
from collections.abc import Callable
from typing import Any

_LIMIT = asyncio.Semaphore(1)

async def run_blocking(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run blocking adapters off-loop with a device-safe concurrency cap."""
    async with _LIMIT:
        return await asyncio.to_thread(function, *args, **kwargs)
