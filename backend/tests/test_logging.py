from backend.app.core.logging import _human_readable_renderer


def test_human_readable_renderer_formats_level_time_message_and_reason() -> None:
    rendered = _human_readable_renderer(
        None,
        "test",
        {
            "level": "info",
            "timestamp": "2026-06-03T08:43:15Z",
            "event": "runtime_refresh_deployments_completed",
            "reason": "scheduler",
            "refreshed": 1,
            "failed": 0,
        },
    )

    assert rendered == (
        "INFO - 2026-06-03T08:43:15Z : runtime refresh deployments completed "
        "| reason=scheduler failed=0 refreshed=1"
    )
