"""
Application controller.

This is the object that connects the UI to your actual bridge logic.

The UI should mostly call methods on this class:
    controller.connect()
    controller.start_stream()
    controller.stop_stream()
    controller.read_once()
    controller.set_ports(...)
    controller.set_simulator(...)

Then the UI reads:
    controller.state
    controller.drain_events()

Later, this controller is where you add the SPC serial client and background
threads/async tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from typing import Optional

from src.bridge.bridge_events import BridgeEvent, BridgeEventType
from src.bridge.bridge_state import BridgeViewState, DeviceViewState
from src.input.input_client import InputClient
from src.input.simulated_input_client import SimulatedInputClient
from src.input.keyence_input_client import KeyenceInputClient


@dataclass
class BridgeConfig:
    use_simulator: bool = True
    keyence_port: str = "COM3"
    spc_port: str = "COM9"
    average_samples: int = 5


class BridgeController:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.input_client: InputClient = self._create_input_client()

        self.state = BridgeViewState(
            keyence=DeviceViewState(
                connected=False,
                port=config.keyence_port,
                height_mm=None,
                state="Simulator selected" if config.use_simulator else "Real hardware selected",
            ),
            spc=DeviceViewState(
                connected=False,
                port=config.spc_port,
                height_mm=None,
                state="Waiting",
            ),
            use_simulator=config.use_simulator,
        )

        self._events: Queue[BridgeEvent] = Queue()
    # -------------------------------------------------------------------------
    # Public API used by UI
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        try:
            self.state.last_error = None
            self.state.keyence.connected = False
            self.state.keyence.state = "Opening port"
            self._status_changed()

            self.input_client.open()

            self._send_keyence_confirmed("R0", expected="R0")
            self._send_keyence_confirmed("MC,1", expected="MC")
            self._send_keyence_confirmed("LC,1", expected="LC")

            self.state.keyence.connected = True
            self.state.keyence.state = (
                "Connected (sim)" if self.config.use_simulator else "Connected"
            )

            self.state.spc.connected = False
            self.state.spc.state = "SPC client not connected"

            self._status_changed()

        except Exception as error:
            self.state.keyence.connected = False
            self.state.keyence.state = "Connection failed"
            self.state.spc.connected = False
            self.state.spc.state = "Connection failed"
            self._set_error(error)
                        
    def close(self) -> None:
        try:
            self.stop_stream()
        except Exception:
            pass

        try:
            self.input_client.close()
        finally:
            self.state.keyence.connected = False
            self.state.keyence.state = "Closed"
            self.state.spc.connected = False
            self.state.spc.state = "Closed"
            self._status_changed()

    def read_once(self) -> None:
        try:
            reading = self.input_client.read_average(samples=self.config.average_samples)
            self.state.keyence.height_mm = reading.value_mm
            self.state.keyence.state = f"Read OK ({reading.judgment})"
            self.state.keyence_rx_count += 1
            self._emit(
                BridgeEventType.KEYENCE_SENT,
                f"MS,3,1 repeated {self.config.average_samples} times",
            )
            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)
            self._status_changed()

        except Exception as error:
            self._set_error(error)

    def start_stream(self) -> None:
        try:
            self.state.streaming = True
            self.state.keyence.state = "Streaming"
            self.state.spc.state = "Receiving stream"

            # If the concrete client supports streaming, use it.
            if hasattr(self.input_client, "start_streaming"):
                self.input_client.start_streaming()  # type: ignore[attr-defined]
                self._emit(BridgeEventType.KEYENCE_SENT, "NS,3,10000000")
            else:
                self._emit(BridgeEventType.KEYENCE_SENT, "STREAM_START_PLACEHOLDER")

            self._emit(BridgeEventType.SPC_RECEIVED, "START")
            self._status_changed()

        except Exception as error:
            self._set_error(error)

    def stop_stream(self) -> None:
        if not self.state.streaming:
            return

        try:
            self.state.streaming = False
            self.state.keyence.state = "Connected"
            self.state.spc.state = "Waiting"

            if hasattr(self.input_client, "stop_streaming"):
                self.input_client.stop_streaming()  # type: ignore[attr-defined]
                self._emit(BridgeEventType.KEYENCE_SENT, "NT")
            else:
                self._emit(BridgeEventType.KEYENCE_SENT, "STREAM_STOP_PLACEHOLDER")

            self._emit(BridgeEventType.SPC_RECEIVED, "STOP")
            self._status_changed()

        except Exception as error:
            self._set_error(error)

    def poll_stream_once(self) -> None:
        """
        Called by the UI timer for now.

        Later, this should probably move into a worker/thread so serial reads never
        block the Textual UI.
        """
        if not self.state.streaming:
            return

        try:
            if hasattr(self.input_client, "read_stream_line"):
                reading = self.input_client.read_stream_line()  # type: ignore[attr-defined]
            else:
                reading = self.input_client.read_once()

            self.state.keyence.height_mm = reading.value_mm
            self.state.keyence_rx_count += 1
            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)
            self._status_changed()

        except Exception as error:
            self._set_error(error)

    def set_ports(self, *, keyence_port: str, spc_port: str) -> None:
        if self.state.keyence.connected:
            self.close()

        self.config.keyence_port = keyence_port
        self.config.spc_port = spc_port

        self.state.keyence.port = keyence_port
        self.state.spc.port = spc_port

        self.input_client = self._create_input_client()

        self._status_changed()

    def set_simulator(self, enabled: bool) -> None:
        if self.state.keyence.connected:
            self.close()

        self.config.use_simulator = enabled
        self.state.use_simulator = enabled

        self.input_client = self._create_input_client()

        self.state.keyence.connected = False
        self.state.keyence.state = (
            "Simulator selected" if enabled else "Real hardware selected"
        )

        self._status_changed()
        
    def set_continuous_visible(self, visible: bool) -> None:
        self.state.continuous_visible = visible
        self._status_changed()

    def drain_events(self) -> list[BridgeEvent]:
        events: list[BridgeEvent] = []
        while not self._events.empty():
            events.append(self._events.get())
        return events

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _emit(self, event_type: BridgeEventType, message: str) -> None:
        if event_type == BridgeEventType.SPC_RECEIVED:
            self.state.spc_rx_count += 1
        elif event_type == BridgeEventType.KEYENCE_SENT:
            self.state.keyence_tx_count += 1

        self._events.put(BridgeEvent(event_type, message))

    def _status_changed(self) -> None:
        self.state.last_update = datetime.now()
        self._events.put(BridgeEvent(BridgeEventType.STATUS_CHANGED, "status changed"))

    def _set_error(self, error: Exception) -> None:
        self.state.last_error = str(error)
        self.state.keyence.state = "Error"
        self._events.put(BridgeEvent(BridgeEventType.ERROR, str(error)))
        self._status_changed()

    def _send_keyence_confirmed(self, command: str, expected: str) -> str:
        self._emit(BridgeEventType.KEYENCE_SENT, command)

        response = self.input_client.send_command(command)
        self._emit(BridgeEventType.KEYENCE_RECEIVED, response)

        if response != expected:
            raise RuntimeError(
                f"Unexpected Keyence response for {command!r}: "
                f"got {response!r}, expected {expected!r}"
            )

        return response
    
    def _create_input_client(self) -> InputClient:
        if self.config.use_simulator:
            return SimulatedInputClient()

        return KeyenceInputClient(port=self.config.keyence_port)