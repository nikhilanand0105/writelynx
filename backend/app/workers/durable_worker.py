import asyncio
import logging
import os
import signal
import sys
from typing import Optional
from backend.app.core.database import SessionLocal
from backend.app.services.job_queue import JobQueueService
from backend.app.services.retention_service import RetentionService
from backend.app.workers.analysis_worker import run_document_analysis_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("writelynx.worker")

WORKER_ID = f"worker_{os.getpid()}"
POLL_INTERVAL_SECONDS = 2
MAINTENANCE_INTERVAL_SECONDS = 60


class DurableWorker:
    def __init__(self):
        self.running = False
        self._last_maintenance = 0

    def handle_signal(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful worker shutdown...")
        self.running = False

    async def run(self):
        self.running = True
        logger.info(f"Writelynx Durable Worker '{WORKER_ID}' started.")

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: self.handle_signal(s, None))
            except NotImplementedError:
                # Windows or unsupported environment
                pass

        while self.running:
            try:
                db = SessionLocal()
                try:
                    # 1. Periodic maintenance: reap stale jobs & execute retention purge
                    now = asyncio.get_event_loop().time()
                    if now - self._last_maintenance > MAINTENANCE_INTERVAL_SECONDS:
                        reaped = JobQueueService.reap_stale_jobs(db)
                        if reaped > 0:
                            logger.info(f"Reaped {reaped} stale/crashed jobs.")
                        purge_stats = RetentionService.run_all_purges(db)
                        if any(purge_stats.values()):
                            logger.info(f"Retention purge stats: {purge_stats}")
                        self._last_maintenance = now

                    # 2. Acquire next job from database queue
                    job = JobQueueService.acquire_next_job(db, WORKER_ID)
                finally:
                    db.close()

                if job:
                    logger.info(f"Worker {WORKER_ID} claimed job {job.id} for document {job.document_id}")
                    params = job.parameters or {}
                    await run_document_analysis_job(
                        document_id=job.document_id,
                        editing_mode=params.get("editing_mode", "academic_revision"),
                        llm_provider=params.get("llm_provider"),
                        job_id=job.id,
                    )
                    logger.info(f"Worker {WORKER_ID} finished job {job.id}")
                else:
                    await asyncio.sleep(POLL_INTERVAL_SECONDS)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker exception: {e}", exc_info=True)
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info(f"Writelynx Durable Worker '{WORKER_ID}' stopped safely.")


if __name__ == "__main__":
    worker = DurableWorker()
    try:
        asyncio.run(worker.run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker process terminated.")
