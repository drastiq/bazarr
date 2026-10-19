import pytest

from app import jobs_queue as jobs_queue_module
from app.jobs_queue import JobsQueue


@pytest.fixture
def queue(monkeypatch):
    monkeypatch.setattr(jobs_queue_module, "event_stream", lambda **kwargs: None)
    return JobsQueue()


def _add_sync(queue, srt_path):
    return queue.feed_jobs_pending_queue(job_name=f"Syncing {srt_path}", module="bazarr.subtitles.sync",
                                         func="sync_subtitles", kwargs={"srt_path": srt_path}, is_progress=True)


def _cancel(queue, job_id, new_name=None):
    job = next(job for job in queue.jobs_pending_queue if job.job_id == job_id)
    queue.jobs_pending_queue.remove(job)
    job.kwargs["job_id"] = job.job_id
    job.status = "canceled"
    if new_name:
        job.job_name = new_name
    queue.jobs_canceled_queue.append(job)
    return job


def test_rerun_canceled_job_queues_a_fresh_copy(queue):
    job_id = _add_sync(queue, "a.srt")
    canceled = _cancel(queue, job_id, new_name="Sync canceled a.srt")

    new_job_id = queue.rerun_canceled_job(job_id)

    assert new_job_id and new_job_id != job_id
    assert list(queue.jobs_canceled_queue) == []
    (new_job,) = queue.jobs_pending_queue
    assert new_job.job_name == "Syncing a.srt"
    assert new_job.kwargs == {"srt_path": "a.srt"}
    assert new_job.status == "pending"
    assert (new_job.module, new_job.func, new_job.is_progress) == (canceled.module, canceled.func, True)


def test_rerun_ignores_jobs_that_are_not_canceled(queue):
    job_id = _add_sync(queue, "a.srt")

    assert queue.rerun_canceled_job(job_id) is False
    assert queue.rerun_canceled_job(12345) is False
    assert len(queue.jobs_pending_queue) == 1


def test_rerun_keeps_canceled_job_when_identical_job_already_queued(queue):
    job_id = _add_sync(queue, "a.srt")
    _cancel(queue, job_id)
    _add_sync(queue, "a.srt")

    assert queue.rerun_canceled_job(job_id) is False
    assert len(queue.jobs_canceled_queue) == 1
    assert len(queue.jobs_pending_queue) == 1
