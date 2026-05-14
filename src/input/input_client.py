"""
Shared abstract input-client interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from statistics import mean
from typing import Optional


@dataclass(frozen=True)
class InputReading:
    value_mm: float
    result_info: int  # 0 normal, 1 invalid, 2 judgment standby
    judgment: str     # HI, GO, LO, or --
    raw: str

    @property
    def ok(self) -> bool:
        return self.result_info == 0 and self.judgment in {"HI", "GO", "LO"}


class InputClient(ABC):
    """Abstract base class for real/simulated input devices."""

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def send_command(self, command: str) -> str:
        """Send a device command without the trailing CR. Return response without CR."""
        pass

    @abstractmethod
    def read_once(self) -> InputReading:
        """Read one processed measurement from the input device."""
        pass

    def initialize(self, emission_on: bool = True) -> None:
        """
        Optional shared startup behavior for CL-3000-like devices.

        Subclasses may override if their hardware/simulator needs different setup.
        """
        self.expect_response("R0", expected="R0")
        self.expect_response("MC,1", expected="MC")

        if emission_on:
            self.expect_response("LC,1", expected="LC")

    def read_average(self, samples: int = 5) -> InputReading:
        readings = [self.read_once() for _ in range(samples)]
        good = [reading for reading in readings if reading.ok]

        if not good:
            raise RuntimeError(f"No valid readings: {readings!r}")

        averaged = mean(reading.value_mm for reading in good)

        return InputReading(
            value_mm=averaged,
            result_info=0,
            judgment="GO",
            raw=f"AVG,{averaged:+09.3f},0,GO",
        )

    def expect_response(self, command: str, expected: Optional[str] = None) -> None:
        response = self.send_command(command)
        expected_response = command if expected is None else expected

        if response != expected_response:
            raise RuntimeError(
                f"Unexpected response to {command!r}: "
                f"got {response!r}, expected {expected_response!r}"
            )
