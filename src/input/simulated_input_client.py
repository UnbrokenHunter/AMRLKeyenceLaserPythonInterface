"""Simulated Keyence input client.

This implements the same InputClient interface as KeyenceInputClient, but it does
not use serial hardware. It exists for programming/debugging workflows where the
real Keyence controller is unavailable.

The simulator is intentionally narrow and may lag newer bridge behavior. Treat it
as a convenience for testing Keyence-style command handling and UI flows, not as
a full SPC/com0com/hardware substitute.
"""

from __future__ import annotations

import math
import random
import time

from src.input.input_client import InputClient, InputReading
from src.input.keyence_protocol import (
    format_keyence_value,
    parse_ms3_response,
    parse_stream_response,
)


class SimulatedInputClient(InputClient):
    def __init__(
        self,
        base_height_mm: float = 12.000,
        noise_std_mm: float = 0.002,
        drift_per_sec_mm: float = 0.0001,
        invalid_probability: float = 0.0,
        out_no: int = 2,
    ) -> None:
        self.base_height_mm = base_height_mm
        self.noise_std_mm = noise_std_mm
        self.drift_per_sec_mm = drift_per_sec_mm
        self.invalid_probability = invalid_probability
        self.out_no = out_no

        self.measurement_mode = True
        self.measurement_on = True
        self.emission_on = True
        self.streaming = False
        self.current_program = 0
        self._start_time = time.monotonic()

    def open(self) -> None:
        pass

    def close(self) -> None:
        self.streaming = False

    def send_command(self, command: str) -> str:
        command = command.strip()

        if command == "R0":
            self.measurement_mode = True
            return "R0"

        if command == "Q0":
            self.measurement_mode = False
            return "Q0"

        if command in {"MC,1", "MC,0"}:
            self.measurement_on = command.endswith(",1")
            return "MC"

        if command in {"LC,1", "LC,0"}:
            self.emission_on = command.endswith(",1")
            return "LC"

        if command == "PR":
            return f"PR,{self.current_program}"

        if command.startswith("PW,"):
            try:
                program = int(command.split(",", maxsplit=1)[1])
            except (IndexError, ValueError):
                return "ER,02"

            if program < 0:
                return "ER,02"

            self.current_program = program
            return "PW"

        if command.startswith("MS,3,"):
            return self._make_ms3_response()

        if command.startswith("NS,3,"):
            if self.streaming:
                return "ER,84"

            self.streaming = True
            return "NS"

        if command == "NT":
            self.streaming = False
            return "NT"

        return "ER,02"

    def read_once(self) -> InputReading:
        response = self.send_command(self.read_command())
        return parse_ms3_response(response)

    def read_command(self) -> str:
        return f"MS,3,{self.out_no}"

    def start_streaming(self) -> None:
        self.expect_response(self.stream_command(), expected="NS")
        self.streaming = True

    def stop_streaming(self) -> None:
        self.expect_response("NT", expected="NT")
        self.streaming = False

    def read_stream_line(self) -> InputReading:
        if not self.streaming:
            raise RuntimeError("Simulator automatic transmission is not active")

        line = self._make_stream_response()
        return parse_stream_response(line)

    def stream_command(self) -> str:
        return f"NS,3,{self._out_mask(self.out_no)}"

    @staticmethod
    def _out_mask(out_no: int) -> str:
        if not 1 <= out_no <= 8:
            raise ValueError(f"Invalid OUT number: {out_no}")

        bits = ["0"] * 8
        bits[out_no - 1] = "1"
        return "".join(bits)

    def _make_ms3_response(self) -> str:
        reading = self._make_reading()
        return (
            f"MS,{format_keyence_value(reading.value_mm)},"
            f"{reading.result_info},{reading.judgment}"
        )

    def _make_stream_response(self) -> str:
        reading = self._make_reading()

        # Automatic-transmission stream line.
        # This parser also supports lines without the NS prefix, but including it
        # makes the simulator easier to read/debug.
        return (
            f"NS,{format_keyence_value(reading.value_mm)},"
            f"{reading.result_info},{reading.judgment}"
        )

    def _make_reading(self) -> InputReading:
        if not self.measurement_mode or not self.measurement_on or not self.emission_on:
            return InputReading(
                value_mm=-999999.0,
                result_info=1,
                judgment="--",
                raw="SIM_INVALID_NOT_MEASURING",
            )

        if random.random() < self.invalid_probability:
            return InputReading(
                value_mm=-999999.0,
                result_info=1,
                judgment="--",
                raw="SIM_INVALID_RANDOM",
            )

        elapsed = time.monotonic() - self._start_time

        value = (
            self.base_height_mm
            + self.drift_per_sec_mm * elapsed
            + 0.010 * math.sin(2.0 * math.pi * 0.20 * elapsed)
            + random.gauss(0.0, self.noise_std_mm)
        )

        judgment = "GO"

        if value > self.base_height_mm + 0.050:
            judgment = "HI"

        elif value < self.base_height_mm - 0.050:
            judgment = "LO"

        return InputReading(
            value_mm=value,
            result_info=0,
            judgment=judgment,
            raw="SIM",
        )
