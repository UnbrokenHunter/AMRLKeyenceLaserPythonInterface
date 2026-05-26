"""Application controller and bridge coordinator.

BridgeController is the central state owner for the app. The Textual UI calls
methods on this object to connect, read, start/stop streams, update settings,
toggle simulator mode, and handle manual commands. The UI then reads
``controller.state`` and drains ``controller.drain_events()`` to update panels.

SPC request flow:
    1. SpcSoftwareClient reads a line from the Python side of the com0com pair.
    2. poll_spc_once emits SPC_RECEIVED and passes the message to the command registry.
    3. The registry dispatches a handler, usually back into this controller.
    4. The controller talks to Keyence, simulator, or tracking state as needed.
    5. poll_spc_once sends the reply back to SPC and emits SPC_SENT.

Keyence read flow:
    1. The UI or SPC asks for a height.
    2. The controller calls the active InputClient.
    3. Real mode uses KeyenceInputClient; simulator mode uses SimulatedInputClient.
    4. Valid readings update bridge state, live height display, and active trackers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Queue

from src.bridge.csv_export import CsvHeightSample, export_height_samples
from src.bridge.bridge_events import BridgeEvent, BridgeEventType
from src.bridge.spc_commands import (
    SPC_FAILURE_STATUS,
    SPC_SUCCESS_STATUS,
    SpcCommandContext,
    create_default_spc_command_registry,
)
from src.bridge.bridge_state import BridgeViewState, DeviceViewState
from src.bridge.height_tracking import HeightTrackerManager
from src.input.input_client import InputClient
from src.input.keyence_input_client import KeyenceInputClient
from src.input.simulated_input_client import SimulatedInputClient
from src.output.spc_software_client import SpcSoftwareClient
from src.serial_settings import (
    SerialPortSettings,
    SpcSerialSettings,
    line_ending_to_terminator,
    terminator_to_label,
)


@dataclass
class BridgeConfig:
    use_simulator: bool = False
    keyence_port: str = "COM5"
    keyence_baudrate: int = 115200
    keyence_timeout: float = 1.0
    spc_port: str = "COM21"
    spc_baudrate: int = 9600
    spc_timeout: float = 0.01
    spc_terminator: bytes = b"\r\n"
    average_samples: int = 5
    keyence_out_no: int = 1

    simulated_base_height_mm: float = 12.000
    simulated_noise_std_mm: float = 0.002
    simulated_drift_per_sec_mm: float = 0.0001
    simulated_invalid_probability: float = 0.0
    log_keep_count: int = 25


class BridgeController:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.input_client: InputClient = self._create_input_client()
        self.spc_client = self._create_spc_client()
        self.spc_commands = create_default_spc_command_registry()
        self.height_trackers = HeightTrackerManager()

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
            keyence_out_no=config.keyence_out_no,
            spc_baudrate=config.spc_baudrate,
            spc_line_ending=terminator_to_label(config.spc_terminator),
            log_keep_count=config.log_keep_count,
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
            self._record_height_sample(reading.value_mm)
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
            self._record_height_sample(reading.value_mm)
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
                self._record_height_sample(reading.value_mm)
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
        self.set_connection_config(
            keyence_port=keyence_port,
            spc_port=spc_port,
            keyence_out_no=self.config.keyence_out_no,
            spc_baudrate=self.config.spc_baudrate,
            spc_line_ending=terminator_to_label(self.config.spc_terminator),
        )

    def set_connection_config(
        self,
        *,
        keyence_port: str,
        spc_port: str,
        keyence_out_no: int | str,
        spc_baudrate: int | str,
        spc_line_ending: str,
    ) -> None:
        self._force_stream_off("changing ports")

        try:
            keyence_out_no = int(str(keyence_out_no).strip())
            spc_baudrate = int(str(spc_baudrate).strip())

            if not 1 <= keyence_out_no <= 8:
                raise ValueError("Keyence OUT must be 1 through 8")

            if spc_baudrate <= 0:
                raise ValueError("SPC baud rate must be positive")

            spc_terminator = line_ending_to_terminator(spc_line_ending)

        except Exception as error:
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"Config change failed: {error}")
            self._status_changed()
            return

        if self.state.keyence.connected:
            self.input_client.close()

        if self.state.spc.connected:
            self.spc_client.disconnect()

        self.config.keyence_port = keyence_port
        self.config.spc_port = spc_port
        self.config.keyence_out_no = keyence_out_no
        self.config.spc_baudrate = spc_baudrate
        self.config.spc_terminator = spc_terminator

        self.state.keyence.port = keyence_port
        self.state.spc.port = spc_port
        self.state.keyence_out_no = keyence_out_no
        self.state.spc_baudrate = spc_baudrate
        self.state.spc_line_ending = terminator_to_label(spc_terminator)

        self.input_client = self._create_input_client()
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

    def handle_spc_request(self, message: str) -> str | bytes | None:
        return self.spc_commands.handle(message, SpcCommandContext(controller=self))

    def set_height_data_visible(self, visible: bool) -> None:
        self.state.height_data_visible = visible
        self._status_changed()

    def set_log_keep_count(self, keep_count: int | str) -> None:
        try:
            keep_count = int(str(keep_count).strip())

            if keep_count <= 0:
                raise ValueError("Log keep count must be positive")

        except Exception as error:
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"Log setting change failed: {error}")
            self._status_changed()
            return

        self.config.log_keep_count = keep_count
        self.state.log_keep_count = keep_count
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
                if reading.ok:
                    self._record_height_sample(reading.value_mm)
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

    def format_latest_height_reply(self) -> str:
        return self._format_latest_height_reply()

    def _record_height_sample(self, value_mm: float) -> None:
        self.height_trackers.add_sample(value_mm)

    def _read_height_for_spc(self) -> str:
        if not self.state.keyence.connected:
            return "ERROR KEYENCE_NOT_CONNECTED"

        if self.state.streaming:
            return "ERROR STREAMING_ACTIVE"

        try:
            reading = self.input_client.read_average(samples=self.config.average_samples)

            self.state.keyence.height_mm = reading.value_mm
            self._record_height_sample(reading.value_mm)
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
            self._emit(BridgeEventType.ERROR, f"SPC READ_HEIGHT failed: {error}")
            return f"ERROR {error}"

    def read_height_for_spc(self) -> str:
        return self._read_height_for_spc()

    def _start_stream_for_spc(self) -> str:
        if self.state.streaming:
            return SPC_SUCCESS_STATUS

        self.start_stream()

        if self.state.streaming:
            return SPC_SUCCESS_STATUS

        return SPC_FAILURE_STATUS

    def start_stream_for_spc(self) -> str:
        return self._start_stream_for_spc()

    def _stop_stream_for_spc(self) -> str:
        if not self.state.streaming:
            return SPC_SUCCESS_STATUS

        self.stop_stream()

        if not self.state.streaming:
            return SPC_SUCCESS_STATUS

        return SPC_FAILURE_STATUS

    def stop_stream_for_spc(self) -> str:
        return self._stop_stream_for_spc()

    def prepare_tracking_scan_for_spc(self, registry: str) -> str:
        try:
            self.height_trackers.clear(registry)
            self.height_trackers.start(registry)

            if self.start_stream_for_spc() != SPC_SUCCESS_STATUS:
                self.height_trackers.stop(registry)
                return SPC_FAILURE_STATUS

            self._emit(
                BridgeEventType.SYSTEM,
                f"Prepared tracking scan for registry {registry}",
            )
            return SPC_SUCCESS_STATUS
        except Exception as error:
            self.height_trackers.stop(registry)
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"SPC PREPARE failed: {error}")
            self._status_changed()
            return SPC_FAILURE_STATUS

    def save_tracking_scan_for_spc(self, registry: str) -> str:
        try:
            self.height_trackers.stop(registry)

            if self.stop_stream_for_spc() != SPC_SUCCESS_STATUS:
                return SPC_FAILURE_STATUS

            return self.export_tracking_csv_for_spc(registry)
        except Exception as error:
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"SPC SAVE failed: {error}")
            self._status_changed()
            return SPC_FAILURE_STATUS

    def export_tracking_csv_for_spc(self, registry: str) -> str:
        try:
            path = self.export_tracking_csv(registry)
            self._emit(BridgeEventType.SYSTEM, f"Exported tracking CSV: {path}")
            return SPC_SUCCESS_STATUS
        except Exception as error:
            self.state.last_error = str(error)
            self._emit(BridgeEventType.ERROR, f"SPC CSV export failed: {error}")
            self._status_changed()
            return SPC_FAILURE_STATUS

    def export_tracking_csv(self, registry: str) -> Path:
        samples = [
            CsvHeightSample(value_mm=value, valid=True)
            for value in self.height_trackers.values(registry)
        ]

        return export_height_samples(
            source_name=f"register-{registry}",
            samples=samples,
        )

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
            settings=SerialPortSettings(
                port=self.config.keyence_port,
                baudrate=self.config.keyence_baudrate,
                timeout=self.config.keyence_timeout,
            ),
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
