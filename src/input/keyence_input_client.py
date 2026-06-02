"""Real serial client for the Keyence controller.

KeyenceInputClient owns the RS232/USB-RS232 conversation with the Keyence
controller. It sends Keyence commands, parses one-shot measurement responses,
starts/stops Keyence streaming output, and converts stream lines into InputReading
objects for the controller.

The client does not know about SPC recipes or UI panels. BridgeController uses
this client as the real hardware implementation of the shared InputClient
interface.
"""

from __future__ import annotations

from io import BytesIO
import time

import serial

from src.input.input_client import InputClient, InputReading
from src.input.keyence_protocol import parse_ms3_response, parse_stream_response
from src.serial_settings import SerialPortSettings

CR = "\r"


class KeyenceInputClient(InputClient):
    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 115200,
        timeout: float = 1.0,
        out_no: int = 2,
        settings: SerialPortSettings | None = None,
    ) -> None:
        if settings is None:
            if port is None:
                raise ValueError("Keyence serial port is required")

            settings = SerialPortSettings(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
            )

        self.settings = settings
        self.out_no = out_no
        self._ser: serial.Serial | None = None
        self.streaming = False
        self._stream_buffer = BytesIO()

    def open(self) -> None:
        self._ser = serial.Serial(**self.settings.serial_kwargs())

        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()
        self._reset_stream_buffer()

        self.clear_stale_streaming_output()
        

    def close(self) -> None:
        if self._ser is not None:
            try:
                if self.streaming:
                    self.stop_streaming()
            except Exception:
                pass

            self._ser.close()
            self._ser = None

    def send_command(self, command: str) -> str:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        if self.streaming:
            raise RuntimeError("Cannot send command while Keyence streaming is active")

        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()
        self._reset_stream_buffer()

        self._ser.write((command + CR).encode("ascii"))

        raw = self._ser.read_until(b"\r")

        if not raw:
            raise TimeoutError(f"No response from Keyence for command {command!r}")

        try:
            response = raw.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise RuntimeError(
                f"Non-ASCII response to {command!r}. "
                f"raw={raw!r}, hex={raw.hex(' ')}"
            ) from error

        return response

    def write_command_no_response(self, command: str) -> None:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        self._ser.write((command + CR).encode("ascii"))

    def read_raw_line(self) -> str:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        raw = self._ser.read_until(b"\r")
        return raw.decode("ascii", errors="replace").strip()

    def read_once(self) -> InputReading:
        response = self.send_command(self.read_command())
        return parse_ms3_response(response)

    def read_command(self) -> str:
        return f"MS,3,{self.out_no}"

    def start_streaming(self) -> None:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        if self.streaming:
            return

        response = self.send_command(self.stream_command())

        if response != "NS":
            raise RuntimeError(
                f"Unexpected response to {self.stream_command()!r}: "
                f"got {response!r}, expected 'NS'"
            )

        self.streaming = True

    def stop_streaming(self) -> None:
        """
        Stop Keyence streaming output.

        The Keyence stream RX path is measurement data. ``NT`` is sent as a
        command, then queued stream data is flushed so the next one-shot command
        gets its own response.
        """
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        self.write_command_no_response("NT")
        self.streaming = False

        time.sleep(0.005)
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()
        self._reset_stream_buffer()

    def clear_stale_streaming_output(self) -> None:
        """
        Best-effort cleanup for stream output left active by an earlier run.

        This keeps connect from being polluted by queued stream lines without
        treating the stop command as an RX-side stream message.
        """
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        self._ser.write(b"NT\r")
        self._ser.flush()
        time.sleep(0.005)

        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()
        self._reset_stream_buffer()
        self.streaming = False

    def stream_command(self) -> str:
        return f"NS,3,{self._out_mask(self.out_no)}"
    
    def read_available_stream_readings(self, max_readings: int = 500) -> list[InputReading]:
        """
        Drain complete Keyence stream lines that are already buffered.

        This is intentionally non-blocking: if no bytes are waiting, it returns
        an empty list so a background collector can sleep briefly instead of
        stalling the UI or command path.
        """
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        if not self.streaming:
            raise RuntimeError("Keyence streaming output is not active")

        waiting = self._ser.in_waiting
        buffered = self._stream_buffer.getvalue()

        if waiting <= 0 and b"\r" not in buffered:
            return []

        if waiting > 0:
            self._stream_buffer.seek(0, 2)
            self._stream_buffer.write(self._ser.read(waiting))

        readings: list[InputReading] = []
        buffer_bytes = self._stream_buffer.getvalue()

        while b"\r" in buffer_bytes and len(readings) < max_readings:
            line_bytes, _, buffer_bytes = buffer_bytes.partition(b"\r")
            line = line_bytes.decode("ascii", errors="replace").strip()

            if not line:
                continue
                                                                                                                                                                                                                       
            readings.append(parse_stream_response(line))

        self._replace_stream_buffer(buffer_bytes)
        return readings

    def _reset_stream_buffer(self) -> None:
        self._stream_buffer = BytesIO()

    def _replace_stream_buffer(self, data: bytes) -> None:
        self._stream_buffer = BytesIO(data)
        self._stream_buffer.seek(0, 2)

    @staticmethod
    def _out_mask(out_no: int) -> str:
        if not 1 <= out_no <= 8:
            raise ValueError(f"Invalid OUT number: {out_no}")

        bits = ["0"] * 8
        bits[out_no - 1] = "1"
        return "".join(bits)
