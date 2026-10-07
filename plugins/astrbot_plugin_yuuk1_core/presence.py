"""Idle-presence policy and lifecycle-owned async task helper."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


def within_active_hours(hour: int, start_hour: int, end_hour: int) -> bool:
    """Use the AstrBot container's configured local timezone and a half-open range."""
    if not (0 <= hour <= 23 and 0 <= start_hour <= 23 and 0 <= end_hour <= 23):
        return False
    if start_hour == end_hour:
        return False
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour


def idle_is_eligible(
    *,
    enabled: bool,
    target_available: bool,
    last_activity_at: float | None,
    last_attempt_at: float | None,
    now: float,
    idle_threshold_seconds: int,
    min_interval_seconds: int,
    active_hour: int,
    active_start_hour: int,
    active_end_hour: int,
) -> bool:
    """Apply every cheap idle gate before any provider request or send."""
    if not enabled or not target_available or last_activity_at is None:
        return False
    if now - last_activity_at < idle_threshold_seconds:
        return False
    if last_attempt_at is not None and now - last_attempt_at < min_interval_seconds:
        return False
    return within_active_hours(active_hour, active_start_hour, active_end_hour)


class ManagedAsyncTask:
    """Own one optional background task and cancel/await it during plugin unload."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(
        self,
        enabled: bool,
        coroutine_factory: Callable[[], Awaitable[None]],
    ) -> bool:
        if not enabled or self.running:
            return False
        self._task = asyncio.create_task(coroutine_factory())
        return True

    async def stop(self) -> None:
        task = self._task
        self._task = None
        if task is None:
            return
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
