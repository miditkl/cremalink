"""
This module defines and manages the background jobs for the local server.
These jobs run periodically in asyncio tasks to handle keep-alive, status
monitoring, and re-keying operations.
"""
import asyncio
from typing import List

from cremalink.local_server_app.device_adapter import DeviceAdapter
from cremalink.local_server_app.state import LocalServerState
from cremalink.local_server_app.config import ServerSettings


class JobManager:
    """A simple manager for starting and stopping asyncio background tasks."""

    def __init__(self):
        self.tasks: List[asyncio.Task] = []

    def start(self, coro, name: str):
        """Creates an asyncio task from a coroutine and adds it to the manager."""
        task = asyncio.create_task(coro, name=name)
        self.tasks.append(task)

    async def stop(self):
        """Cancels and cleans up all managed tasks."""
        for task in self.tasks:
            task.cancel()
        # Wait for all tasks to acknowledge cancellation
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()


async def nudger_job(st: LocalServerState, adapter: DeviceAdapter, settings: ServerSettings, stop_event: asyncio.Event):
    """
    Periodically "nudges" the device by sending a registration request.

    This is a key part of the protocol. The device often needs to be prompted
    to send data. This job ensures that registration is maintained, especially
    if there are pending commands in the queue.
    """
    interval = settings.nudger_poll_interval
    while not stop_event.is_set():
        try:
            # Nudge if there are commands waiting or if we aren't registered.
            async with st.lock:
                should_nudge = len(st.command_queue) > 0 or not st.registered
            if should_nudge:
                await adapter.register_with_device(st)
        except Exception as exc:
            st.log("local_reg_nudge_failed", {"error": str(exc)})
            # If nudging fails, it might be a key issue, so trigger a rekey.
            await st.rekey()
        
        try:
            # Wait for the specified interval or until the stop event is set.
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def monitor_job(st: LocalServerState, settings: ServerSettings, stop_event: asyncio.Event):
    """
    Periodically queues a request to fetch the device's monitoring status.
    """
    interval = settings.monitor_poll_interval
    while not stop_event.is_set():
        try:
            # Only queue a request if the server is configured and another request isn't already pending.
            async with st.lock:
                ready = st.is_configured() and not st._monitor_request_pending
            if ready:
                await st.queue_monitor()
        except Exception as exc:
            st.log("monitor_poll_failed", {"error": str(exc)})
        
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def rekey_job(state: LocalServerState, adapter: DeviceAdapter, settings: ServerSettings, stop_event: asyncio.Event):
    """
    Periodically triggers a full cryptographic re-keying process.

    This enhances security by ensuring session keys are not long-lived.
    """
    interval = settings.rekey_interval_seconds
    while not stop_event.is_set():
        try:
            # Wait for the rekey interval.
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            # Interval elapsed, proceed with re-keying.
            pass
        try:
            state.log("rekey_triggered", {"interval": interval})
            # Reset keys and re-register with the device.
            await state.rekey()
            await adapter.register_with_device(state)
        except Exception as exc:
            state.log("rekey_failed", {"error": str(exc)})
