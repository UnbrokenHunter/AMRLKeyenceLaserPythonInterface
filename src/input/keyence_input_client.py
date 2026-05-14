"""
Keyence CL-3000 RS-232 input client.
"""

from __future__ import annotations

from src.input.input_client import InputClient, InputReading
from src.input.keyence_protocol import parse_stream_response

try:
    import serial
except ImportError:
    serial = None


CR = "\r"


class KeyenceInputClient(InputClient):
    """Talks to a real Keyence CL-3000 over RS-232."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        out_no: int = 1,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.out_no = out_no
        self._ser = None

    def open(self) -> None:
        if serial is None:
            raise RuntimeError("pyserial is not installed. Run: pip install pyserial")

        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.timeout,
        )

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def send_command(self, command: str) -> str:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        self._ser.reset_input_buffer()
        self._ser.write((command + CR).encode("ascii"))

        raw = self._ser.read_until(b"\r")
        if not raw:
            raise TimeoutError(f"No response from Keyence for command {command!r}")

        return raw.decode("ascii", errors="replace").strip()

    def start_streaming(self) -> None:
        """
        Start automatic transmission for OUT1 only.

        NS,3,10000000 means:
        - 3: value + result info + judgment
        - 10000000: OUT1 enabled, OUT2-OUT8 disabled
        """
        self.expect_response("NS,3,10000000", expected="NS")

    def stop_streaming(self) -> None:
        self.expect_response("NT", expected="NT")

    def read_stream_line(self) -> InputReading:
        if self._ser is None:
            raise RuntimeError("Serial port is not open")

        raw = self._ser.read_until(b"\r")
        if not raw:
            raise TimeoutError("No automatic-transmission data from Keyence")

        line = raw.decode("ascii", errors="replace").strip()
        return parse_stream_response(line)
