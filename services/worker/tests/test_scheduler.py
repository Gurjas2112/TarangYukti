from ty_worker.__main__ import build_scheduler


def test_jobs_registered() -> None:
    ids = {j.id for j in build_scheduler().get_jobs()}
    assert ids == {"watch", "outbox", "ingest", "agent_purge"}
