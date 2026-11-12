"""Single local worker for persisted import jobs."""

import fcntl
import threading
import time
import uuid

from ..storage.arrangements import ConflictError
from ..storage.db import connect
from .jobs import ImportJobs


def heartbeat(jobs: ImportJobs, worker_id: str) -> None:
    with connect(jobs.store.database) as db:
        db.execute(
            "INSERT INTO worker_heartbeat VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET worker_id=excluded.worker_id,last_seen=excluded.last_seen",
            (worker_id, time.time()),
        )


def run_once(jobs: ImportJobs, worker_id: str, provider=None, pdf_jobs=None) -> bool:
    heartbeat(jobs, worker_id)
    job = jobs.claim_job(worker_id, lease_seconds=360)
    if job is None:
        if pdf_jobs is not None:
            handled = pdf_jobs.run_one(worker_id)
            heartbeat(jobs, worker_id)
            return handled
        return False
    stop = threading.Event()

    def renew():
        while not stop.wait(30):
            if not jobs.renew_lease(job["id"], worker_id):
                return
            heartbeat(jobs, worker_id)

    refresher = threading.Thread(target=renew, daemon=True)
    refresher.start()
    try:
        if job["method"] == "direct":
            jobs.process_direct(job["id"], worker_id)
        elif job["method"] == "local":
            jobs.process_local(job["id"], worker_id)
        elif provider is not None:
            jobs.process_ai(job["id"], worker_id, provider)
        else:
            raise ValueError("Provider not configured")
    except ConflictError:
        pass  # A replacement worker owns the job now.
    except Exception:  # noqa: BLE001 -- no exception text or source content enters logs
        with connect(jobs.store.database) as db:
            db.execute(
                "UPDATE import_jobs SET state='failed',error_code='conversion_failed',worker_id=NULL,lease_until=NULL WHERE id=? AND worker_id=? AND state='processing'",
                (job["id"], worker_id),
            )
    finally:
        stop.set()
        refresher.join()
    heartbeat(jobs, worker_id)
    return True


def run_worker(jobs: ImportJobs) -> None:
    worker_id = str(uuid.uuid4())
    from ..pdf.jobs import PdfJobs
    from .provider_settings import make_provider

    pdf_jobs = PdfJobs(jobs.store)
    with (jobs.store.root / ".worker.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                provider = make_provider(jobs.store)
            except (ValueError, OSError, KeyError, TypeError):
                provider = None
            try:
                handled = run_once(jobs, worker_id, provider, pdf_jobs)
            finally:
                if provider is not None:
                    getattr(provider, "adapter", provider).client.close()
            if not handled:
                time.sleep(5)
