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

from src.bridge.bridge_events import BridgeEvent, BridgeEventType
from src.bridge.bridge_state import BridgeViewState, DeviceViewState
from src.input.input_client import InputClient
from src.input.keyence_input_client import KeyenceInputClient
from src.input.simulated_input_client import SimulatedInputClient
from src.output.spc_software_client import SpcSerialSettings, SpcSoftwareClient


@dataclass
class BridgeConfig:
    use_simulator: bool = False
    keyence_port: str = "COM5"
    spc_port: str = "COM21"
    spc_baudrate: int = 9600
    spc_timeout: float = 0.01
    spc_terminator: bytes = b"\r\n"
    average_samples: int = 5
    keyence_out_no: int = 2

    simulated_base_height_mm: float = 12.000
    simulated_noise_std_mm: float = 0.002
    simulated_drift_per_sec_mm: float = 0.0001
    simulated_invalid_probability: float = 0.0


class BridgeController:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.input_client: InputClient = self._create_input_client()
        self.spc_client = self._create_spc_client()

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
                state="SPC not connected",
            ),
            use_simulator=config.use_simulator,
        )

        self._events: Queue[BridgeEvent] = Queue()

    # -------------------------------------------------------------------------
    # Public API used by UI
    # -------------------------------------------------------------------------

    def connect(self) -> None:
        self._force_stream_off("connecting")

        self.state.last_error = None
        self.state.keyence.connected = False
        self.state.keyence.state = "Opening port"
        self.state.spc.connected = False
        self.state.spc.state = "Opening SPC peer"
        self._status_changed()

        try:
            self.input_client.open()

            self._send_keyence_confirmed("R0", expected="R0")

            reading = self.input_client.read_once()

            self._emit(BridgeEventType.KEYENCE_SENT, self._read_command_text())
            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)

            if not reading.ok:
                raise RuntimeError(
                    f"Keyence responded, but reading is not OK: {reading.raw}"
                )

            self.state.keyence.connected = True
            self.state.keyence.height_mm = reading.value_mm
            self.state.keyence.state = (
                f"Connected (sim OUT{self.config.keyence_out_no})"
                if self.config.use_simulator
                else f"Connected OUT{self.config.keyence_out_no}"
            )

        except Exception as error:
            self.state.keyence.connected = False
            self.state.keyence.state = "Connection failed"
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"Keyence connection failed: {error}")

            try:
                self.input_client.close()
            except Exception:
                pass

        self._connect_spc_peer()
        self._status_changed()

    def close(self) -> None:
        try:
            self.stop_stream()
        except Exception:
            pass

        try:
            self.input_client.close()
            self.spc_client.disconnect()
        finally:
            self.state.keyence.connected = False
            self.state.keyence.state = "Closed"
            self.state.spc.connected = False
            self.state.spc.state = "Closed"
            self._status_changed()

    def read_once(self) -> None:
        try:
            if not self.state.keyence.connected:
                raise RuntimeError("Cannot read: Keyence is not connected")

            reading = self.input_client.read_average(samples=self.config.average_samples)

            self.state.keyence.height_mm = reading.value_mm
            self.state.keyence.state = f"Read OK ({reading.judgment})"
            self._emit(
                BridgeEventType.KEYENCE_SENT,
                f"{self._read_command_text()} repeated {self.config.average_samples} times",
            )
            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)
            self._status_changed()

        except Exception as error:
            self.state.keyence.state = "Read failed"
            self.state.last_error = str(error)

            self._emit(
                BridgeEventType.ERROR,
                "Read failed: no valid Keyence measurement. "
                "Check target distance/alignment or wait for valid data.",
            )
            self._status_changed()

    def start_stream(self) -> None:
        try:
            if not self.state.keyence.connected:
                raise RuntimeError("Cannot start stream: Keyence is not connected")

            self.state.streaming = True
            self.state.keyence.state = "Streaming"

            if self.state.spc.connected:
                self.state.spc.state = "Receiving stream"
            else:
                self.state.spc.state = "SPC not connected"

            self._emit(BridgeEventType.KEYENCE_SENT, self._stream_command_text())

            if hasattr(self.input_client, "start_streaming"):
                self.input_client.start_streaming()  # type: ignore[attr-defined]
            else:
                raise RuntimeError("Input client does not support streaming")

            self._emit(BridgeEventType.SYSTEM, "Keyence stream started")
            self._status_changed()

        except Exception as error:
            self.state.streaming = False
            self.state.keyence.state = "Stream failed"

            if not self.state.spc.connected:
                self.state.spc.state = "SPC not connected"

            self._set_error(error)


    def stop_stream(self) -> None:
        if not self.state.streaming:
            return

        try:
            self.state.streaming = False

            if self.state.keyence.connected:
                self.state.keyence.state = "Connected"
            else:
                self.state.keyence.state = "Disconnected"

            if self.state.spc.connected:
                self.state.spc.state = "Waiting"
            else:
                self.state.spc.state = "SPC not connected"

            if hasattr(self.input_client, "stop_streaming"):
                self._emit(BridgeEventType.KEYENCE_SENT, "NT")
                self.input_client.stop_streaming()  # type: ignore[attr-defined]

            self._emit(BridgeEventType.SYSTEM, "Keyence stream stopped")
            self._status_changed()

        except Exception as error:
            self._set_error(error)


    def poll_stream_once(self) -> None:
        if not self.state.streaming:
            return

        try:
            if hasattr(self.input_client, "read_latest_stream_reading"):
                reading = self.input_client.read_latest_stream_reading()  # type: ignore[attr-defined]
            elif hasattr(self.input_client, "read_stream_line"):
                reading = self.input_client.read_stream_line()  # type: ignore[attr-defined]
            else:
                raise RuntimeError("Input client does not support streaming")

            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)

            if reading.ok:
                self.state.keyence.height_mm = reading.value_mm
                self.state.keyence.state = f"Streaming OK ({reading.judgment})"
            else:
                self.state.keyence.state = (
                    f"Streaming invalid: info={reading.result_info}, "
                    f"judgment={reading.judgment}"
                )

            self._status_changed()

        except Exception as error:
            self.state.keyence.state = "Stream read failed"
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"Stream read failed: {error}")
            self._status_changed()

    def poll_spc_once(self) -> None:
        if not self.state.spc.connected:
            return

        try:
            message = self.spc_client.read_message()

            if message is None:
                return

            self._emit(BridgeEventType.SPC_RECEIVED, message)

            reply = self.handle_spc_request(message)

            if reply is not None:
                self.spc_client.send_reply(reply)
                self._emit(BridgeEventType.SPC_SENT, reply)

            self._status_changed()

        except Exception as error:
            self.state.spc.connected = False
            self.state.spc.state = "SPC connection error"
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"SPC poll failed: {error}")
            self._status_changed()
                        
    def set_ports(self, *, keyence_port: str, spc_port: str) -> None:
        self._force_stream_off("changing ports")

        if self.state.keyence.connected:
            self.close()

        self.config.keyence_port = keyence_port
        self.config.spc_port = spc_port

        self.state.keyence.port = keyence_port
        self.state.spc.port = spc_port

        self.input_client = self._create_input_client()
        self.spc_client.disconnect()
        self.spc_client = self._create_spc_client()

        self.state.keyence.connected = False
        self.state.keyence.state = (
            "Simulator selected" if self.config.use_simulator else "Real hardware selected"
        )

        self.state.spc.connected = False
        self.state.spc.state = "SPC not connected"

        self._status_changed()

    def set_simulator(self, enabled: bool) -> None:
        self._force_stream_off("changing simulator mode")

        if self.state.keyence.connected:
            self.close()

        self.config.use_simulator = enabled
        self.state.use_simulator = enabled

        self.input_client = self._create_input_client()
        self.spc_client.disconnect()

        self.state.keyence.connected = False
        self.state.keyence.state = (
            "Simulator selected" if enabled else "Real hardware selected"
        )

        self.state.spc.connected = False
        self.state.spc.state = "SPC not connected"

        self._status_changed()

    def send_keyence_command(self, command: str, *, emit_sent: bool = True) -> None:
        """
        Send a manually entered command to the Keyence device.

        emit_sent=False is used when the UI panel has already logged the TX line.
        Controller-owned actions should leave emit_sent=True so the UI still sees
        the command through normal controller events.
        """

        command = command.strip()

        if not command:
            return

        try:
            if not self.state.keyence.connected:
                raise RuntimeError("Cannot send command: Keyence is not connected")

            if self.state.streaming:
                raise RuntimeError(
                    "Cannot send manual Keyence command while streaming is active"
                )

            if emit_sent:
                self._emit(BridgeEventType.KEYENCE_SENT, command)

            response = self.input_client.send_command(command)
            self._emit(BridgeEventType.KEYENCE_RECEIVED, response)
            self._apply_keyence_response_to_state(response)
            self._status_changed()

        except Exception as error:
            self.state.last_error = str(error)
            self.state.keyence.state = "Manual command failed"
            self._emit(BridgeEventType.ERROR, f"Keyence command failed: {error}")
            self._status_changed()

    def send_spc_command(self, command: str, *, emit_sent: bool = True) -> None:
        """
        Send a manually entered outbound SPC message for debugging.

        The normal process path is SPC -> Python request, then Python -> SPC reply.
        This manual method is useful when testing the virtual COM pair by hand.
        """

        command = command.strip()

        if not command:
            return

        if not self.state.spc.connected:
            self._emit(BridgeEventType.ERROR, "SPC command failed: SPC is not connected")
            return

        try:
            self.spc_client.send_reply(command)

            if emit_sent:
                self._emit(BridgeEventType.SPC_SENT, command)
            else:
                self.state.spc_tx_count += 1

            self._status_changed()

        except Exception as error:
            self.state.last_error = str(error)
            self.state.spc.state = "Manual send failed"
            self._emit(BridgeEventType.ERROR, f"SPC send failed: {error}")
            self._status_changed()

    def handle_spc_request(self, message: str) -> str | None:
        command = message.strip().upper()

        if not command:
            return None

        if command == "PING":
            return "PONG"

        if command == "STATUS":
            height = self._format_latest_height_reply()
            return (
                f"KEYENCE_CONNECTED={int(self.state.keyence.connected)};"
                f"SPC_CONNECTED={int(self.state.spc.connected)};"
                f"STREAMING={int(self.state.streaming)};"
                f"HEIGHT={height}"
            )

        if command in {"GET_HEIGHT", "HEIGHT?"}:
            return self._format_latest_height_reply()

        if command == "READ_ONCE":
            return self._read_height_for_spc()

        if command == "START_STREAM":
            return self._start_stream_for_spc()

        if command == "STOP_STREAM":
            return self._stop_stream_for_spc()

        return f"ERROR UNKNOWN_COMMAND {message.strip()}"

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

    def _force_stream_off(self, reason: str) -> None:
        if not self.state.streaming:
            return

        try:
            if hasattr(self.input_client, "stop_streaming"):
                self._emit(BridgeEventType.KEYENCE_SENT, "NT")
                self.input_client.stop_streaming()  # type: ignore[attr-defined]

        except Exception as error:
            self._emit(
                BridgeEventType.ERROR,
                f"Failed to stop stream while {reason}: {error}",
            )

        finally:
            self.state.streaming = False

            if self.state.keyence.connected:
                self.state.keyence.state = "Connected"
            else:
                self.state.keyence.state = "Disconnected"

            if self.state.spc.connected:
                self.state.spc.state = "Waiting"
            else:
                self.state.spc.state = "SPC not connected"

            self._status_changed()

    def _emit(self, event_type: BridgeEventType, message: str) -> None:
        if event_type == BridgeEventType.SPC_RECEIVED:
            self.state.spc_rx_count += 1

        elif event_type == BridgeEventType.SPC_SENT:
            self.state.spc_tx_count += 1

        elif event_type == BridgeEventType.KEYENCE_SENT:
            self.state.keyence_tx_count += 1

        elif event_type == BridgeEventType.KEYENCE_RECEIVED:
            self.state.keyence_rx_count += 1

        self._events.put(BridgeEvent(event_type, message))

    def _status_changed(self) -> None:
        self.state.last_update = datetime.now()
        self._events.put(BridgeEvent(BridgeEventType.STATUS_CHANGED, "status changed"))

    def _set_error(self, error: Exception) -> None:
        self.state.last_error = str(error)
        self.state.keyence.state = "Error"

        if not self.state.spc.connected:
            self.state.spc.state = "SPC not connected"

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

    def _apply_keyence_response_to_state(self, response: str) -> None:
        """Update displayed Keyence state when a manual command returns data."""

        response = response.strip()

        if response.startswith("MS,"):
            try:
                from src.input.keyence_protocol import parse_ms3_response

                reading = parse_ms3_response(response)
                self.state.keyence.height_mm = reading.value_mm
                self.state.keyence.state = (
                    f"Manual read OK ({reading.judgment})"
                    if reading.ok
                    else f"Manual read invalid ({reading.judgment})"
                )
                return
            except Exception:
                # Still show the raw response in the comms panel; just don't let
                # display-state parsing failure hide the actual device response.
                pass

        if response.startswith("ER,"):
            self.state.keyence.state = f"Manual command returned error: {response}"
        else:
            self.state.keyence.state = f"Manual command response: {response}"

    def _read_command_text(self) -> str:
        if hasattr(self.input_client, "read_command"):
            return self.input_client.read_command()  # type: ignore[attr-defined]

        return f"MS,3,{self.config.keyence_out_no}"

    def _stream_command_text(self) -> str:
        if hasattr(self.input_client, "stream_command"):
            return self.input_client.stream_command()  # type: ignore[attr-defined]

        return f"NS,3,{self._out_mask(self.config.keyence_out_no)}"

    def _connect_spc_peer(self) -> None:
        try:
            self.spc_client.connect()
            self.state.spc.connected = True
            self.state.spc.state = "Waiting for SPC requests"
            self._emit(
                BridgeEventType.SYSTEM,
                f"SPC peer listening on {self.config.spc_port}",
            )

        except Exception as error:
            self.state.spc.connected = False
            self.state.spc.state = "SPC not connected"
            self.state.last_error = str(error)
            self._emit(
                BridgeEventType.ERROR,
                f"SPC peer connection failed on {self.config.spc_port}: {error}",
            )

    def _format_latest_height_reply(self) -> str:
        if self.state.keyence.height_mm is None:
            return "NO_HEIGHT"

        return f"{self.state.keyence.height_mm:.5f}"

    def _read_height_for_spc(self) -> str:
        if not self.state.keyence.connected:
            return "ERROR KEYENCE_NOT_CONNECTED"

        if self.state.streaming:
            return "ERROR STREAMING_ACTIVE"

        try:
            reading = self.input_client.read_average(samples=self.config.average_samples)

            self.state.keyence.height_mm = reading.value_mm
            self.state.keyence.state = f"SPC read OK ({reading.judgment})"

            self._emit(
                BridgeEventType.KEYENCE_SENT,
                f"{self._read_command_text()} repeated {self.config.average_samples} times",
            )
            self._emit(BridgeEventType.KEYENCE_RECEIVED, reading.raw)

            return self._format_latest_height_reply()

        except Exception as error:
            self.state.keyence.state = "SPC read failed"
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"SPC READ_ONCE failed: {error}")
            return f"ERROR {error}"

    def _start_stream_for_spc(self) -> str:
        if self.state.streaming:
            return "OK"

        self.start_stream()

        if self.state.streaming:
            return "OK"

        return f"ERROR {self.state.last_error or 'STREAM_NOT_STARTED'}"

    def _stop_stream_for_spc(self) -> str:
        if not self.state.streaming:
            return "OK"

        self.stop_stream()

        if not self.state.streaming:
            return "OK"

        return f"ERROR {self.state.last_error or 'STREAM_NOT_STOPPED'}"

    def _create_input_client(self) -> InputClient:
        if self.config.use_simulator:
            return SimulatedInputClient(
                base_height_mm=self.config.simulated_base_height_mm,
                noise_std_mm=self.config.simulated_noise_std_mm,
                drift_per_sec_mm=self.config.simulated_drift_per_sec_mm,
                invalid_probability=self.config.simulated_invalid_probability,
                out_no=self.config.keyence_out_no,
            )

        return KeyenceInputClient(
            port=self.config.keyence_port,
            out_no=self.config.keyence_out_no,
        )

    def _create_spc_client(self) -> SpcSoftwareClient:
        return SpcSoftwareClient(
            SpcSerialSettings(
                port=self.config.spc_port,
                baudrate=self.config.spc_baudrate,
                timeout=self.config.spc_timeout,
                terminator=self.config.spc_terminator,
            )
        )

    @staticmethod
    def _out_mask(out_no: int) -> str:
        if not 1 <= out_no <= 8:
            raise ValueError(f"Invalid OUT number: {out_no}")

        bits = ["0"] * 8
        bits[out_no - 1] = "1"
        return "".join(bits)
