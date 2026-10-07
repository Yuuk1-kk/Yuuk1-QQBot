from __future__ import annotations

import asyncio

from plugins.astrbot_plugin_yuuk1_core.logic import normalize_config
from plugins.astrbot_plugin_yuuk1_core.presence import (
    ManagedAsyncTask,
    idle_is_eligible,
    within_active_hours,
)


def _eligible(**changes: object) -> bool:
    values: dict[str, object] = {
        "enabled": True,
        "target_available": True,
        "last_activity_at": 100.0,
        "last_attempt_at": None,
        "now": 2000.0,
        "idle_threshold_seconds": 1800,
        "min_interval_seconds": 21600,
        "active_hour": 12,
        "active_start_hour": 9,
        "active_end_hour": 23,
    }
    values.update(changes)
    return idle_is_eligible(**values)  # type: ignore[arg-type]


def test_idle_presence_is_disabled_by_default_and_has_no_task() -> None:
    settings = normalize_config({})
    assert not settings.idle_speak_enabled

    async def run() -> None:
        task = ManagedAsyncTask()
        started = False

        async def should_never_run() -> None:
            nonlocal started
            started = True

        assert not task.start(settings.idle_speak_enabled, should_never_run)
        await asyncio.sleep(0)
        assert not task.running
        assert not started
        await task.stop()

    asyncio.run(run())


def test_idle_requires_target_threshold_active_hours_and_cooldown() -> None:
    assert _eligible()
    assert not _eligible(enabled=False)
    assert not _eligible(target_available=False)
    assert not _eligible(last_activity_at=None)
    assert not _eligible(now=1000.0)
    assert not _eligible(last_attempt_at=1990.0)
    assert not _eligible(active_hour=2)


def test_active_hours_support_daytime_and_overnight_windows() -> None:
    assert within_active_hours(9, 9, 23)
    assert not within_active_hours(23, 9, 23)
    assert within_active_hours(23, 22, 6)
    assert within_active_hours(5, 22, 6)
    assert not within_active_hours(12, 22, 6)
    assert not within_active_hours(9, 9, 9)


def test_restart_has_no_idle_target_or_immediate_activity_eligibility() -> None:
    assert not _eligible(target_available=False)
    assert not _eligible(last_activity_at=1999.0, now=2000.0)
    assert not _eligible(last_attempt_at=0.0, now=1000.0)


def test_idle_task_starts_once_and_is_cancelled_on_cleanup() -> None:
    async def run() -> None:
        task = ManagedAsyncTask()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def loop() -> None:
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()

        assert task.start(True, loop)
        await started.wait()
        assert task.running
        assert not task.start(True, loop)
        await task.stop()
        assert cancelled.is_set()
        assert not task.running

    asyncio.run(run())
