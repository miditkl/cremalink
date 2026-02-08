"""
This module defines the FastAPI application for the local proxy server.
It creates all the API endpoints, manages application state, and handles the
startup and shutdown of background services.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional, AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRouter

from cremalink.local_server_app.config import ServerSettings, get_settings
from cremalink.local_server_app.device_adapter import DeviceAdapter
from cremalink.local_server_app.jobs import (
    JobManager,
    monitor_job,
    nudger_job,
    rekey_job,
)
from cremalink.local_server_app.logging import create_logger
from cremalink.local_server_app.models import (
    CommandPollResponse,
    CommandRequest,
    ConfigureRequest,
    EncPayload,
    KeyExchangeRequest,
    MonitorResponse,
    PropertiesResponse,
)
from cremalink.local_server_app import protocol
from cremalink.local_server_app.state import LocalServerState


def create_app(
    settings: Optional[ServerSettings] = None,
    device_adapter: Optional[DeviceAdapter] = None,
    logger=None,
) -> FastAPI:
    """
    Application factory for the FastAPI server.

    Initializes all components (state, settings, adapter, jobs) and wires up
    the API routes, startup/shutdown events, and dependencies.

    Returns:
        A configured FastAPI application instance.
    """
    # Initialize core components, allowing for dependency injection in tests.
    settings = settings or get_settings()
    logger = logger or create_logger("local_server", settings.log_ring_size)
    state = LocalServerState(settings, logger)
    adapter = device_adapter or DeviceAdapter(settings, logger)
    stop_event = asyncio.Event()
    jobs = JobManager()

    print(f"Starting cremalink local server on http://{settings.server_ip}:{settings.server_port}...")
    print(f"IP address advertised to the coffee machine: {settings.advertised_ip}")

    # Define the application lifespan context manager for startup/shutdown events.
    @asynccontextmanager
    async def lifespan(app_: FastAPI) -> AsyncIterator[None]:
        await app_.router.startup()
        try:
            yield
        finally:
            await app_.router.shutdown()

    app = FastAPI(title="cremalink Local Server", version="2.0.0")
    app.state.local_state = state
    app.state.settings = settings
    app.state.adapter = adapter
    app.state.jobs = jobs
    app.state.stop_event = stop_event
    app.state.logger = logger

    router = APIRouter()

    # --- Dependency Injection ---
    async def get_state() -> LocalServerState:
        return state

    async def get_adapter() -> DeviceAdapter:
        return adapter

    @router.post("/configure")
    async def configure(req: ConfigureRequest, st: LocalServerState = Depends(get_state)):
        """Configures the server with device connection details."""
        await st.configure(
            dsn=req.dsn,
            device_ip=req.device_ip,
            lan_key=req.lan_key,
            device_scheme=req.device_scheme,
            monitor_property_name=req.monitor_property_name,
            data_request_property_name=req.data_request_property_name
        )
        # Attempt an initial registration with the device.
        try:
            await adapter.register_with_device(st)
        except Exception as exc:
            st.log("local_reg_initial_failed", {"error": str(exc)})
        return {"status": "configured", "dsn": req.dsn, "device_scheme": req.device_scheme}

    @router.post("/command")
    async def command(req: CommandRequest, st: LocalServerState = Depends(get_state), ad: DeviceAdapter = Depends(get_adapter)):
        """Queues a command to be sent to the device."""
        if not st.is_configured():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server not configured")
        try:
            await ad.register_with_device(st)
            await st.queue_command(req.command)
        except OverflowError as exc:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc))
        except ConnectionError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        return {"status": "queued", "seq": st.seq}

    @router.get("/get_monitor", response_model=MonitorResponse)
    async def get_monitor(st: LocalServerState = Depends(get_state)):
        """Gets the last known monitor status."""
        return await st.snapshot_monitor()

    @router.get("/refresh_monitor")
    async def refresh_monitor(st: LocalServerState = Depends(get_state), ad: DeviceAdapter = Depends(get_adapter)):
        """Queues a request to refresh the monitor status."""
        try:
            await ad.register_with_device(st)
            await st.queue_monitor()
        except ConnectionError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        return PlainTextResponse("queued monitor refresh")

    @router.get("/get_properties", response_model=PropertiesResponse)
    async def get_properties(st: LocalServerState = Depends(get_state), ad: DeviceAdapter = Depends(get_adapter)):
        """Gets the last known device properties."""
        try:
            await ad.register_with_device(st)
            await st.queue_properties()
        except ConnectionError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        return await st.snapshot_properties()

    @router.get("/properties/{property_name}")
    async def get_property(property_name: str, st: LocalServerState = Depends(get_state)):
        """Gets a single property value from the last known snapshot."""
        value = await st.get_property_value(property_name)
        if value is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        return {"name": property_name, "value": value}

    @router.get("/health")
    async def health():
        return PlainTextResponse("ok")

    @router.get("/logs")
    async def logs():
        ring_handler = next((h for h in logger.handlers if hasattr(h, "get_events")), None)
        events = ring_handler.__getattribute__("get_events") if ring_handler else []
        return {"events": events, "last_command": state.last_command}

    @router.get("/debug_queue")
    async def debug_queue(st: LocalServerState = Depends(get_state)):
        async with st.lock:  # type: ignore[attr-defined]
            next_payload = st.command_queue[0] if st.command_queue else None
            queued = len(st.command_queue)
            seq = st.seq
        return {"queued": queued, "next_payload": next_payload, "seq": seq}

    @router.get("/monitor")
    async def monitor(st: LocalServerState = Depends(get_state)):
        async with st.lock:  # type: ignore[attr-defined]
            return JSONResponse(st.last_monitor)

    # --- Device-Facing API Endpoints (called by the coffee machine) ---

    @router.post("/local_lan/key_exchange.json")
    async def key_exchange(req: KeyExchangeRequest, st: LocalServerState = Depends(get_state)):
        """Handles the cryptographic key exchange request from the device."""
        if not st.lan_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Server not configured")
        exchange = req.key_exchange
        await st.init_crypto(random_1=exchange.random_1, time_1=exchange.time_1)
        st.log("key_exchange", {"random_1": exchange.random_1, "time_1": exchange.time_1})
        return JSONResponse({"random_2": st.random_2, "time_2": int(st.time_2)}, status_code=status.HTTP_202_ACCEPTED)

    async def serve_command_poll(st: LocalServerState) -> CommandPollResponse:
        """Shared logic for serving the next command to the device."""
        if not st.keys_ready():
            st.log("command_poll_no_keys", {"queued": len(st.command_queue)})
            return CommandPollResponse(enc="", sign="", seq=st.seq)

        next_item = await st.next_command_payload()
        payload, current_seq = next_item["payload"], next_item["seq"]
        
        enc, new_iv = protocol.encrypt_payload(payload, st.app_crypto_key, st.app_iv_seed)
        st.app_iv_seed = new_iv
        sign = protocol.sign_payload(payload, st.app_sign_key)
        async with st.lock:
            st.command_payload = protocol.build_empty_payload(st.seq)
        st.log(
            "command_served",
            {"seq": current_seq, "queued_remaining": len(st.command_queue), "payload_size": len(payload)},
        )
        return CommandPollResponse(enc=enc, sign=sign, seq=current_seq)

    @router.get("/local_lan/commands.json", response_model=CommandPollResponse)
    async def poll_commands_get(st: LocalServerState = Depends(get_state)):
        """Endpoint for the device to poll for commands (GET)."""
        return await serve_command_poll(st)

    @router.post("/local_lan/commands.json", response_model=CommandPollResponse)
    async def poll_commands_post(st: LocalServerState = Depends(get_state)):
        """Endpoint for the device to poll for commands (POST)."""
        return await serve_command_poll(st)

    @router.post("/local_lan/property/datapoint.json")
    async def datapoint(payload: EncPayload, st: LocalServerState = Depends(get_state)):
        """Endpoint for the device to push encrypted data to."""
        if not st.dev_crypto_key or not st.dev_iv_seed:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Keys not initialized")
        
        decrypted_bytes, new_iv = protocol.decrypt_payload(payload.enc, st.dev_crypto_key, st.dev_iv_seed)
        st.dev_iv_seed = new_iv
        
        try:
            decoded = decrypted_bytes.decode("utf-8")
            decoded_json = json.loads(decoded)
        except UnicodeDecodeError:
            st.log("datapoint_decode_failed_utf8", {"cipher": payload.enc[:32]})
            async with st.lock:
                st._monitor_request_pending = False
                st._properties_request_pending = False
            return Response(status_code=status.HTTP_200_OK)
        except json.JSONDecodeError:
            st.log("datapoint_decode_failed_json", {"decoded_prefix": decrypted_bytes[:64].decode('utf-8', 'ignore')})
            async with st.lock:
                st._monitor_request_pending = False
                st._properties_request_pending = False
            return Response(status_code=status.HTTP_200_OK)
        
        await st.handle_datapoint(decoded_json)
        return {}

    @router.get("/register")
    async def register(st: LocalServerState = Depends(get_state), ad: DeviceAdapter = Depends(get_adapter)):
        try:
            await ad.register_with_device(st)
        except Exception as exc:
            st.log("internal_server_error", {"status_code": status.HTTP_500_INTERNAL_SERVER_ERROR, "error": str(exc)})
            return PlainTextResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return PlainTextResponse("registered")

    app.include_router(router)

    async def startup_event():
        if settings.enable_nudger_job:
            jobs.start(nudger_job(state, adapter, settings, stop_event), name="nudger")
        if settings.enable_monitor_job:
            jobs.start(monitor_job(state, settings, stop_event), name="monitor")
        if settings.enable_rekey_job:
            jobs.start(rekey_job(state, adapter, settings, stop_event), name="rekey")

    app.add_event_handler("startup", startup_event)

    async def shutdown_event():
        stop_event.set()
        await jobs.stop()
        await adapter.close()

    app.add_event_handler("shutdown", shutdown_event)

    return app
