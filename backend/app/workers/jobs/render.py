from app.workers.jobs.simulation import ProgressReporter, simulate_progress


async def run(_: int, report_progress: ProgressReporter) -> None:
    await simulate_progress(report_progress)
