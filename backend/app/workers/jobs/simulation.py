import asyncio
from collections.abc import Awaitable, Callable

ProgressReporter = Callable[[int], Awaitable[None]]


async def simulate_progress(report_progress: ProgressReporter) -> None:
    for progress in (10, 30, 55, 75, 95):
        await asyncio.sleep(0.5)
        await report_progress(progress)
