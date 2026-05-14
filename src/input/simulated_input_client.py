"""
Simulated Keyence input client.

This implements the same InputClient interface as KeyenceInputClient, but it does
not use serial hardware.
"""

from __future__ import annotations

import math
import random
import time

from src.input.input_client import InputClient, InputReading
from src.input.keyence_protocol import format_keyence_value, parse_ms3_response, parse_stream_response


class SimulatedInputClient(InputClient):
    def __init__(
        self,
        base_height_mm: float = 12.000,
        noise_std_mm: float = 0.002,
        drift_per_sec_mm: float = 0.0001,
        invalid_probability: float = 0.0,
    ) -> None:
        self.base_height_mm = base_height_mm
        self.noise_std_mm = noise_std_mm
        self.drift_per_sec_mm = drift_per_sec_mm
        self.invalid_probability = invalid_probability

        self.measurement_mode = True
        self.measurement_on = True
        self.emission_on = True
        self.streaming = False
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

        if command == "MS,3,1":
            return self._make_ms3_response()

        if command == "NS,3,10000000":
            if self.streaming:
                return "ER,84"
            self.streaming = True
            return "NS"

        if command == "NT":
            self.streaming = False
            return "NT"

        return "ER,02"

    def read_once(self) -> InputReading:
        response = self.send_command("MS,3,1")
        return parse_ms3_response(response)

    def start_streaming(self) -> None:
        self.expect_response("NS,3,10000000", expected="NS")

    def stop_streaming(self) -> None:
        self.expect_response("NT", expected="NT")

    def read_stream_line(self) -> InputReading:
        if not self.streaming:
            raise RuntimeError("Simulator is not streaming. Call start_streaming() first.")

        line = self._make_stream_response()
        return parse_stream_response(line)

    def _make_ms3_response(self) -> str:
        reading = self._make_reading()
        return f"MS,{format_keyence_value(reading.value_mm)},{reading.result_info},{reading.judgment}"

    def _make_stream_response(self) -> str:
        reading = self._make_reading()
        return f"NS,{format_keyence_value(reading.value_mm)},{reading.result_info},{reading.judgment}"

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
