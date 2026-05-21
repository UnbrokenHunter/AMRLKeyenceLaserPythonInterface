"""Shared serial-port settings and helpers."""

from __future__ import annotations

from dataclasses import dataclass

import serial


@dataclass(frozen=True)
class SerialPortSettings:
    port: str
    baudrate: int
    bytesize: int = serial.EIGHTBITS
    parity: str = serial.PARITY_NONE
    stopbits: float = serial.STOPBITS_ONE
    timeout: float = 1.0
    write_timeout: float | None = None

    def serial_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "port": self.port,
            "baudrate": self.baudrate,
            "bytesize": self.bytesize,
            "parity": self.parity,
            "stopbits": self.stopbits,
            "timeout": self.timeout,
        }

        if self.write_timeout is not None:
            kwargs["write_timeout"] = self.write_timeout

        return kwargs


@dataclass(frozen=True)
class SpcSerialSettings(SerialPortSettings):
    baudrate: int = 9600
    timeout: float = 0.01
    write_timeout: float | None = 0.5
    terminator: bytes = b"\r\n"
    read_terminators: tuple[bytes, ...] = (b"\r\n", b"\n", b"\r")


def line_ending_to_terminator(line_ending: str) -> bytes:
    normalized = line_ending.strip().upper().replace("+", "")

    if normalized == "CRLF":
        return b"\r\n"

    if normalized == "LF":
        return b"\n"

    if normalized == "CR":
        return b"\r"

    raise ValueError("SPC line ending must be CRLF, LF, or CR")


def terminator_to_label(terminator: bytes) -> str:
    if terminator == b"\r\n":
        return "CRLF"

    if terminator == b"\n":
        return "LF"

    if terminator == b"\r":
        return "CR"

    return "CUSTOM"
