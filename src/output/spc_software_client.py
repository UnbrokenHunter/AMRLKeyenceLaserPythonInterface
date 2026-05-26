"""Serial peer for SpiiPlusSPC software.

SPC is software on the PC, not hardware controlled by this app. This client
opens the Python side of a com0com virtual COM pair and waits for SPC to request
data. For example, SPC may open COM20 while Python opens the paired COM21.

Reads are line-oriented with flexible input terminators. Replies are encoded as
ASCII and are terminated with the configured SPC reply terminator, usually CRLF.
"""

from __future__ import annotations

import serial

from src.serial_settings import SpcSerialSettings


class SpcSoftwareClient:
    def __init__(self, settings: SpcSerialSettings) -> None:
        self.settings = settings
        self._ser: serial.Serial | None = None
        self._rx_buffer = bytearray()

    def connect(self) -> None:
        self._ser = serial.Serial(**self.settings.serial_kwargs())
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()
        self._rx_buffer.clear()

    def disconnect(self) -> None:
        if self._ser is None:
            return

        self._ser.close()
        self._ser = None
        self._rx_buffer.clear()

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def read_message(self) -> str | None:
        """Return one complete line from SPC, or None when no line is ready."""
        if self._ser is None:
            raise RuntimeError("SPC serial port is not open")

        waiting = self._ser.in_waiting
        if waiting:
            self._rx_buffer.extend(self._ser.read(waiting))
        elif not self._rx_buffer:
            return None

        match = self._find_next_terminator()
        if match is None:
            return None

        terminator_index, terminator = match
        raw_message = bytes(self._rx_buffer[:terminator_index])
        del self._rx_buffer[: terminator_index + len(terminator)]

        return raw_message.decode("ascii", errors="replace").strip()

    def send_reply(self, reply: str | bytes) -> None:
        if self._ser is None:
            raise RuntimeError("SPC serial port is not open")

        if isinstance(reply, str):
            payload = reply.encode("ascii")
        else:
            payload = reply

        if not payload.endswith(self.settings.terminator):
            payload += self.settings.terminator

        self._ser.write(payload)
        self._ser.flush()

    def _find_next_terminator(self) -> tuple[int, bytes] | None:
        matches = [
            (index, terminator)
            for terminator in self.settings.read_terminators
            if (index := self._rx_buffer.find(terminator)) >= 0
        ]

        if not matches:
            return None

        return min(matches, key=lambda match: match[0])
